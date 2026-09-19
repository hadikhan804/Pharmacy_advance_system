from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.i18n import t
from app.services import stock_service
from app.ui.widgets.helpers import DataTable, SearchBar, ask, error, info
from app.utils.money import format_pkr


class StockPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.stock_table = DataTable(
            [t("brand"), t("generic"), t("company"), t("qty"), t("reorder_level"), t("value_cost"), t("value_sale")]
        )
        self.batch_table = DataTable(
            [t("brand"), t("batch"), t("expiry_date"), t("qty"), t("cost"), t("sale_price"), t("expired")]
        )
        self.ledger_table = DataTable(
            [t("time"), t("brand"), t("batch"), t("direction"), t("qty"), t("ref"), t("user"), t("notes")]
        )

        stock_w = QWidget()
        sl = QVBoxLayout(stock_w)
        self.s_search = SearchBar(lambda _: self.reload())
        sl.addWidget(self.s_search)
        sl.addWidget(self.stock_table)

        batch_w = QWidget()
        bl = QVBoxLayout(batch_w)
        self.adj_btn = QPushButton(t("adjust"))
        self.adj_btn.clicked.connect(self._adjust)
        self.b_search = SearchBar(lambda _: self.reload(), [self.adj_btn])
        bl.addWidget(self.b_search)
        bl.addWidget(self.batch_table)

        led_w = QWidget()
        ll = QVBoxLayout(led_w)
        self.l_search = SearchBar(lambda _: self.reload())
        ll.addWidget(self.l_search)
        ll.addWidget(self.ledger_table)

        self.tabs.addTab(stock_w, t("current_stock"))
        self.tabs.addTab(batch_w, t("by_batch"))
        self.tabs.addTab(led_w, t("stock_ledger"))
        self.reload()

    def retranslate(self) -> None:
        self.tabs.setTabText(0, t("current_stock"))
        self.tabs.setTabText(1, t("by_batch"))
        self.tabs.setTabText(2, t("stock_ledger"))
        self.adj_btn.setText(t("adjust"))
        self.stock_table.set_headers(
            [t("brand"), t("generic"), t("company"), t("qty"), t("reorder_level"), t("value_cost"), t("value_sale")]
        )
        self.batch_table.set_headers(
            [t("brand"), t("batch"), t("expiry_date"), t("qty"), t("cost"), t("sale_price"), t("expired")]
        )
        self.ledger_table.set_headers(
            [t("time"), t("brand"), t("batch"), t("direction"), t("qty"), t("ref"), t("user"), t("notes")]
        )
        self.reload()

    def reload(self) -> None:
        stocks = stock_service.current_stock(self.s_search.edit.text())
        self.stock_table.fill(
            [
                [r["brand_name"], r["generic_name"], r["company_name"], r["qty"], r["reorder_level"], r["value_cost"], r["value_sale"]]
                for r in stocks
            ],
            [r["medicine_id"] for r in stocks],
            money_cols={5, 6},
        )
        batches = stock_service.all_batches(self.b_search.edit.text())
        self.batch_table.fill(
            [
                [
                    r["brand_name"],
                    r["batch_no"],
                    r["expiry"],
                    r["qty"],
                    r["cost_paisa"],
                    r["sale_paisa"],
                    "Yes" if r["expired"] else "",
                ]
                for r in batches
            ],
            [r["id"] for r in batches],
            money_cols={4, 5},
        )
        led = stock_service.ledger(self.l_search.edit.text())
        self.ledger_table.fill(
            [
                [r["ts"], r["brand_name"], r["batch_no"], r["direction"], r["qty"], r["ref_type"], r["username"], r["notes"]]
                for r in led
            ],
            [r["id"] for r in led],
        )

    def _adjust(self) -> None:
        bid = self.batch_table.selected_id()
        if not bid:
            error(self, t("select_row"))
            return
        batch = stock_service.get_batch(bid)
        dlg = QDialog(self)
        dlg.setWindowTitle(t("adjust"))
        form = QFormLayout(dlg)
        qty = QSpinBox()
        qty.setRange(0, 1_000_000)
        qty.setValue(batch["qty"])
        reason = QLineEdit()
        form.addRow(t("new_qty"), qty)
        form.addRow(t("reason"), reason)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        form.addRow(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec():
            if not reason.text().strip():
                error(self, t("required"))
                return
            try:
                stock_service.adjust_stock(bid, qty.value(), reason.text())
                info(self, t("success"))
                self.reload()
            except Exception as exc:
                error(self, exc)

    def apply_filter(self, extra: dict) -> None:
        self.reload()
        if extra.get("low"):
            stocks = [r for r in stock_service.current_stock() if r["qty"] <= r["reorder_level"]]
            self.stock_table.fill(
                [
                    [r["brand_name"], r["generic_name"], r["company_name"], r["qty"], r["reorder_level"], r["value_cost"], r["value_sale"]]
                    for r in stocks
                ],
                [r["medicine_id"] for r in stocks],
                money_cols={5, 6},
            )
            self.tabs.setCurrentIndex(0)
