from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

from app.db.database import get_db, rows_to_dicts
from app.services import customer_service, stock_service, supplier_service
from app.utils.dates import month_start, prev_month_range, prev_year_range, today, week_start, year_start
from app.utils.money import from_paisa


def _sales_profit(start: str, end: str) -> dict:
    from app.services.dashboard_service import period_totals

    totals = period_totals(start, end)
    row = get_db().execute(
        """
        SELECT COALESCE(SUM(discount_paisa),0) AS discount,
               COALESCE(SUM(gst_paisa),0) AS gst,
               COUNT(id) AS invoices
        FROM sales WHERE status NOT IN ('held', 'voided') AND date >= ? AND date <= ?
        """,
        (start, end),
    ).fetchone()
    return {
        "sale": totals["sale"],
        "profit": totals["profit"],
        "discount": row["discount"] or 0,
        "gst": row["gst"] or 0,
        "invoices": row["invoices"] or 0,
        "start": start,
        "end": end,
    }


def daily_summary(day: str | None = None) -> dict:
    d = day or today()
    return _sales_profit(d, d)


def date_range(start: str, end: str) -> dict:
    header = _sales_profit(start, end)
    header["rows"] = rows_to_dicts(
        get_db().execute(
            """
            SELECT s.date, s.invoice_no, s.total_paisa, s.payment_method, s.discount_paisa,
                   c.name AS customer_name, u.username,
                   COALESCE((SELECT SUM(line_profit_paisa) FROM sale_items WHERE sale_id = s.id),0)
                     - COALESCE((SELECT SUM(profit_reversal_paisa) FROM sale_returns WHERE sale_id = s.id),0)
                     AS profit_paisa
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            LEFT JOIN users u ON u.id = s.user_id
            WHERE s.status NOT IN ('held', 'voided') AND s.date >= ? AND s.date <= ?
            ORDER BY s.date, s.id
            """,
            (start, end),
        ).fetchall()
    )
    return header


def profit_period(kind: str) -> dict:
    t = today()
    if kind == "daily":
        return _sales_profit(t, t)
    if kind == "weekly":
        return _sales_profit(week_start(), t)
    if kind == "monthly":
        return _sales_profit(month_start(), t)
    if kind == "yearly":
        return _sales_profit(year_start(), t)
    return _sales_profit(t, t)


def comparison() -> dict:
    t = today()
    this_month = _sales_profit(month_start(), t)
    pms, pme = prev_month_range()
    last_month = _sales_profit(pms, pme)
    this_year = _sales_profit(year_start(), t)
    pys, pye = prev_year_range()
    last_year = _sales_profit(pys, pye)
    return {
        "this_month": this_month,
        "last_month": last_month,
        "this_year": this_year,
        "last_year": last_year,
    }


def top_medicines(start: str, end: str, limit: int = 20) -> list[dict]:
    return rows_to_dicts(
        get_db().execute(
            """
            SELECT m.id, m.brand_name, m.generic_name, c.name AS company_name,
                   SUM(si.qty) - COALESCE((
                       SELECT SUM(sr.qty) FROM sale_returns sr
                       JOIN sales sx ON sx.id = sr.sale_id
                       WHERE sr.medicine_id = m.id AND sx.date >= ? AND sx.date <= ?
                   ), 0) AS qty,
                   SUM(si.qty * si.unit_price_paisa - si.discount_paisa) AS sale_paisa,
                   SUM(si.line_profit_paisa) AS profit_paisa
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            JOIN medicines m ON m.id = si.medicine_id
            LEFT JOIN companies c ON c.id = m.company_id
            WHERE s.status NOT IN ('held', 'voided') AND s.date >= ? AND s.date <= ?
            GROUP BY m.id
            ORDER BY qty DESC
            LIMIT ?
            """,
            (start, end, start, end, limit),
        ).fetchall()
    )


def top_customers(start: str, end: str, limit: int = 20) -> list[dict]:
    return rows_to_dicts(
        get_db().execute(
            """
            SELECT c.id, c.name, c.phone, COUNT(s.id) AS invoices, SUM(s.total_paisa) AS sale_paisa
            FROM sales s
            JOIN customers c ON c.id = s.customer_id
            WHERE s.status NOT IN ('held', 'voided') AND s.date >= ? AND s.date <= ?
            GROUP BY c.id
            ORDER BY sale_paisa DESC
            LIMIT ?
            """,
            (start, end, limit),
        ).fetchall()
    )


def sales_by_company(start: str, end: str) -> list[dict]:
    return rows_to_dicts(
        get_db().execute(
            """
            SELECT IFNULL(c.name, 'Unknown') AS name,
                   SUM(si.qty) AS qty,
                   SUM(si.qty * si.unit_price_paisa - si.discount_paisa) AS sale_paisa,
                   SUM(si.line_profit_paisa) AS profit_paisa
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            JOIN medicines m ON m.id = si.medicine_id
            LEFT JOIN companies c ON c.id = m.company_id
            WHERE s.status NOT IN ('held', 'voided') AND s.date >= ? AND s.date <= ?
            GROUP BY c.id
            ORDER BY sale_paisa DESC
            """,
            (start, end),
        ).fetchall()
    )


def sales_by_formulation(start: str, end: str) -> list[dict]:
    return rows_to_dicts(
        get_db().execute(
            """
            SELECT IFNULL(f.name, 'Unknown') AS name,
                   SUM(si.qty) AS qty,
                   SUM(si.qty * si.unit_price_paisa - si.discount_paisa) AS sale_paisa,
                   SUM(si.line_profit_paisa) AS profit_paisa
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            JOIN medicines m ON m.id = si.medicine_id
            LEFT JOIN formulations f ON f.id = m.formulation_id
            WHERE s.status NOT IN ('held', 'voided') AND s.date >= ? AND s.date <= ?
            GROUP BY f.id
            ORDER BY sale_paisa DESC
            """,
            (start, end),
        ).fetchall()
    )


def purchases(start: str, end: str) -> list[dict]:
    return rows_to_dicts(
        get_db().execute(
            """
            SELECT p.*, s.name AS supplier_name,
                   (p.total_paisa - p.returned_paisa - p.paid_paisa) AS due_paisa
            FROM purchases p
            JOIN suppliers s ON s.id = p.supplier_id
            WHERE p.date >= ? AND p.date <= ?
            ORDER BY p.date, p.id
            """,
            (start, end),
        ).fetchall()
    )


def profit_by_medicine(start: str, end: str) -> list[dict]:
    return top_medicines(start, end, limit=200)


def export_excel(path: str | Path, title: str, columns: list[tuple[str, str]], rows: list[dict]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31] or "Report"
    header_font = Font(bold=True, color="FFFFFF")
    fill = PatternFill("solid", fgColor="7E22CE")
    thin = Border(
        left=Side(style="thin", color="D1D5DB"),
        right=Side(style="thin", color="D1D5DB"),
        top=Side(style="thin", color="D1D5DB"),
        bottom=Side(style="thin", color="D1D5DB"),
    )
    ws["A1"] = title
    ws["A1"].font = Font(bold=True, size=14)
    for col, (key, label) in enumerate(columns, 1):
        cell = ws.cell(3, col, label)
        cell.font = header_font
        cell.fill = fill
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin
    money_keys = {k for k, _ in columns if "paisa" in k or k in ("sale", "profit", "discount", "gst", "cost", "value_cost", "value_sale")}
    for r_i, row in enumerate(rows, 4):
        for c_i, (key, _) in enumerate(columns, 1):
            val = row.get(key, "")
            if key in money_keys and isinstance(val, (int, float)):
                val = from_paisa(int(val))
            cell = ws.cell(r_i, c_i, val)
            cell.border = thin
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 18
    wb.save(str(path))
