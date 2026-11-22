from __future__ import annotations

from app.auth.session import Session
from app.constants import PAYMENT_CREDIT, REF_SALE, REF_SALE_RETURN, STATUS_COMPLETED, STATUS_HELD, STATUS_RETURNED, STATUS_VOIDED
from app.db.database import get_db, row_to_dict, rows_to_dicts, transaction
from app.services import audit_service, stock_service
from app.utils.dates import now_iso, today


def next_invoice_no(sale_date: str | None = None) -> str:
    d = sale_date or today()
    prefix = d.replace("-", "")
    row = get_db().execute(
        """
        SELECT invoice_no FROM sales
        WHERE invoice_no LIKE ? AND status != ?
        ORDER BY invoice_no DESC LIMIT 1
        """,
        (f"{prefix}-%", STATUS_HELD),
    ).fetchone()
    if not row or not row["invoice_no"]:
        n = 1
    else:
        try:
            n = int(row["invoice_no"].split("-")[-1]) + 1
        except ValueError:
            n = 1
    return f"{prefix}-{n:04d}"


def _line_totals(item: dict) -> tuple[int, int, int, int]:
    qty = int(item["qty"])
    unit = int(item["unit_price_paisa"])
    discount = int(item.get("discount_paisa") or 0)
    gst_pct = float(item.get("gst_pct") or 0)
    cost = int(item["cost_paisa"])
    if item.get("line_base_paisa") is not None:
        base = int(item["line_base_paisa"]) - discount
    else:
        base = unit * qty - discount
    if base < 0:
        base = 0
    gst = int(round(base * gst_pct / 100.0))
    profit = base - (cost * qty)
    return base, gst, profit, discount


def list_sales(search: str = "", status: str | None = None, user_id: int | None = None) -> list[dict]:
    like = f"%{search.strip()}%"
    sql = """
        SELECT s.*, c.name AS customer_name, u.username,
               COALESCE((SELECT SUM(line_profit_paisa) FROM sale_items si WHERE si.sale_id = s.id), 0)
                 - COALESCE((SELECT SUM(profit_reversal_paisa) FROM sale_returns sr WHERE sr.sale_id = s.id), 0)
                 AS profit_paisa,
               COALESCE((SELECT SUM(amount_paisa) FROM sale_returns sr WHERE sr.sale_id = s.id), 0) AS returned_paisa
        FROM sales s
        LEFT JOIN customers c ON c.id = s.customer_id
        LEFT JOIN users u ON u.id = s.user_id
        WHERE (? = '' OR IFNULL(s.invoice_no,'') LIKE ? OR IFNULL(c.name,'') LIKE ?)
    """
    params: list = [search.strip(), like, like]
    if status:
        sql += " AND s.status = ?"
        params.append(status)
    if user_id:
        sql += " AND s.user_id = ?"
        params.append(user_id)
    sql += " ORDER BY s.id DESC"
    return rows_to_dicts(get_db().execute(sql, params).fetchall())


def get_sale(sale_id: int) -> dict | None:
    header = row_to_dict(
        get_db().execute(
            """
            SELECT s.*, c.name AS customer_name, c.phone AS customer_phone, u.username
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            LEFT JOIN users u ON u.id = s.user_id
            WHERE s.id = ?
            """,
            (sale_id,),
        ).fetchone()
    )
    if not header:
        return None
    header["items"] = rows_to_dicts(
        get_db().execute(
            """
            SELECT si.*, m.brand_name, m.generic_name, b.batch_no, b.expiry
            FROM sale_items si
            JOIN medicines m ON m.id = si.medicine_id
            JOIN batches b ON b.id = si.batch_id
            WHERE si.sale_id = ?
            """,
            (sale_id,),
        ).fetchall()
    )
    header["returns"] = rows_to_dicts(
        get_db().execute(
            "SELECT * FROM sale_returns WHERE sale_id = ? ORDER BY id",
            (sale_id,),
        ).fetchall()
    )
    return header


def hold_sale(items: list[dict], customer_id: int | None, discount_paisa: int, notes: str = "") -> int:
    if not items:
        raise ValueError("Cart is empty")
    subtotal = gst = 0
    for item in items:
        base, line_gst, _, _ = _line_totals(item)
        subtotal += base
        gst += line_gst
    total = max(0, subtotal + gst - int(discount_paisa or 0))
    with transaction() as conn:
        cur = conn.execute(
            """
            INSERT INTO sales(invoice_no, customer_id, date, subtotal_paisa, discount_paisa, gst_paisa,
                              total_paisa, paid_paisa, due_paisa, payment_method, status, notes, user_id, ts)
            VALUES (NULL, ?, ?, ?, ?, ?, ?, 0, 0, NULL, ?, ?, ?, ?)
            """,
            (customer_id, today(), subtotal, discount_paisa, gst, total, STATUS_HELD, notes, Session.user_id(), now_iso()),
        )
        sid = cur.lastrowid
        _insert_items(conn, sid, items)
        audit_service.log("sale.hold", "sales", sid, "")
        return sid


def resume_held(sale_id: int) -> dict:
    sale = get_sale(sale_id)
    if not sale or sale["status"] != STATUS_HELD:
        raise ValueError("Held sale not found")
    with transaction() as conn:
        conn.execute("DELETE FROM sale_items WHERE sale_id = ?", (sale_id,))
        conn.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
        audit_service.log("sale.resume", "sales", sale_id, "")
    return sale


def complete_sale(
    items: list[dict],
    payment_method: str,
    paid_paisa: int,
    customer_id: int | None,
    discount_paisa: int,
    notes: str = "",
    held_id: int | None = None,
) -> int:
    if not items:
        raise ValueError("Cart is empty")
    if payment_method == PAYMENT_CREDIT and not customer_id:
        raise ValueError("Customer required for credit (udhaar)")
    subtotal = gst = profit = 0
    for item in items:
        base, line_gst, line_profit, _ = _line_totals(item)
        subtotal += base
        gst += line_gst
        profit += line_profit
    bill_discount = int(discount_paisa or 0)
    total = max(0, subtotal + gst - bill_discount)
    paid = int(paid_paisa or 0)
    if payment_method != PAYMENT_CREDIT:
        paid = total
        due = 0
    else:
        if paid > total:
            paid = total
        due = total - paid
    invoice = next_invoice_no()
    with transaction() as conn:
        need: dict[int, int] = {}
        for item in items:
            if int(item["qty"]) <= 0:
                raise ValueError("Quantity must be more than 0")
            need[item["batch_id"]] = need.get(item["batch_id"], 0) + int(item["qty"])
        for batch_id, qty in need.items():
            batch = conn.execute(
                "SELECT b.*, m.brand_name, m.active FROM batches b JOIN medicines m ON m.id = b.medicine_id WHERE b.id = ?",
                (batch_id,),
            ).fetchone()
            if not batch:
                raise ValueError("A medicine in the cart no longer exists. Remove it and add it again.")
            if not batch["active"]:
                raise ValueError(f"'{batch['brand_name']}' was deleted. Remove it from the cart.")
            if batch["expiry"] < today():
                raise ValueError(f"Cannot sell expired batch of '{batch['brand_name']}'")
            if batch["qty"] < qty:
                raise ValueError(f"Insufficient stock for '{batch['brand_name']}': {batch['qty']} left, cart has {qty}")
        if held_id:
            conn.execute("DELETE FROM sale_items WHERE sale_id = ?", (held_id,))
            conn.execute("DELETE FROM sales WHERE id = ?", (held_id,))
        cur = conn.execute(
            """
            INSERT INTO sales(invoice_no, customer_id, date, subtotal_paisa, discount_paisa, gst_paisa,
                              total_paisa, paid_paisa, due_paisa, payment_method, status, notes, user_id, ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                invoice,
                customer_id,
                today(),
                subtotal,
                bill_discount,
                gst,
                total,
                paid,
                due,
                payment_method,
                STATUS_COMPLETED,
                notes,
                Session.user_id(),
                now_iso(),
            ),
        )
        sid = cur.lastrowid
        _insert_items(conn, sid, items)
        for item in items:
            stock_service.remove_stock(conn, item["batch_id"], int(item["qty"]), REF_SALE, sid, invoice)
        if customer_id and paid > 0:
            conn.execute(
                """
                INSERT INTO customer_payments(customer_id, sale_id, amount_paisa, method, notes, user_id, ts)
                VALUES (?, ?, ?, ?, 'Sale payment', ?, ?)
                """,
                (customer_id, sid, paid, payment_method, Session.user_id(), now_iso()),
            )
        audit_service.log("sale.complete", "sales", sid, invoice)
        return sid


def _insert_items(conn, sale_id: int, items: list[dict]) -> None:
    for item in items:
        base, gst, profit, discount = _line_totals(item)
        conn.execute(
            """
            INSERT INTO sale_items(sale_id, medicine_id, batch_id, qty, unit_price_paisa, discount_paisa,
                                   gst_paisa, cost_paisa, line_profit_paisa)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sale_id,
                item["medicine_id"],
                item["batch_id"],
                int(item["qty"]),
                int(item["unit_price_paisa"]),
                discount,
                gst,
                int(item["cost_paisa"]),
                profit,
            ),
        )


def return_sale(sale_id: int, lines: list[dict], reason: str) -> None:
    """lines: {sale_item_id, qty}"""
    if not reason.strip():
        raise ValueError("Reason required")
    with transaction() as conn:
        sale = conn.execute("SELECT * FROM sales WHERE id = ?", (sale_id,)).fetchone()
        if not sale or sale["status"] not in (STATUS_COMPLETED, STATUS_RETURNED):
            raise ValueError("Sale cannot be returned")
        any_return = False
        for line in lines:
            item = conn.execute("SELECT * FROM sale_items WHERE id = ? AND sale_id = ?", (line["sale_item_id"], sale_id)).fetchone()
            if not item:
                raise ValueError("Sale item not found")
            qty = int(line["qty"])
            if qty <= 0:
                continue
            already = conn.execute(
                "SELECT COALESCE(SUM(qty),0) AS q FROM sale_returns WHERE sale_item_id = ?",
                (item["id"],),
            ).fetchone()["q"]
            if already + qty > item["qty"]:
                raise ValueError("Return qty exceeds sold qty")
            ratio = qty / item["qty"]
            amount = int(round((item["unit_price_paisa"] * item["qty"] - item["discount_paisa"]) * ratio))
            profit_rev = int(round(item["line_profit_paisa"] * ratio))
            stock_service.add_stock(conn, item["batch_id"], qty, REF_SALE_RETURN, sale_id, reason)
            conn.execute(
                """
                INSERT INTO sale_returns(sale_id, sale_item_id, medicine_id, batch_id, qty, amount_paisa,
                                         profit_reversal_paisa, reason, user_id, ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sale_id,
                    item["id"],
                    item["medicine_id"],
                    item["batch_id"],
                    qty,
                    amount,
                    profit_rev,
                    reason,
                    Session.user_id(),
                    now_iso(),
                ),
            )
            any_return = True
            due = conn.execute("SELECT due_paisa FROM sales WHERE id = ?", (sale_id,)).fetchone()["due_paisa"]
            if due > 0:
                conn.execute(
                    "UPDATE sales SET due_paisa = due_paisa - ? WHERE id = ?",
                    (min(due, amount), sale_id),
                )
        if not any_return:
            raise ValueError("Nothing to return")
        remaining = conn.execute(
            """
            SELECT
              (SELECT COALESCE(SUM(qty),0) FROM sale_items WHERE sale_id = ?)
              - (SELECT COALESCE(SUM(qty),0) FROM sale_returns WHERE sale_id = ?) AS left_qty
            """,
            (sale_id, sale_id),
        ).fetchone()["left_qty"]
        if remaining <= 0:
            conn.execute("UPDATE sales SET status = ? WHERE id = ?", (STATUS_RETURNED, sale_id))
        audit_service.log("sale.return", "sales", sale_id, reason)


def void_sale(sale_id: int, reason: str) -> None:
    if not Session.is_owner():
        raise ValueError("Only the owner can void a sale")
    if not reason.strip():
        raise ValueError("Reason required")
    with transaction() as conn:
        sale = conn.execute("SELECT * FROM sales WHERE id = ?", (sale_id,)).fetchone()
        if not sale or sale["status"] != STATUS_COMPLETED:
            raise ValueError("Only a completed sale can be voided")
        if sale["date"] != today():
            raise ValueError("Void is only allowed on the same day")
        items = conn.execute("SELECT * FROM sale_items WHERE sale_id = ?", (sale_id,)).fetchall()
        for item in items:
            already = conn.execute(
                "SELECT COALESCE(SUM(qty),0) AS q FROM sale_returns WHERE sale_item_id = ?",
                (item["id"],),
            ).fetchone()["q"]
            left = item["qty"] - already
            if left <= 0:
                continue
            stock_service.add_stock(conn, item["batch_id"], left, REF_SALE_RETURN, sale_id, f"VOID {reason}")
            conn.execute(
                """
                INSERT INTO sale_returns(sale_id, sale_item_id, medicine_id, batch_id, qty, amount_paisa,
                                         profit_reversal_paisa, reason, user_id, ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sale_id,
                    item["id"],
                    item["medicine_id"],
                    item["batch_id"],
                    left,
                    int(round((item["unit_price_paisa"] * item["qty"] - item["discount_paisa"]) * (left / item["qty"]))),
                    int(round(item["line_profit_paisa"] * (left / item["qty"]))),
                    f"VOID: {reason}",
                    Session.user_id(),
                    now_iso(),
                ),
            )
        conn.execute(
            "UPDATE sales SET status = ?, due_paisa = 0, notes = ? WHERE id = ?",
            (STATUS_VOIDED, f"{sale['notes'] or ''} VOID: {reason}".strip(), sale_id),
        )
        audit_service.log("sale.void", "sales", sale_id, reason)


def delete_sale(sale_id: int) -> str:
    """Remove a sale for good. Tablets not already returned go back into their batch."""
    if not Session.is_owner():
        raise ValueError("Only the owner can delete a sale")
    with transaction() as conn:
        sale = conn.execute("SELECT * FROM sales WHERE id = ?", (sale_id,)).fetchone()
        if not sale:
            raise ValueError("Sale not found")
        label = sale["invoice_no"] or f"held #{sale_id}"
        if sale["status"] not in (STATUS_HELD, STATUS_VOIDED):
            for item in conn.execute("SELECT * FROM sale_items WHERE sale_id = ?", (sale_id,)).fetchall():
                back = conn.execute(
                    "SELECT COALESCE(SUM(qty),0) AS q FROM sale_returns WHERE sale_item_id = ?",
                    (item["id"],),
                ).fetchone()["q"]
                left = item["qty"] - back
                if left > 0:
                    stock_service.add_stock(conn, item["batch_id"], left, REF_SALE_RETURN, sale_id, f"Sale deleted {label}")
        conn.execute("DELETE FROM customer_payments WHERE sale_id = ? AND notes = 'Sale payment'", (sale_id,))
        conn.execute("UPDATE customer_payments SET sale_id = NULL WHERE sale_id = ?", (sale_id,))
        conn.execute("DELETE FROM sale_returns WHERE sale_id = ?", (sale_id,))
        conn.execute("DELETE FROM sale_items WHERE sale_id = ?", (sale_id,))
        conn.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
        audit_service.log("sale.delete", "sales", sale_id, label)
    return "deleted"
