"""Headless check that stock re-edit and month UI actually exist."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.db.database import init_db
from app.i18n import i18n, t
from app.services import period_service, stock_service
from app.ui.pages.dashboard import DashboardPage
from app.ui.pages.pos import PosPage
from app.ui.pages.reports import ReportsPage
from app.ui.pages.stock import StockPage


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    init_db()
    i18n.load("en")
    failures = []

    stock = StockPage()
    if not stock.reedit_stock_btn.isVisibleTo(stock):
        failures.append("Stock Re-edit button is not on the current-stock tab")
    if stock.reedit_stock_btn.text() != t("reedit"):
        failures.append(f"Stock Re-edit label is {stock.reedit_stock_btn.text()!r}")
    if stock.tabs.tabText(0) != t("current_stock"):
        failures.append("First stock tab is not Current stock")

    reports = ReportsPage()
    for name in ("week_btn", "month_btn", "year_btn", "close_btn", "closed_btn"):
        if not hasattr(reports, name):
            failures.append(f"Reports missing {name}")
    if reports.close_btn.text() != t("close_month"):
        failures.append(f"Close month button is {reports.close_btn.text()!r}")
    if reports.kind.currentData() != "profit_monthly":
        failures.append(f"Reports default is {reports.kind.currentData()!r}, not monthly")

    dash = DashboardPage(lambda *_args, **_kw: None)
    if not hasattr(dash, "close_btn"):
        failures.append("Dashboard has no Close last month button")
    if dash.close_btn.text() != t("close_month"):
        failures.append(f"Dashboard close button is {dash.close_btn.text()!r}")
    if "2026-09" not in dash.period_lab.text() and "Current month" not in dash.period_lab.text():
        failures.append(f"Dashboard period label empty: {dash.period_lab.text()!r}")

    pos = PosPage()
    if pos.print_pay_btn.text() != t("print_bill"):
        failures.append(f"POS print button is {pos.print_pay_btn.text()!r}")
    if pos.month_btn.text() != t("new_month"):
        failures.append(f"POS new month button is {pos.month_btn.text()!r}")
    headers = [pos.table.horizontalHeaderItem(i).text() for i in range(pos.table.columnCount())]
    if t("rack") not in headers:
        failures.append(f"POS cart has no Rack column: {headers}")

    cur = period_service.current_period()
    if "period_key" not in cur:
        failures.append("current_period() has no period_key")
    closed = period_service.close_previous_month()
    if not closed.get("ok"):
        failures.append(f"close_previous_month failed: {closed}")

    if not callable(stock_service.edit_batch):
        failures.append("edit_batch is missing")

    if failures:
        print("FAIL")
        for item in failures:
            print(" -", item)
        raise SystemExit(1)
    print("OK stock re-edit button, month bar, close month, POS print/hold labels")
    print("current month", cur["period_key"], "last close", closed.get("period_key"), "already", closed.get("already"))
    app.quit()


if __name__ == "__main__":
    main()
