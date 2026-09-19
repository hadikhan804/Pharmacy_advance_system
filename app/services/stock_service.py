from __future__ import annotations

from app.auth.session import Session
from app.constants import REF_ADJUST
from app.db.database import get_db, row_to_dict, rows_to_dicts, transaction
from app.services import audit_service, settings_service
from app.utils.dates import now_iso, today


def current_stock(search: str = "") -> list[dict]:
    like = f"%{search.strip()}%"
    return rows_to_dicts(
        get_db().execute(
            """
            SELECT m.id AS medicine_id, m.brand_name, m.generic_name, m.reorder_level, m.unit,
                   c.name AS company_name,
                   COALESCE(SUM(b.qty), 0) AS qty,
                   COALESCE(SUM(b.qty * b.cost_paisa), 0) AS value_cost,
                   COALESCE(SUM(b.qty * b.sale_paisa), 0) AS value_sale
            FROM medicines m
            LEFT JOIN companies c ON c.id = m.company_id
            LEFT JOIN batches b ON b.medicine_id = m.id
            WHERE m.active = 1 AND (? = '' OR m.brand_name LIKE ? OR IFNULL(m.generic_name,'') LIKE ?)
            GROUP BY m.id
            ORDER BY m.brand_name
            """,
            (search.strip(), like, like),
        ).fetchall()
    )


def batches_for_medicine(medicine_id: int, include_empty: bool = True) -> list[dict]:
    sql = """
        SELECT b.*, m.brand_name,
               CASE WHEN b.expiry < date('now') THEN 1 ELSE 0 END AS expired
        FROM batches b
        JOIN medicines m ON m.id = b.medicine_id
        WHERE b.medicine_id = ?
    """
    if not include_empty:
        sql += " AND b.qty > 0"
    sql += " ORDER BY b.expiry ASC"
    return rows_to_dicts(get_db().execute(sql, (medicine_id,)).fetchall())


def all_batches(search: str = "") -> list[dict]:
    like = f"%{search.strip()}%"
    return rows_to_dicts(
        get_db().execute(
            """
            SELECT b.*, m.brand_name, m.generic_name, c.name AS company_name,
                   CASE WHEN b.expiry < date('now') THEN 1 ELSE 0 END AS expired
            FROM batches b
            JOIN medicines m ON m.id = b.medicine_id
            LEFT JOIN companies c ON c.id = m.company_id
            WHERE (? = '' OR m.brand_name LIKE ? OR b.batch_no LIKE ?)
            ORDER BY m.brand_name, b.expiry
            """,
            (search.strip(), like, like),
        ).fetchall()
    )


def fefo_batch(medicine_id: int) -> dict | None:
    return row_to_dict(
        get_db().execute(
            """
            SELECT * FROM batches
            WHERE medicine_id = ? AND qty > 0 AND expiry >= date('now')
            ORDER BY expiry ASC, id ASC
            LIMIT 1
            """,
            (medicine_id,),
        ).fetchone()
    )


def get_batch(batch_id: int) -> dict | None:
    return row_to_dict(get_db().execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone())


def sellable_batches(medicine_id: int) -> list[dict]:
    return rows_to_dicts(
        get_db().execute(
            """
            SELECT * FROM batches
            WHERE medicine_id = ? AND qty > 0 AND expiry >= date('now')
            ORDER BY expiry ASC
            """,
            (medicine_id,),
        ).fetchall()
    )


def find_or_create_batch(conn, medicine_id: int, batch_no: str, expiry: str, cost_paisa: int, sale_paisa: int) -> int:
    row = conn.execute(
        """
        SELECT id FROM batches
        WHERE medicine_id = ? AND batch_no = ? AND expiry = ?
        """,
        (medicine_id, batch_no.strip(), expiry),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE batches SET cost_paisa = ?, sale_paisa = ? WHERE id = ?",
            (cost_paisa, sale_paisa, row["id"]),
        )
        return row["id"]
    cur = conn.execute(
        """
        INSERT INTO batches(medicine_id, batch_no, expiry, qty, cost_paisa, sale_paisa)
        VALUES (?, ?, ?, 0, ?, ?)
        """,
        (medicine_id, batch_no.strip(), expiry, cost_paisa, sale_paisa),
    )
    return cur.lastrowid


def add_stock(conn, batch_id: int, qty: int, ref_type: str, ref_id: int | None, notes: str = "") -> None:
    batch = conn.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
    if not batch:
        raise ValueError("Batch not found")
    conn.execute("UPDATE batches SET qty = qty + ? WHERE id = ?", (qty, batch_id))
    conn.execute(
        """
        INSERT INTO stock_ledger(medicine_id, batch_id, direction, qty, ref_type, ref_id, notes, user_id, ts)
        VALUES (?, ?, 'in', ?, ?, ?, ?, ?, ?)
        """,
        (batch["medicine_id"], batch_id, qty, ref_type, ref_id, notes, Session.user_id(), now_iso()),
    )


def remove_stock(conn, batch_id: int, qty: int, ref_type: str, ref_id: int | None, notes: str = "") -> None:
    batch = conn.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
    if not batch:
        raise ValueError("Batch not found")
    if batch["qty"] < qty:
        raise ValueError("Insufficient stock")
    conn.execute("UPDATE batches SET qty = qty - ? WHERE id = ?", (qty, batch_id))
    conn.execute(
        """
        INSERT INTO stock_ledger(medicine_id, batch_id, direction, qty, ref_type, ref_id, notes, user_id, ts)
        VALUES (?, ?, 'out', ?, ?, ?, ?, ?, ?)
        """,
        (batch["medicine_id"], batch_id, qty, ref_type, ref_id, notes, Session.user_id(), now_iso()),
    )


def adjust_stock(batch_id: int, new_qty: int, reason: str) -> None:
    with transaction() as conn:
        batch = conn.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
        if not batch:
            raise ValueError("Batch not found")
        delta = int(new_qty) - int(batch["qty"])
        if delta == 0:
            return
        if delta > 0:
            add_stock(conn, batch_id, delta, REF_ADJUST, None, reason)
        else:
            remove_stock(conn, batch_id, -delta, REF_ADJUST, None, reason)
        audit_service.log("stock.adjust", "batches", batch_id, f"{reason} delta={delta}")


def ledger(search: str = "", limit: int = 1000) -> list[dict]:
    like = f"%{search.strip()}%"
    return rows_to_dicts(
        get_db().execute(
            """
            SELECT l.*, m.brand_name, b.batch_no, u.username
            FROM stock_ledger l
            JOIN medicines m ON m.id = l.medicine_id
            LEFT JOIN batches b ON b.id = l.batch_id
            LEFT JOIN users u ON u.id = l.user_id
            WHERE (? = '' OR m.brand_name LIKE ? OR l.ref_type LIKE ? OR IFNULL(b.batch_no,'') LIKE ?)
            ORDER BY l.id DESC
            LIMIT ?
            """,
            (search.strip(), like, like, like, limit),
        ).fetchall()
    )


def valuation() -> dict:
    row = get_db().execute(
        """
        SELECT COALESCE(SUM(qty * cost_paisa), 0) AS cost,
               COALESCE(SUM(qty * sale_paisa), 0) AS sale
        FROM batches WHERE qty > 0
        """
    ).fetchone()
    return {"cost": row["cost"], "sale": row["sale"]}


def low_stock() -> list[dict]:
    return rows_to_dicts(
        get_db().execute(
            """
            SELECT m.id, m.brand_name, m.generic_name, m.reorder_level, m.unit,
                   COALESCE(SUM(b.qty), 0) AS qty
            FROM medicines m
            LEFT JOIN batches b ON b.medicine_id = m.id
            WHERE m.active = 1
            GROUP BY m.id
            HAVING qty <= m.reorder_level
            ORDER BY qty ASC, m.brand_name
            """
        ).fetchall()
    )


def out_of_stock() -> list[dict]:
    return [r for r in low_stock() if r["qty"] <= 0]


def expiring_within(days: int) -> list[dict]:
    return rows_to_dicts(
        get_db().execute(
            """
            SELECT b.*, m.brand_name, m.generic_name, c.name AS company_name,
                   CAST(julianday(b.expiry) - julianday('now') AS INTEGER) AS days_left
            FROM batches b
            JOIN medicines m ON m.id = b.medicine_id
            LEFT JOIN companies c ON c.id = m.company_id
            WHERE b.qty > 0 AND b.expiry >= date('now') AND b.expiry <= date('now', ?)
            ORDER BY b.expiry ASC
            """,
            (f"+{int(days)} days",),
        ).fetchall()
    )


def expired() -> list[dict]:
    return rows_to_dicts(
        get_db().execute(
            """
            SELECT b.*, m.brand_name, m.generic_name, c.name AS company_name
            FROM batches b
            JOIN medicines m ON m.id = b.medicine_id
            LEFT JOIN companies c ON c.id = m.company_id
            WHERE b.qty > 0 AND b.expiry < date('now')
            ORDER BY b.expiry ASC
            """
        ).fetchall()
    )


def expiry_buckets() -> dict[int, list[dict]]:
    result = {}
    for days in settings_service.expiry_windows():
        result[days] = expiring_within(days)
    return result
