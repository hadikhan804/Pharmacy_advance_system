from __future__ import annotations

from app.config import EXPIRY_ALERT_DAYS
from app.db.database import get_db
from app.services import customer_service, stock_service, supplier_service
from app.utils.dates import month_start, today, week_start, year_start


def period_totals(start: str, end: str) -> dict:
    sale = get_db().execute(
        """
        SELECT COALESCE(SUM(total_paisa),0) AS sale
        FROM sales WHERE status NOT IN ('held', 'voided') AND date >= ? AND date <= ?
        """,
        (start, end),
    ).fetchone()["sale"]
    profit = get_db().execute(
        """
        SELECT COALESCE(SUM(si.line_profit_paisa),0) AS p
        FROM sale_items si
        JOIN sales s ON s.id = si.sale_id
        WHERE s.status NOT IN ('held', 'voided') AND s.date >= ? AND s.date <= ?
        """,
        (start, end),
    ).fetchone()["p"]
    ret = get_db().execute(
        """
        SELECT COALESCE(SUM(sr.profit_reversal_paisa),0) AS r, COALESCE(SUM(sr.amount_paisa),0) AS a
        FROM sale_returns sr
        JOIN sales s ON s.id = sr.sale_id
        WHERE s.status NOT IN ('held', 'voided') AND s.date >= ? AND s.date <= ?
        """,
        (start, end),
    ).fetchone()
    return {"sale": max(0, (sale or 0) - (ret["a"] or 0)), "profit": (profit or 0) - (ret["r"] or 0)}


def summary() -> dict:
    t = today()
    val = stock_service.valuation()
    low = stock_service.low_stock()
    exp = stock_service.expiring_within(EXPIRY_ALERT_DAYS)
    out = {
        "today": period_totals(t, t),
        "week": period_totals(week_start(), t),
        "month": period_totals(month_start(), t),
        "year": period_totals(year_start(), t),
        "stock_cost": val["cost"],
        "stock_sale": val["sale"],
        "expiring_soon": len(exp),
        "low_stock": len(low),
        "udhaar": customer_service.total_udhaar(),
        "payables": supplier_service.total_payables(),
        "backup": {"last_verified": "", "warning": True, "stale": True, "pending_secondary": False},
    }
    try:
        from app.services import backup_service

        out["backup"] = backup_service.status()
    except Exception:
        pass
    return out
