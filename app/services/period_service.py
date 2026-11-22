"""Month close / period rollover. Live sales stay; a snapshot is archived."""

from __future__ import annotations

from app.db.database import get_db, rows_to_dicts, transaction
from app.services import audit_service, stock_service
from app.utils.dates import month_end, month_start, now_iso, prev_month_range, today


def list_closes(limit: int = 24) -> list[dict]:
    return rows_to_dicts(
        get_db().execute(
            "SELECT * FROM period_closes ORDER BY period_key DESC LIMIT ?",
            (limit,),
        ).fetchall()
    )


def close_month(start: str, end: str, user_id: int | None = None) -> dict:
    key = start[:7]
    existing = get_db().execute("SELECT id FROM period_closes WHERE period_key = ?", (key,)).fetchone()
    if existing:
        return {"ok": True, "already": True, "period_key": key}
    from app.services.report_service import _sales_profit

    totals = _sales_profit(start, end)
    val = stock_service.valuation()
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO period_closes(
                period_key, period_kind, start_date, end_date, sale_paisa, profit_paisa,
                invoices, stock_cost_paisa, stock_sale_paisa, closed_at, user_id
            ) VALUES (?, 'month', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                start,
                end,
                totals["sale"],
                totals["profit"],
                totals["invoices"],
                val["cost"],
                val["sale"],
                now_iso(),
                user_id,
            ),
        )
        conn.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            ("last_closed_month", key),
        )
        audit_service.log("period.close", "period_closes", None, key)
    try:
        from app.services import backup_service

        backup_service.event_backup("month_close")
    except Exception:
        pass
    return {"ok": True, "already": False, "period_key": key, **totals}


def close_previous_month(user_id: int | None = None) -> dict:
    start, end = prev_month_range()
    return close_month(start, end, user_id)


def maybe_close_previous_month(user_id: int | None = None) -> dict | None:
    """At the start of a new month, archive last month and leave the current month open."""
    start, end = prev_month_range()
    if end >= today():
        return None
    key = start[:7]
    row = get_db().execute("SELECT id FROM period_closes WHERE period_key = ?", (key,)).fetchone()
    if row:
        return None
    return close_month(start, end, user_id)


def current_period() -> dict:
    start = month_start()
    end = today()
    from app.services.report_service import _sales_profit

    return {"period_key": start[:7], "end": month_end(start), **_sales_profit(start, end)}
