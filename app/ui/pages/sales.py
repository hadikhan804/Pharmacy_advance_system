from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.i18n import t
from app.printing.receipt import print_sale, show_bill
from app.services import sale_service
from app.ui.widgets.helpers import DataTable, SearchBar, error, info
from app.utils.money import format_pkr


class SalesPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.view_btn = QPushButton(t("view_bill"))
        self.view_btn.setObjectName("GoldBtn")
        self.ret_btn = QPushButton(t("sale_return"))
        self.void_btn = QPushButton(t("void_sale"))
        self.p80 = QPushButton(t("print_80"))
        self.pa4 = QPushButton(t("print_a4"))
        self.view_btn.clicked.connect(self._view)
        self.ret_btn.clicked.connect(self._return)
        self.void_btn.clicked.connect(self._void)
        self.p80.clicked.connect(lambda: self._print(True))
        self.pa4.clicked.connect(lambda: self._print(False))
        self.search = SearchBar(lambda _: self.reload(), [self.view_btn, self.ret_btn, self.void_btn, self.p80, self.pa4])
        layout.addWidget(self.search)
        self.table = DataTable(
            [t("invoice"), t("date"), t("customer"), t("total"), t("due"), t("profit"), t("payment"), t("status"), t("user")]
        )
        self.table.doubleClicked.connect(lambda _: self._view())
        layout.addWidget(self.table)
        self.reload()

    def retranslate(self) -> None:
        self.view_btn.setText(t("view_bill"))
        self.ret_btn.setText(t("sale_return"))
        self.void_btn.setText(t("void_sale"))
        self.p80.setText(t("print_80"))
        self.pa4.setText(t("print_a4"))
        self.search.edit.setPlaceholderText(t("search"))
        self.table.set_headers(
            [t("invoice"), t("date"), t("customer"), t("total"), t("due"), t("profit"), t("payment"), t("status"), t("user")]
        )
        self.reload()

    def reload(self) -> None:
        rows = [r for r in sale_service.list_sales(self.search.edit.text()) if r["status"] != "held"]
        self.table.fill(
            [
                [
                    r["invoice_no"],
                    r["date"],
                    r["customer_name"],
                    r["total_paisa"],
                    r["due_paisa"],
                    r["profit_paisa"],
                    r["payment_method"],
                    r["status"],
                    r["username"],
                ]
                for r in rows
            ],
            [r["id"] for r in rows],
            money_cols={3, 4, 5},
        )

    def _selected_sale(self):
        sid = self.table.selected_id()
        if not sid:
            error(self, t("select_row"))
            return None
        return sale_service.get_sale(sid)

    def _view(self) -> None:
        sale = self._selected_sale()
        if sale:
            show_bill(sale, parent=self, print_now=False)

    def _print(self, thermal: bool) -> None:
        sale = self._selected_sale()
        if sale:
            print_sale(sale, thermal=thermal, parent=self)

    def _return(self) -> None:
        sid = self.table.selected_id()
        if not sid:
            error(self, t("select_row"))
            return
        sale = sale_service.get_sale(sid)
        dlg = QDialog(self)
        dlg.setWindowTitle(t("sale_return"))
        dlg.resize(700, 420)
        box = QVBoxLayout(dlg)
        table = DataTable([t("brand"), t("batch"), t("qty")])
        from PySide6.QtWidgets import QTableWidgetItem

        spins = []
        table.setRowCount(len(sale["items"]))
        for i, item in enumerate(sale["items"]):
            already = sum(r["qty"] for r in sale["returns"] if r["sale_item_id"] == item["id"])
            left = item["qty"] - already
            table.setItem(i, 0, QTableWidgetItem(item["brand_name"]))
            table.setItem(i, 1, QTableWidgetItem(item["batch_no"]))
            spin = QSpinBox()
            spin.setRange(0, max(0, left))
            table.setCellWidget(i, 2, spin)
            spins.append((item["id"], spin))
        reason = QLineEdit()
        box.addWidget(table)
        form = QFormLayout()
        form.addRow(t("reason"), reason)
        box.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        box.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec():
            if not reason.text().strip():
                error(self, t("required"))
                return
            lines = [{"sale_item_id": iid, "qty": sp.value()} for iid, sp in spins if sp.value() > 0]
            try:
                sale_service.return_sale(sid, lines, reason.text())
                info(self, t("success"))
                self.reload()
            except Exception as exc:
                error(self, exc)

    def _void(self) -> None:
        sid = self.table.selected_id()
        if not sid:
            error(self, t("select_row"))
            return
        reason = QLineEdit()
        from app.ui.widgets.helpers import form_dialog

        dlg = form_dialog(self, t("void_sale"), [(t("reason"), reason)])
        if dlg.exec():
            try:
                sale_service.void_sale(sid, reason.text())
                info(self, t("success"))
                self.reload()
            except Exception as exc:
                error(self, exc)
