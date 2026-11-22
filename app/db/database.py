from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import db_path
from app.db.schema import SCHEMA_SQL

_connection: sqlite3.Connection | None = None


def connect(path: Path | None = None) -> sqlite3.Connection:
    global _connection
    if _connection is not None:
        return _connection
    target = Path(path) if path else db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    _connection = conn
    return conn


def get_db() -> sqlite3.Connection:
    if _connection is None:
        return connect()
    return _connection


def close_db() -> None:
    global _connection
    if _connection is not None:
        try:
            _connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            _connection.commit()
        except sqlite3.Error:
            pass
        _connection.close()
        _connection = None


def init_db() -> sqlite3.Connection:
    conn = connect()
    conn.executescript(SCHEMA_SQL)
    _migrate(conn)
    conn.commit()
    from app.db.seed import seed_if_needed

    seed_if_needed(conn)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    except sqlite3.Error:
        pass
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(medicines)").fetchall()}
    for name, spec in (
        ("discount_pct", "REAL NOT NULL DEFAULT 0"),
        ("rack", "TEXT DEFAULT ''"),
        ("sale_paisa", "INTEGER NOT NULL DEFAULT 0"),
        ("cost_paisa", "INTEGER NOT NULL DEFAULT 0"),
        ("units_per_pack", "INTEGER NOT NULL DEFAULT 1"),
    ):
        if name not in cols:
            conn.execute(f"ALTER TABLE medicines ADD COLUMN {name} {spec}")
    for row in conn.execute(
        "SELECT id, pack_size, units_per_pack FROM medicines WHERE IFNULL(units_per_pack,1) <= 1"
    ).fetchall():
        raw = str(row["pack_size"] or "").strip()
        if raw.isdigit() and int(raw) > 1:
            conn.execute("UPDATE medicines SET units_per_pack = ? WHERE id = ?", (int(raw), row["id"]))
    _add_columns(conn, "companies", (("phone", "TEXT DEFAULT ''"), ("address", "TEXT DEFAULT ''")))
    _add_columns(conn, "suppliers", (("company_id", "INTEGER"),))
    _link_suppliers_to_companies(conn)
    conn.execute(
        """
        UPDATE sales SET total_paisa = MAX(0, subtotal_paisa + gst_paisa - discount_paisa)
        WHERE status NOT IN ('held', 'voided')
          AND total_paisa < MAX(0, subtotal_paisa + gst_paisa - discount_paisa)
          AND EXISTS (SELECT 1 FROM sale_returns r WHERE r.sale_id = sales.id)
        """
    )


def _add_columns(conn: sqlite3.Connection, table: str, columns) -> None:
    have = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, spec in columns:
        if name not in have:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {spec}")


def _link_suppliers_to_companies(conn: sqlite3.Connection) -> None:
    """The company is the supplier. Give every old supplier row a company so its purchases and dues stay visible."""
    for sup in conn.execute("SELECT * FROM suppliers WHERE company_id IS NULL").fetchall():
        name = (sup["name"] or "").strip() or f"Supplier {sup['id']}"
        row = conn.execute("SELECT id, phone, address FROM companies WHERE lower(name) = lower(?)", (name,)).fetchone()
        if row:
            cid = row["id"]
            conn.execute(
                "UPDATE companies SET phone = COALESCE(NULLIF(phone,''), ?), address = COALESCE(NULLIF(address,''), ?) WHERE id = ?",
                (sup["phone"] or "", sup["address"] or "", cid),
            )
        else:
            cid = conn.execute(
                "INSERT INTO companies(name, notes, active, phone, address) VALUES (?, ?, ?, ?, ?)",
                (name, sup["notes"] or "", sup["active"], sup["phone"] or "", sup["address"] or ""),
            ).lastrowid
        conn.execute("UPDATE suppliers SET company_id = ? WHERE id = ?", (cid, sup["id"]))


@contextmanager
def transaction():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def rows_to_dicts(rows) -> list[dict]:
    return [{k: r[k] for k in r.keys()} for r in rows]
