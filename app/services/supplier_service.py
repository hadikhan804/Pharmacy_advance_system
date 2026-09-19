from __future__ import annotations

from app.auth.session import Session
from app.db.database import get_db, row_to_dict, rows_to_dicts, transaction
from app.services import audit_service, purchase_service
from app.utils.dates import now_iso


def list_suppliers(search: str = "", active_only: bool = False) -> list[dict]:
    like = f"%{search.strip()}%"
    sql = """
        SELECT s.*,
               COALESCE((
                   SELECT SUM(p.total_paisa - p.returned_paisa - p.paid_paisa)
                   FROM purchases p WHERE p.supplier_id = s.id
               ), 0) AS payable_paisa
        FROM suppliers s
        WHERE (? = '' OR s.name LIKE ? OR IFNULL(s.phone,'') LIKE ?)
    """
    params: list = [search.strip(), like, like]
    if active_only:
        sql += " AND s.active = 1"
    sql += " ORDER BY s.name"
    return rows_to_dicts(get_db().execute(sql, params).fetchall())


def get_supplier(supplier_id: int) -> dict | None:
    return row_to_dict(
        get_db().execute(
            """
            SELECT s.*,
                   COALESCE((
                       SELECT SUM(p.total_paisa - p.returned_paisa - p.paid_paisa)
                       FROM purchases p WHERE p.supplier_id = s.id
                   ), 0) AS payable_paisa
            FROM suppliers s WHERE s.id = ?
            """,
            (supplier_id,),
        ).fetchone()
    )


def save_supplier(data: dict, supplier_id: int | None = None) -> int:
    fields = (
        data["name"].strip(),
        (data.get("phone") or "").strip(),
        (data.get("address") or "").strip(),
        (data.get("notes") or "").strip(),
        1 if data.get("active", True) else 0,
    )
    with transaction() as conn:
        if supplier_id:
            conn.execute(
                "UPDATE suppliers SET name=?, phone=?, address=?, notes=?, active=? WHERE id=?",
                (*fields, supplier_id),
            )
            audit_service.log("supplier.update", "suppliers", supplier_id, data["name"])
            return supplier_id
        cur = conn.execute(
            "INSERT INTO suppliers(name, phone, address, notes, active) VALUES (?, ?, ?, ?, ?)",
            fields,
        )
        audit_service.log("supplier.create", "suppliers", cur.lastrowid, data["name"])
        return cur.lastrowid


def purchase_history(supplier_id: int) -> list[dict]:
    return rows_to_dicts(
        get_db().execute(
            """
            SELECT p.*, (p.total_paisa - p.returned_paisa - p.paid_paisa) AS due_paisa
            FROM purchases p WHERE p.supplier_id = ? ORDER BY p.id DESC
            """,
            (supplier_id,),
        ).fetchall()
    )


def ledger(supplier_id: int) -> list[dict]:
    purchases = rows_to_dicts(
        get_db().execute(
            """
            SELECT id, IFNULL(invoice_no,'PO') AS ref, date, ts, total_paisa AS debit, 0 AS credit,
                   'purchase' AS kind, notes
            FROM purchases WHERE supplier_id = ? ORDER BY id
            """,
            (supplier_id,),
        ).fetchall()
    )
    pays = rows_to_dicts(
        get_db().execute(
            """
            SELECT id, 'PAY' AS ref, substr(ts,1,10) AS date, ts, 0 AS debit, amount_paisa AS credit,
                   'payment' AS kind, notes
            FROM supplier_payments WHERE supplier_id = ? ORDER BY id
            """,
            (supplier_id,),
        ).fetchall()
    )
    ppays = rows_to_dicts(
        get_db().execute(
            """
            SELECT pp.id, 'PAY' AS ref, substr(pp.ts,1,10) AS date, pp.ts, 0 AS debit, pp.amount_paisa AS credit,
                   'payment' AS kind, pp.notes
            FROM purchase_payments pp
            JOIN purchases p ON p.id = pp.purchase_id
            WHERE p.supplier_id = ?
            ORDER BY pp.id
            """,
            (supplier_id,),
        ).fetchall()
    )
    rets = rows_to_dicts(
        get_db().execute(
            """
            SELECT r.id, 'RET' AS ref, substr(r.ts,1,10) AS date, r.ts, 0 AS debit, r.amount_paisa AS credit,
                   'return' AS kind, r.reason AS notes
            FROM purchase_returns r
            JOIN purchases p ON p.id = r.purchase_id
            WHERE p.supplier_id = ?
            ORDER BY r.id
            """,
            (supplier_id,),
        ).fetchall()
    )
    rows = purchases + pays + ppays + rets
    rows.sort(key=lambda r: (r["ts"], r["kind"], r["id"]))
    bal = 0
    out = []
    for r in rows:
        bal += r["debit"] - r["credit"]
        item = dict(r)
        item["balance_paisa"] = bal
        out.append(item)
    return out


def record_payment(supplier_id: int, amount_paisa: int, method: str = "Cash", notes: str = "") -> None:
    if amount_paisa <= 0:
        raise ValueError("Amount must be positive")
    remaining = amount_paisa
    with transaction() as conn:
        dues = conn.execute(
            """
            SELECT id, (total_paisa - returned_paisa - paid_paisa) AS due
            FROM purchases
            WHERE supplier_id = ? AND (total_paisa - returned_paisa - paid_paisa) > 0
            ORDER BY date, id
            """,
            (supplier_id,),
        ).fetchall()
        applied = None
        for p in dues:
            if remaining <= 0:
                break
            take = min(remaining, p["due"])
            conn.execute("UPDATE purchases SET paid_paisa = paid_paisa + ? WHERE id = ?", (take, p["id"]))
            purchase_service._refresh_status(conn, p["id"])
            remaining -= take
            applied = p["id"]
        conn.execute(
            """
            INSERT INTO supplier_payments(supplier_id, purchase_id, amount_paisa, method, notes, user_id, ts)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (supplier_id, applied, amount_paisa, method, notes, Session.user_id(), now_iso()),
        )
        audit_service.log("supplier.payment", "suppliers", supplier_id, str(amount_paisa))


def payables() -> list[dict]:
    return rows_to_dicts(
        get_db().execute(
            """
            SELECT s.id, s.name, s.phone,
                   COALESCE(SUM(p.total_paisa - p.returned_paisa - p.paid_paisa), 0) AS payable_paisa
            FROM suppliers s
            JOIN purchases p ON p.supplier_id = s.id
            GROUP BY s.id
            HAVING payable_paisa > 0
            ORDER BY payable_paisa DESC
            """
        ).fetchall()
    )


def total_payables() -> int:
    row = get_db().execute(
        "SELECT COALESCE(SUM(total_paisa - returned_paisa - paid_paisa),0) AS t FROM purchases"
    ).fetchone()
    return row["t"]
