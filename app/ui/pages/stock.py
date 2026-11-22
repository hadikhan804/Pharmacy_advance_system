from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
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

from app.constants import CATEGORIES
from app.i18n import t
from app.services import medicine_service, stock_service
from app.ui.widgets.helpers import DataTable, SearchBar, error, info, money_spin
from app.utils.money import to_paisa
from app.utils.pack import pack_to_units, unit_paisa, units_per_pack


class StockPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.stock_table = DataTable(
            [t("brand"), t("generic"), t("category"), t("company"), t("qty"), t("reorder_level"), t("value_cost"), t("value_sale")]
        )
        self.batch_table = DataTable(
            [t("brand"), t("category"), t("batch"), t("expiry_date"), t("qty"), t("cost"), t("sale_price"), t("expired")]
        )
        self.ledger_table = DataTable(
            [t("time"), t("brand"), t("batch"), t("direction"), t("qty"), t("ref"), t("user"), t("notes")]
        )
        self.stock_table.cellDoubleClicked.connect(lambda *_: self._reedit_from_stock())
        self.batch_table.cellDoubleClicked.connect(lambda *_: self._reedit())

        stock_w = QWidget()
        sl = QVBoxLayout(stock_w)
        self.s_search = SearchBar(lambda _: self.reload())
        sl.addWidget(self.s_search)
        actions = QHBoxLayout()
        self.cat_filter = QComboBox()
        self.cat_filter.addItem(t("category"), "")
        for name in CATEGORIES:
            self.cat_filter.addItem(name, name)
        self.cat_filter.currentIndexChanged.connect(lambda _: self.reload())
        self.reedit_stock_btn = QPushButton(t("reedit"))
        self.reedit_stock_btn.setObjectName("GoldBtn")
        self.reedit_stock_btn.setMinimumHeight(40)
        self.reedit_stock_btn.clicked.connect(self._reedit_from_stock)
        self.restock_btn = QPushButton(t("restock"))
        self.restock_btn.setMinimumHeight(40)
        self.restock_btn.clicked.connect(self._restock)
        actions.addWidget(self.reedit_stock_btn)
        actions.addWidget(self.restock_btn)
        actions.addWidget(self.cat_filter)
        actions.addStretch()
        sl.addLayout(actions)
        sl.addWidget(self.stock_table)

        batch_w = QWidget()
        bl = QVBoxLayout(batch_w)
        self.b_search = SearchBar(lambda _: self.reload())
        bl.addWidget(self.b_search)
        batch_actions = QHBoxLayout()
        self.reedit_btn = QPushButton(t("reedit"))
        self.reedit_btn.setObjectName("GoldBtn")
        self.reedit_btn.setMinimumHeight(40)
        self.reedit_btn.clicked.connect(self._reedit)
        self.adj_btn = QPushButton(t("adjust"))
        self.adj_btn.setMinimumHeight(40)
        self.adj_btn.clicked.connect(self._adjust)
        batch_actions.addWidget(self.reedit_btn)
        batch_actions.addWidget(self.adj_btn)
        batch_actions.addStretch()
        bl.addLayout(batch_actions)
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
        self.reedit_btn.setText(t("reedit"))
        self.reedit_stock_btn.setText(t("reedit"))
        self.restock_btn.setText(t("restock"))
        self.stock_table.set_headers(
            [t("brand"), t("generic"), t("category"), t("company"), t("qty"), t("reorder_level"), t("value_cost"), t("value_sale")]
        )
        self.batch_table.set_headers(
            [t("brand"), t("category"), t("batch"), t("expiry_date"), t("qty"), t("cost"), t("sale_price"), t("expired")]
        )
        self.ledger_table.set_headers(
            [t("time"), t("brand"), t("batch"), t("direction"), t("qty"), t("ref"), t("user"), t("notes")]
        )
        self.reload()

    def reload(self) -> None:
        cat = self.cat_filter.currentData() if hasattr(self, "cat_filter") else ""
        stocks = stock_service.current_stock(self.s_search.edit.text())
        if cat:
            stocks = [r for r in stocks if (r.get("category") or "") == cat]
        self.stock_table.fill(
            [
                [
                    r["brand_name"],
                    r["generic_name"],
                    r.get("category") or "",
                    r["company_name"],
                    r["qty"],
                    r["reorder_level"],
                    r["value_cost"],
                    r["value_sale"],
                ]
                for r in stocks
            ],
            [r["medicine_id"] for r in stocks],
            money_cols={6, 7},
        )
        batches = stock_service.all_batches(self.b_search.edit.text())
        if cat:
            batches = [r for r in batches if (r.get("category") or "") == cat]
        self.batch_table.fill(
            [
                [
                    r["brand_name"],
                    r.get("category") or "",
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
            money_cols={5, 6},
        )
        led = stock_service.ledger(self.l_search.edit.text())
        self.ledger_table.fill(
            [
                [r["ts"], r["brand_name"], r["batch_no"], r["direction"], r["qty"], r["ref_type"], r["username"], r["notes"]]
                for r in led
            ],
            [r["id"] for r in led],
        )

    def _reedit_from_stock(self) -> None:
        mid = self.stock_table.selected_id()
        if not mid:
            error(self, t("select_row"))
            return
        batches = stock_service.batches_for_medicine(int(mid), include_empty=True)
        if not batches:
            error(self, t("select_row"))
            return
        if len(batches) == 1:
            self._open_reedit(int(batches[0]["id"]))
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(t("reedit"))
        form = QFormLayout(dlg)
        box = QComboBox()
        for b in batches:
            box.addItem(f"{b.get('batch_no') or 'NA'}  ·  {b.get('expiry') or ''}  ·  {b.get('qty')}", b["id"])
        form.addRow(t("batch"), box)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        form.addRow(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec():
            self._open_reedit(int(box.currentData()))

    def _reedit(self) -> None:
        bid = self.batch_table.selected_id()
        if not bid:
            error(self, t("select_row"))
            return
        self._open_reedit(int(bid))

    def _open_reedit(self, bid: int) -> None:
        batch = stock_service.get_batch(bid)
        if not batch:
            error(self, t("select_row"))
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(t("reedit"))
        dlg.resize(440, 380)
        form = QFormLayout(dlg)
        batch_no = QLineEdit(batch.get("batch_no") or "")
        expiry = QDateEdit()
        expiry.setCalendarPopup(True)
        exp = QDate.fromString(str(batch.get("expiry") or ""), "yyyy-MM-dd")
        expiry.setDate(exp if exp.isValid() else QDate.currentDate().addYears(2))
        qty = QSpinBox()
        qty.setRange(0, 1_000_000)
        qty.setValue(int(batch.get("qty") or 0))
        cost = money_spin(int(batch.get("cost_paisa") or 0) / 100.0)
        sale = money_spin(int(batch.get("sale_paisa") or 0) / 100.0)
        reason = QLineEdit()
        reason.setPlaceholderText(t("reedit_reason"))
        form.addRow(t("batch"), batch_no)
        form.addRow(t("expiry_date"), expiry)
        form.addRow(t("new_qty"), qty)
        form.addRow(t("cost_price"), cost)
        form.addRow(t("sale_price"), sale)
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
                stock_service.edit_batch(
                    bid,
                    batch_no.text().strip(),
                    expiry.date().toString("yyyy-MM-dd"),
                    qty.value(),
                    to_paisa(cost.value()),
                    to_paisa(sale.value()),
                    reason.text(),
                )
                info(self, t("success"))
                self.reload()
            except Exception as exc:
                error(self, exc)

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

    def _restock(self) -> None:
        mid = self.stock_table.selected_id()
        if not mid:
            error(self, t("select_row"))
            return
        med = medicine_service.get_medicine(mid)
        if not med:
            error(self, t("select_row"))
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(t("restock"))
        form = QFormLayout(dlg)
        boxes = QSpinBox()
        boxes.setRange(1, 1_000_000)
        boxes.setValue(1)
        batch = QLineEdit()
        expiry = QDateEdit()
        expiry.setCalendarPopup(True)
        expiry.setDate(QDate.currentDate().addYears(2))
        cost = money_spin(int(med.get("cost_paisa") or 0) / 100.0)
        sale = money_spin(int(med.get("sale_paisa") or 0) / 100.0)
        form.addRow(t("brand"), QLabel(med["brand_name"]))
        form.addRow(t("category"), QLabel(med.get("category") or "—"))
        form.addRow(t("stock_size"), boxes)
        form.addRow(t("batch"), batch)
        form.addRow(t("expiry_date"), expiry)
        form.addRow(t("cost_price"), cost)
        form.addRow(t("sale_price_box"), sale)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        form.addRow(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec():
            upp = units_per_pack(med)
            pack_cost = to_paisa(cost.value())
            pack_sale = to_paisa(sale.value())
            try:
                stock_service.restock_medicine(
                    mid,
                    pack_to_units(boxes.value(), upp),
                    batch.text().strip() or "NA",
                    expiry.date().toString("yyyy-MM-dd"),
                    unit_paisa(pack_cost, upp),
                    unit_paisa(pack_sale, upp),
                    pack_cost,
                    pack_sale,
                    "Restock",
                )
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
                    [
                        r["brand_name"],
                        r["generic_name"],
                        r.get("category") or "",
                        r["company_name"],
                        r["qty"],
                        r["reorder_level"],
                        r["value_cost"],
                        r["value_sale"],
                    ]
                    for r in stocks
                ],
                [r["medicine_id"] for r in stocks],
                money_cols={6, 7},
            )
            self.tabs.setCurrentIndex(0)
