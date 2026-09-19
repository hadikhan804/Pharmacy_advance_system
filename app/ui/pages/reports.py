from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import t
from app.printing.receipt import print_html, report_html
from app.services import customer_service, report_service, stock_service, supplier_service
from app.ui.widgets.helpers import DataTable, error, info
from app.utils.dates import month_start, today, year_start
from app.utils.money import format_pkr


REPORTS = [
    "daily_sales",
    "range_sales",
    "profit_daily",
    "profit_weekly",
    "profit_monthly",
    "profit_yearly",
    "top_medicines",
    "top_customers",
    "expiry_report",
    "low_stock_report",
    "valuation",
    "udhaar_report",
    "payables_report",
    "by_company",
    "by_formulation",
    "purchase_report",
    "comparison",
]


class ReportsPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.kind = QComboBox()
        for key in REPORTS:
            self.kind.addItem(t(key), key)
        self.start = QDateEdit()
        self.start.setCalendarPopup(True)
        self.start.setDate(QDate.fromString(month_start(), "yyyy-MM-dd"))
        self.end = QDateEdit()
        self.end.setCalendarPopup(True)
        self.end.setDate(QDate.currentDate())
        self.gen = QPushButton(t("generate"))
        self.gen.setObjectName("GoldBtn")
        self.xlsx = QPushButton(t("export_excel"))
        self.pdf = QPushButton(t("export_pdf"))
        self.gen.clicked.connect(self.reload)
        self.xlsx.clicked.connect(self._excel)
        self.pdf.clicked.connect(self._pdf)
        for w in (QLabel(t("report_type")), self.kind, QLabel(t("from")), self.start, QLabel(t("to")), self.end, self.gen, self.xlsx, self.pdf):
            bar.addWidget(w)
        layout.addLayout(bar)
        self.summary = QLabel()
        layout.addWidget(self.summary)
        self.table = DataTable([t("details")])
        layout.addWidget(self.table)
        self._rows: list[dict] = []
        self._cols: list[tuple[str, str]] = []
        self.reload()

    def retranslate(self) -> None:
        current = self.kind.currentData()
        self.kind.clear()
        for key in REPORTS:
            self.kind.addItem(t(key), key)
        idx = self.kind.findData(current)
        if idx >= 0:
            self.kind.setCurrentIndex(idx)
        self.gen.setText(t("generate"))
        self.xlsx.setText(t("export_excel"))
        self.pdf.setText(t("export_pdf"))
        self.reload()

    def _range(self) -> tuple[str, str]:
        return self.start.date().toString("yyyy-MM-dd"), self.end.date().toString("yyyy-MM-dd")

    def reload(self) -> None:
        kind = self.kind.currentData() or "daily_sales"
        start, end = self._range()
        cols: list[tuple[str, str]] = []
        rows: list[dict] = []
        summary = ""
        try:
            if kind == "daily_sales":
                d = report_service.daily_summary(end)
                summary = f"{t('total')}: {format_pkr(d['sale'])}  {t('profit')}: {format_pkr(d['profit'])}  {t('invoices')}: {d['invoices']}"
                data = report_service.date_range(end, end)
                cols = [("invoice_no", t("invoice")), ("customer_name", t("customer")), ("total_paisa", t("total")), ("profit_paisa", t("profit"))]
                rows = data["rows"]
            elif kind == "range_sales":
                data = report_service.date_range(start, end)
                summary = f"{t('total')}: {format_pkr(data['sale'])}  {t('profit')}: {format_pkr(data['profit'])}"
                cols = [("date", t("date")), ("invoice_no", t("invoice")), ("customer_name", t("customer")), ("total_paisa", t("total")), ("profit_paisa", t("profit"))]
                rows = data["rows"]
            elif kind in ("profit_daily", "profit_weekly", "profit_monthly", "profit_yearly"):
                key = kind.split("_")[1]
                d = report_service.profit_period(key)
                summary = f"{t('total')}: {format_pkr(d['sale'])}  {t('profit')}: {format_pkr(d['profit'])}  {d['start']} → {d['end']}"
                cols = [("start", t("from")), ("end", t("to")), ("sale", t("total")), ("profit", t("profit"))]
                rows = [d]
            elif kind == "top_medicines":
                rows = report_service.top_medicines(start, end)
                cols = [("brand_name", t("brand")), ("qty", t("qty")), ("sale_paisa", t("total")), ("profit_paisa", t("profit"))]
            elif kind == "top_customers":
                rows = report_service.top_customers(start, end)
                cols = [("name", t("name")), ("invoices", t("invoices")), ("sale_paisa", t("total"))]
            elif kind == "expiry_report":
                rows = stock_service.expiring_within(90)
                cols = [("brand_name", t("brand")), ("batch_no", t("batch")), ("expiry", t("expiry_date")), ("qty", t("qty")), ("days_left", t("days_left"))]
            elif kind == "low_stock_report":
                rows = stock_service.low_stock()
                cols = [("brand_name", t("brand")), ("qty", t("qty")), ("reorder_level", t("reorder_level"))]
            elif kind == "valuation":
                rows = stock_service.current_stock()
                cols = [("brand_name", t("brand")), ("qty", t("qty")), ("value_cost", t("value_cost")), ("value_sale", t("value_sale"))]
            elif kind == "udhaar_report":
                rows = customer_service.udhaar_list()
                cols = [("name", t("name")), ("phone", t("phone")), ("balance_paisa", t("balance"))]
            elif kind == "payables_report":
                rows = supplier_service.payables()
                cols = [("name", t("name")), ("phone", t("phone")), ("payable_paisa", t("total_payables"))]
            elif kind == "by_company":
                rows = report_service.sales_by_company(start, end)
                cols = [("name", t("company")), ("qty", t("qty")), ("sale_paisa", t("total")), ("profit_paisa", t("profit"))]
            elif kind == "by_formulation":
                rows = report_service.sales_by_formulation(start, end)
                cols = [("name", t("formulation")), ("qty", t("qty")), ("sale_paisa", t("total")), ("profit_paisa", t("profit"))]
            elif kind == "purchase_report":
                rows = report_service.purchases(start, end)
                cols = [("date", t("date")), ("invoice_no", t("invoice")), ("supplier_name", t("supplier")), ("total_paisa", t("total")), ("status", t("status"))]
            elif kind == "comparison":
                c = report_service.comparison()
                rows = [
                    {"name": t("this_month"), "sale": c["this_month"]["sale"], "profit": c["this_month"]["profit"]},
                    {"name": t("last_month"), "sale": c["last_month"]["sale"], "profit": c["last_month"]["profit"]},
                    {"name": t("this_year"), "sale": c["this_year"]["sale"], "profit": c["this_year"]["profit"]},
                    {"name": t("last_year"), "sale": c["last_year"]["sale"], "profit": c["last_year"]["profit"]},
                ]
                cols = [("name", t("comparison")), ("sale", t("total")), ("profit", t("profit"))]
        except Exception as exc:
            error(self, exc)
            return
        self._cols = cols
        self._rows = rows
        self.summary.setText(summary)
        money = {i for i, (k, _) in enumerate(cols) if "paisa" in k or k in ("sale", "profit", "value_cost", "value_sale")}
        self.table.set_headers([label for _, label in cols])
        self.table.fill([[r.get(k, "") for k, _ in cols] for r in rows], None, money_cols=money)

    def _excel(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, t("export_excel"), "", "Excel (*.xlsx)")
        if not path:
            return
        try:
            report_service.export_excel(path, self.kind.currentText(), self._cols, self._rows)
            info(self, t("success"))
        except Exception as exc:
            error(self, exc)

    def _pdf(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, t("export_pdf"), "", "PDF (*.pdf)")
        if not path:
            return
        money = {i for i, (k, _) in enumerate(self._cols) if "paisa" in k or k in ("sale", "profit", "value_cost", "value_sale")}
        html_rows = []
        for r in self._rows:
            line = []
            for i, (k, _) in enumerate(self._cols):
                val = r.get(k, "")
                if i in money and isinstance(val, (int, float)):
                    val = format_pkr(int(val))
                line.append(str(val))
            html_rows.append(line)
        html = report_html(self.kind.currentText(), [c[1] for c in self._cols], html_rows, self.summary.text())
        print_html(html, pdf_path=path, parent=self)
        info(self, t("success"))
