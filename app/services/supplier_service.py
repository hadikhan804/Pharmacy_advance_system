"""Money owed to companies. The company is the supplier; a hidden suppliers row links old purchases to it."""
from __future__ import annotations

from app.auth.session import Session
from app.db.database import get_db, rows_to_dicts, transaction
from app.services import audit_service, purchase_service
from app.utils.dates import now_iso

_COMPANY_SUPPLIERS = "SELECT id FROM suppliers WHERE company_id = ?"


def supplier_for_company(company_id: int, conn=None) -> int:
    """Hidden supplier row for a company (created on first purchase)."""
    db = conn or get_db()
    row = db.execute("SELECT id FROM suppliers WHERE company_id = ? ORDER BY id LIMIT 1", (company_id,)).fetchone()
    if row:
        return int(row["id"])
    comp = db.execute("SELECT name, phone, address FROM companies WHERE id = ?", (company_id,)).fetchone()
    if not comp:
        raise ValueError("Company not found")
    cur = db.execute(
        "INSERT INTO suppliers(name, phone, address, notes, active, company_id) VALUES (?, ?, ?, '', 1, ?)",
        (comp["name"], comp["phone"] or "", comp["address"] or "", company_id),
    )
    if conn is None:
        db.commit()
    return int(cur.lastrowid)


def sync_company(conn, company_id: int, name: str, phone: str = "", address: str = "") -> None:
    conn.execute(
        "UPDATE suppliers SET name = ?, phone = ?, address = ? WHERE company_id = ?",
        (name.strip(), phone.strip(), address.strip(), company_id),
    )


def company_payable(company_id: int) -> int:
    row = get_db().execute(
        f"""
        SELECT COALESCE(SUM(total_paisa - returned_paisa - paid_paisa), 0) AS due
        FROM purchases WHERE supplier_id IN ({_COMPANY_SUPPLIERS})
        """,
        (company_id,),
    ).fetchone()
    return int(row["due"])


def purchase_history(company_id: int) -> list[dict]:
    return rows_to_dicts(
        get_db().execute(
            f"""
            SELECT p.*, (p.total_paisa - p.returned_paisa - p.paid_paisa) AS due_paisa
            FROM purchases p WHERE p.supplier_id IN ({_COMPANY_SUPPLIERS}) ORDER BY p.id DESC
            """,
            (company_id,),
        ).fetchall()
    )


def ledger(company_id: int) -> list[dict]:
    db = get_db()
    purchases = rows_to_dicts(
        db.execute(
            f"""
            SELECT id, IFNULL(invoice_no,'PO') AS ref, date, ts, total_paisa AS debit, 0 AS credit,
                   'purchase' AS kind, notes
            FROM purchases WHERE supplier_id IN ({_COMPANY_SUPPLIERS})
            """,
            (company_id,),
        ).fetchall()
    )
    pays = rows_to_dicts(
        db.execute(
            f"""
            SELECT id, 'PAY' AS ref, substr(ts,1,10) AS date, ts, 0 AS debit, amount_paisa AS credit,
                   'payment' AS kind, notes
            FROM supplier_payments WHERE supplier_id IN ({_COMPANY_SUPPLIERS})
            """,
            (company_id,),
        ).fetchall()
    )
    ppays = rows_to_dicts(
        db.execute(
            f"""
            SELECT pp.id, 'PAY' AS ref, substr(pp.ts,1,10) AS date, pp.ts, 0 AS debit, pp.amount_paisa AS credit,
                   'payment' AS kind, pp.notes
            FROM purchase_payments pp
            JOIN purchases p ON p.id = pp.purchase_id
            WHERE p.supplier_id IN ({_COMPANY_SUPPLIERS})
            """,
            (company_id,),
        ).fetchall()
    )
    rets = rows_to_dicts(
        db.execute(
            f"""
            SELECT r.id, 'RET' AS ref, substr(r.ts,1,10) AS date, r.ts, 0 AS debit, r.amount_paisa AS credit,
                   'return' AS kind, r.reason AS notes
            FROM purchase_returns r
            JOIN purchases p ON p.id = r.purchase_id
            WHERE p.supplier_id IN ({_COMPANY_SUPPLIERS})
            """,
            (company_id,),
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


def record_payment(company_id: int, amount_paisa: int, method: str = "Cash", notes: str = "") -> None:
    if amount_paisa <= 0:
        raise ValueError("Amount must be positive")
    due = company_payable(company_id)
    if amount_paisa > due:
        raise ValueError(f"Payment is more than the amount owed (Rs {due / 100:,.2f})")
    remaining = amount_paisa
    with transaction() as conn:
        dues = conn.execute(
            f"""
            SELECT id, (total_paisa - returned_paisa - paid_paisa) AS due
            FROM purchases
            WHERE supplier_id IN ({_COMPANY_SUPPLIERS}) AND (total_paisa - returned_paisa - paid_paisa) > 0
            ORDER BY date, id
            """,
            (company_id,),
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
            (supplier_for_company(company_id, conn), applied, amount_paisa, method, notes, Session.user_id(), now_iso()),
        )
        audit_service.log("company.payment", "companies", company_id, str(amount_paisa))


def payables() -> list[dict]:
    return rows_to_dicts(
        get_db().execute(
            """
            SELECT c.id, c.name, c.phone,
                   COALESCE(SUM(p.total_paisa - p.returned_paisa - p.paid_paisa), 0) AS payable_paisa
            FROM companies c
            JOIN suppliers s ON s.company_id = c.id
            JOIN purchases p ON p.supplier_id = s.id
            GROUP BY c.id
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
