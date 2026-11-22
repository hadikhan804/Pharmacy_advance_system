from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QLineEdit, QPushButton, QTabWidget, QVBoxLayout, QWidget

from app.constants import PAYMENT_METHODS
from app.i18n import t
from app.services import supplier_service
from app.ui.widgets.helpers import DataTable, error, form_dialog, info, money_spin
from app.utils.money import to_paisa


class PayablesPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.table = DataTable([t("company"), t("phone"), t("total_payables")])
        self.hist = DataTable([t("date"), t("invoice"), t("total"), t("paid"), t("due"), t("status")])
        self.led = DataTable([t("date"), t("ref"), t("details"), "Debit", "Credit", t("balance")])
        self.pay_btn = QPushButton(t("record_payment"))
        self.pay_btn.clicked.connect(self._pay)
        w1 = QWidget()
        l1 = QVBoxLayout(w1)
        l1.addWidget(self.pay_btn)
        l1.addWidget(self.table)
        self.table.itemSelectionChanged.connect(self._details)
        w2 = QWidget()
        l2 = QVBoxLayout(w2)
        l2.addWidget(self.hist)
        w3 = QWidget()
        l3 = QVBoxLayout(w3)
        l3.addWidget(self.led)
        self.tabs.addTab(w1, t("payables"))
        self.tabs.addTab(w2, t("purchases"))
        self.tabs.addTab(w3, t("company_ledger"))
        self.reload()

    def retranslate(self) -> None:
        self.pay_btn.setText(t("record_payment"))
        self.tabs.setTabText(0, t("payables"))
        self.tabs.setTabText(1, t("purchases"))
        self.tabs.setTabText(2, t("company_ledger"))
        self.table.set_headers([t("company"), t("phone"), t("total_payables")])
        self.hist.set_headers([t("date"), t("invoice"), t("total"), t("paid"), t("due"), t("status")])
        self.led.set_headers([t("date"), t("ref"), t("details"), "Debit", "Credit", t("balance")])
        self.reload()

    def reload(self) -> None:
        rows = supplier_service.payables()
        self.table.fill(
            [[r["name"], r["phone"], r["payable_paisa"]] for r in rows],
            [r["id"] for r in rows],
            money_cols={2},
        )

    def _details(self) -> None:
        sid = self.table.selected_id()
        if not sid:
            return
        hist = supplier_service.purchase_history(sid)
        self.hist.fill(
            [[r["date"], r["invoice_no"], r["total_paisa"], r["paid_paisa"], r["due_paisa"], r["status"]] for r in hist],
            [r["id"] for r in hist],
            money_cols={2, 3, 4},
        )
        led = supplier_service.ledger(sid)
        self.led.fill(
            [[r["date"], r["ref"], r["kind"], r["debit"], r["credit"], r["balance_paisa"]] for r in led],
            [r["id"] for r in led],
            money_cols={3, 4, 5},
        )

    def _pay(self) -> None:
        sid = self.table.selected_id()
        if not sid:
            error(self, t("select_row"))
            return
        amount = money_spin()
        method = QComboBox()
        method.addItems([m for m in PAYMENT_METHODS if m != "Credit"])
        notes = QLineEdit()
        dlg = form_dialog(self, t("record_payment"), [(t("amount"), amount), (t("method"), method), (t("notes"), notes)])
        if dlg.exec():
            try:
                supplier_service.record_payment(sid, to_paisa(amount.value()), method.currentText(), notes.text())
                info(self, t("success"))
                self.reload()
                self._details()
            except Exception as exc:
                error(self, exc)
