from __future__ import annotations

from app.auth.session import Session
from app.constants import PAY_PAID, PAY_PARTIAL, PAY_UNPAID, REF_PURCHASE, REF_PURCHASE_RETURN
from app.db.database import get_db, row_to_dict, rows_to_dicts, transaction
from app.services import audit_service, stock_service
from app.utils.dates import now_iso, today


def _status(total: int, paid: int, returned: int) -> str:
    remaining = max(0, total - returned - paid)
    if remaining <= 0:
        return PAY_PAID
    if paid > 0:
        return PAY_PARTIAL
    return PAY_UNPAID


def _refresh_status(conn, purchase_id: int) -> None:
    row = conn.execute("SELECT total_paisa, paid_paisa, returned_paisa FROM purchases WHERE id = ?", (purchase_id,)).fetchone()
    status = _status(row["total_paisa"], row["paid_paisa"], row["returned_paisa"])
    conn.execute("UPDATE purchases SET status = ? WHERE id = ?", (status, purchase_id))


def list_purchases(search: str = "") -> list[dict]:
    like = f"%{search.strip()}%"
    return rows_to_dicts(
        get_db().execute(
            """
            SELECT p.*, s.name AS supplier_name,
                   (p.total_paisa - p.returned_paisa - p.paid_paisa) AS due_paisa
            FROM purchases p
            JOIN suppliers s ON s.id = p.supplier_id
            WHERE (? = '' OR s.name LIKE ? OR IFNULL(p.invoice_no,'') LIKE ?)
            ORDER BY p.id DESC
            """,
            (search.strip(), like, like),
        ).fetchall()
    )


def get_purchase(purchase_id: int) -> dict | None:
    header = row_to_dict(
        get_db().execute(
            """
            SELECT p.*, s.name AS supplier_name,
                   (p.total_paisa - p.returned_paisa - p.paid_paisa) AS due_paisa
            FROM purchases p
            JOIN suppliers s ON s.id = p.supplier_id
            WHERE p.id = ?
            """,
            (purchase_id,),
        ).fetchone()
    )
    if not header:
        return None
    header["items"] = rows_to_dicts(
        get_db().execute(
            """
            SELECT pi.*, m.brand_name
            FROM purchase_items pi
            JOIN medicines m ON m.id = pi.medicine_id
            WHERE pi.purchase_id = ?
            """,
            (purchase_id,),
        ).fetchall()
    )
    return header


def create_purchase(supplier_id: int, invoice_no: str, date: str, items: list[dict], paid_paisa: int = 0, notes: str = "") -> int:
    if not items:
        raise ValueError("No items")
    total = sum(int(i["qty"]) * int(i["cost_paisa"]) for i in items)
    with transaction() as conn:
        cur = conn.execute(
            """
            INSERT INTO purchases(supplier_id, invoice_no, date, total_paisa, paid_paisa, returned_paisa, status, notes, user_id, ts)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
            """,
            (
                supplier_id,
                invoice_no.strip() or None,
                date or today(),
                total,
                paid_paisa,
                _status(total, paid_paisa, 0),
                notes,
                Session.user_id(),
                now_iso(),
            ),
        )
        pid = cur.lastrowid
        for item in items:
            batch_id = stock_service.find_or_create_batch(
                conn,
                item["medicine_id"],
                item["batch_no"],
                item["expiry"],
                int(item["cost_paisa"]),
                int(item["sale_paisa"]),
            )
            stock_service.add_stock(conn, batch_id, int(item["qty"]), REF_PURCHASE, pid, invoice_no)
            conn.execute(
                """
                INSERT INTO purchase_items(purchase_id, medicine_id, batch_id, batch_no, expiry, qty, cost_paisa, sale_paisa)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pid,
                    item["medicine_id"],
                    batch_id,
                    item["batch_no"].strip(),
                    item["expiry"],
                    int(item["qty"]),
                    int(item["cost_paisa"]),
                    int(item["sale_paisa"]),
                ),
            )
        if paid_paisa > 0:
            conn.execute(
                """
                INSERT INTO purchase_payments(purchase_id, supplier_id, amount_paisa, method, notes, user_id, ts)
                VALUES (?, ?, ?, 'Cash', 'At purchase', ?, ?)
                """,
                (pid, supplier_id, paid_paisa, Session.user_id(), now_iso()),
            )
        audit_service.log("purchase.create", "purchases", pid, invoice_no)
    try:
        from app.services import backup_service

        backup_service.event_backup("purchase")
    except Exception:
        pass
    return pid


def add_payment(purchase_id: int, amount_paisa: int, method: str = "Cash", notes: str = "") -> None:
    if amount_paisa <= 0:
        raise ValueError("Amount must be positive")
    with transaction() as conn:
        row = conn.execute("SELECT * FROM purchases WHERE id = ?", (purchase_id,)).fetchone()
        if not row:
            raise ValueError("Purchase not found")
        conn.execute("UPDATE purchases SET paid_paisa = paid_paisa + ? WHERE id = ?", (amount_paisa, purchase_id))
        conn.execute(
            """
            INSERT INTO purchase_payments(purchase_id, supplier_id, amount_paisa, method, notes, user_id, ts)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (purchase_id, row["supplier_id"], amount_paisa, method, notes, Session.user_id(), now_iso()),
        )
        _refresh_status(conn, purchase_id)
        audit_service.log("purchase.payment", "purchases", purchase_id, str(amount_paisa))


def return_items(purchase_id: int, lines: list[dict], reason: str) -> None:
    """lines: {purchase_item_id, qty}"""
    if not lines:
        raise ValueError("No return lines")
    with transaction() as conn:
        purchase = conn.execute("SELECT * FROM purchases WHERE id = ?", (purchase_id,)).fetchone()
        if not purchase:
            raise ValueError("Purchase not found")
        total_return = 0
        for line in lines:
            item = conn.execute("SELECT * FROM purchase_items WHERE id = ? AND purchase_id = ?", (line["purchase_item_id"], purchase_id)).fetchone()
            if not item:
                raise ValueError("Item not found")
            qty = int(line["qty"])
            if qty <= 0:
                continue
            already = conn.execute(
                "SELECT COALESCE(SUM(qty),0) AS q FROM purchase_returns WHERE purchase_id = ? AND medicine_id = ? AND batch_id = ?",
                (purchase_id, item["medicine_id"], item["batch_id"]),
            ).fetchone()["q"]
            if already + qty > item["qty"]:
                raise ValueError("Return qty exceeds purchased qty")
            amount = qty * item["cost_paisa"]
            stock_service.remove_stock(conn, item["batch_id"], qty, REF_PURCHASE_RETURN, purchase_id, reason)
            conn.execute(
                """
                INSERT INTO purchase_returns(purchase_id, medicine_id, batch_id, qty, amount_paisa, reason, user_id, ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (purchase_id, item["medicine_id"], item["batch_id"], qty, amount, reason, Session.user_id(), now_iso()),
            )
            total_return += amount
        conn.execute("UPDATE purchases SET returned_paisa = returned_paisa + ? WHERE id = ?", (total_return, purchase_id))
        _refresh_status(conn, purchase_id)
        audit_service.log("purchase.return", "purchases", purchase_id, reason)
