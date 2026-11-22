from __future__ import annotations

from app.auth.session import Session
from app.db.database import get_db, row_to_dict, rows_to_dicts, transaction
from app.services import audit_service, settings_service
from app.utils.dates import now_iso


def list_customers(search: str = "", active_only: bool = False) -> list[dict]:
    like = f"%{search.strip()}%"
    sql = """
        SELECT c.*,
               COALESCE((SELECT SUM(due_paisa) FROM sales s WHERE s.customer_id = c.id AND s.status NOT IN ('held', 'voided')), 0) AS balance_paisa
        FROM customers c
        WHERE (? = '' OR c.name LIKE ? OR IFNULL(c.phone,'') LIKE ? OR IFNULL(c.cnic,'') LIKE ?)
    """
    params: list = [search.strip(), like, like, like]
    if active_only:
        sql += " AND c.active = 1"
    sql += " ORDER BY c.name"
    return rows_to_dicts(get_db().execute(sql, params).fetchall())


def get_customer(customer_id: int) -> dict | None:
    return row_to_dict(
        get_db().execute(
            """
            SELECT c.*,
                   COALESCE((SELECT SUM(due_paisa) FROM sales s WHERE s.customer_id = c.id AND s.status NOT IN ('held', 'voided')), 0) AS balance_paisa
            FROM customers c WHERE c.id = ?
            """,
            (customer_id,),
        ).fetchone()
    )


def save_customer(data: dict, customer_id: int | None = None) -> int:
    fields = (
        data["name"].strip(),
        (data.get("cnic") or "").strip(),
        (data.get("phone") or "").strip(),
        (data.get("address") or "").strip(),
        (data.get("notes") or "").strip(),
        1 if data.get("active", True) else 0,
    )
    with transaction() as conn:
        if customer_id:
            conn.execute(
                "UPDATE customers SET name=?, cnic=?, phone=?, address=?, notes=?, active=? WHERE id=?",
                (*fields, customer_id),
            )
            audit_service.log("customer.update", "customers", customer_id, data["name"])
            return customer_id
        cur = conn.execute(
            "INSERT INTO customers(name, cnic, phone, address, notes, active) VALUES (?, ?, ?, ?, ?, ?)",
            fields,
        )
        audit_service.log("customer.create", "customers", cur.lastrowid, data["name"])
        return cur.lastrowid


def delete_customer(customer_id: int) -> str:
    """Customers with udhaar cannot be removed. Customers with bills are archived, not erased."""
    cust = get_customer(customer_id)
    if not cust:
        raise ValueError("Customer not found")
    if cust["balance_paisa"] > 0:
        raise ValueError(
            f"{cust['name']} still owes Rs {cust['balance_paisa'] / 100:,.2f}. Record the udhaar payment first."
        )
    db = get_db()
    used = db.execute("SELECT COUNT(*) FROM sales WHERE customer_id = ?", (customer_id,)).fetchone()[0]
    used += db.execute("SELECT COUNT(*) FROM customer_payments WHERE customer_id = ?", (customer_id,)).fetchone()[0]
    with transaction() as conn:
        if used:
            conn.execute("UPDATE customers SET active = 0 WHERE id = ?", (customer_id,))
            audit_service.log("customer.archive", "customers", customer_id, cust["name"])
            return "archived"
        conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
        audit_service.log("customer.delete", "customers", customer_id, cust["name"])
        return "deleted"


def ledger(customer_id: int) -> list[dict]:
    sales = rows_to_dicts(
        get_db().execute(
            """
            SELECT id, invoice_no AS ref, date, ts, total_paisa AS debit, 0 AS credit,
                   'sale' AS kind, IFNULL(payment_method,'') AS notes
            FROM sales
            WHERE customer_id = ? AND status NOT IN ('held', 'voided')
            ORDER BY id
            """,
            (customer_id,),
        ).fetchall()
    )
    pays = rows_to_dicts(
        get_db().execute(
            """
            SELECT id, 'PAY' AS ref, substr(ts,1,10) AS date, ts, 0 AS debit, amount_paisa AS credit,
                   'payment' AS kind, notes
            FROM customer_payments
            WHERE customer_id = ?
            ORDER BY id
            """,
            (customer_id,),
        ).fetchall()
    )
    rets = rows_to_dicts(
        get_db().execute(
            """
            SELECT r.id, 'RET' AS ref, substr(r.ts,1,10) AS date, r.ts, 0 AS debit, r.amount_paisa AS credit,
                   'return' AS kind, r.reason AS notes
            FROM sale_returns r
            JOIN sales s ON s.id = r.sale_id
            WHERE s.customer_id = ?
            ORDER BY r.id
            """,
            (customer_id,),
        ).fetchall()
    )
    rows = sales + pays + rets
    rows.sort(key=lambda r: (r["ts"], r["kind"], r["id"]))
    bal = 0
    out = []
    for r in rows:
        bal += r["debit"] - r["credit"]
        item = dict(r)
        item["balance_paisa"] = max(0, bal)
        out.append(item)
    return out


def record_payment(customer_id: int, amount_paisa: int, method: str = "Cash", notes: str = "") -> None:
    if amount_paisa <= 0:
        raise ValueError("Amount must be positive")
    with transaction() as conn:
        remaining = amount_paisa
        dues = conn.execute(
            """
            SELECT id, due_paisa FROM sales
            WHERE customer_id = ? AND due_paisa > 0 AND status NOT IN ('held', 'voided')
            ORDER BY date, id
            """,
            (customer_id,),
        ).fetchall()
        applied_sale = None
        for sale in dues:
            if remaining <= 0:
                break
            take = min(remaining, sale["due_paisa"])
            conn.execute(
                "UPDATE sales SET due_paisa = due_paisa - ?, paid_paisa = paid_paisa + ? WHERE id = ?",
                (take, take, sale["id"]),
            )
            remaining -= take
            applied_sale = sale["id"]
        conn.execute(
            """
            INSERT INTO customer_payments(customer_id, sale_id, amount_paisa, method, notes, user_id, ts)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (customer_id, applied_sale, amount_paisa, method, notes, Session.user_id(), now_iso()),
        )
        audit_service.log("customer.payment", "customers", customer_id, str(amount_paisa))


def udhaar_list() -> list[dict]:
    return rows_to_dicts(
        get_db().execute(
            """
            SELECT c.id, c.name, c.phone, c.cnic,
                   COALESCE(SUM(s.due_paisa), 0) AS balance_paisa,
                   MIN(CASE WHEN s.due_paisa > 0 THEN s.date END) AS oldest_due
            FROM customers c
            JOIN sales s ON s.customer_id = c.id AND s.status NOT IN ('held', 'voided')
            GROUP BY c.id
            HAVING balance_paisa > 0
            ORDER BY balance_paisa DESC
            """
        ).fetchall()
    )


def overdue() -> list[dict]:
    days = settings_service.overdue_days()
    return rows_to_dicts(
        get_db().execute(
            """
            SELECT c.id, c.name, c.phone, s.invoice_no, s.date, s.due_paisa,
                   CAST(julianday('now') - julianday(s.date) AS INTEGER) AS days_over
            FROM sales s
            JOIN customers c ON c.id = s.customer_id
            WHERE s.due_paisa > 0 AND s.status NOT IN ('held', 'voided')
              AND s.date <= date('now', ?)
            ORDER BY s.date
            """,
            (f"-{days} days",),
        ).fetchall()
    )


def total_udhaar() -> int:
    row = get_db().execute(
        "SELECT COALESCE(SUM(due_paisa),0) AS t FROM sales WHERE status NOT IN ('held', 'voided')"
    ).fetchone()
    return row["t"]
