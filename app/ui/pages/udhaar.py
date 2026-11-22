from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QLineEdit, QPushButton, QTabWidget, QVBoxLayout, QWidget

from app.constants import PAYMENT_METHODS
from app.i18n import t
from app.services import customer_service
from app.ui.widgets.helpers import DataTable, SearchBar, error, form_dialog, info, money_spin
from app.utils.money import format_pkr, to_paisa


class UdhaarPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.bal_table = DataTable([t("name"), t("phone"), t("cnic"), t("balance"), t("date")])
        self.over_table = DataTable([t("name"), t("phone"), t("invoice"), t("date"), t("due"), t("overdue")])
        self.led_table = DataTable([t("date"), t("ref"), t("details"), "Debit", "Credit", t("balance")])

        bal_w = QWidget()
        bl = QVBoxLayout(bal_w)
        self.pay_btn = QPushButton(t("record_payment"))
        self.exp_btn = QPushButton(t("export_excel"))
        self.pay_btn.clicked.connect(self._pay)
        self.exp_btn.clicked.connect(self._export)
        self.search = SearchBar(lambda _: self.reload(), [self.pay_btn, self.exp_btn])
        bl.addWidget(self.search)
        bl.addWidget(self.bal_table)
        self.bal_table.itemSelectionChanged.connect(self._ledger)

        over_w = QWidget()
        ol = QVBoxLayout(over_w)
        ol.addWidget(self.over_table)

        led_w = QWidget()
        ll = QVBoxLayout(led_w)
        ll.addWidget(self.led_table)

        self.tabs.addTab(bal_w, t("udhaar"))
        self.tabs.addTab(over_w, t("overdue"))
        self.tabs.addTab(led_w, t("customer_ledger"))
        self.reload()

    def retranslate(self) -> None:
        self.pay_btn.setText(t("record_payment"))
        self.tabs.setTabText(0, t("udhaar"))
        self.tabs.setTabText(1, t("overdue"))
        self.tabs.setTabText(2, t("customer_ledger"))
        self.bal_table.set_headers([t("name"), t("phone"), t("cnic"), t("balance"), t("date")])
        self.over_table.set_headers([t("name"), t("phone"), t("invoice"), t("date"), t("due"), t("overdue")])
        self.led_table.set_headers([t("date"), t("ref"), t("details"), "Debit", "Credit", t("balance")])
        self.reload()

    def reload(self) -> None:
        q = self.search.edit.text().lower()
        rows = [r for r in customer_service.udhaar_list() if q in r["name"].lower()]
        self.bal_table.fill(
            [[r["name"], r["phone"], r["cnic"], r["balance_paisa"], r["oldest_due"]] for r in rows],
            [r["id"] for r in rows],
            money_cols={3},
        )
        over = customer_service.overdue()
        self.over_table.fill(
            [[r["name"], r["phone"], r["invoice_no"], r["date"], r["due_paisa"], r["days_over"]] for r in over],
            [r["id"] for r in over],
            money_cols={4},
        )

    def _ledger(self) -> None:
        cid = self.bal_table.selected_id()
        if not cid:
            return
        rows = customer_service.ledger(cid)
        self.led_table.fill(
            [[r["date"], r["ref"], r["kind"], r["debit"], r["credit"], r["balance_paisa"]] for r in rows],
            [r["id"] for r in rows],
            money_cols={3, 4, 5},
        )

    def _pay(self) -> None:
        cid = self.bal_table.selected_id()
        if not cid:
            error(self, t("select_row"))
            return
        amount = money_spin()
        method = QComboBox()
        method.addItems([m for m in PAYMENT_METHODS if m != "Credit"])
        notes = QLineEdit()
        dlg = form_dialog(self, t("record_payment"), [(t("amount"), amount), (t("method"), method), (t("notes"), notes)])
        if dlg.exec():
            try:
                customer_service.record_payment(cid, to_paisa(amount.value()), method.currentText(), notes.text())
                info(self, t("success"))
                self.reload()
                self._ledger()
            except Exception as exc:
                error(self, exc)

    def _export(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        from app.services import report_service

        path, _ = QFileDialog.getSaveFileName(self, t("export_excel"), "udhaar.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        rows = customer_service.udhaar_list()
        report_service.export_excel(
            path,
            "Who owes money",
            [
                ("name", t("name")),
                ("phone", t("phone")),
                ("balance_paisa", t("balance")),
                ("oldest_due", t("date")),
            ],
            rows,
        )
        info(self, t("success"))
