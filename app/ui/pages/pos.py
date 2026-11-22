from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.constants import PAYMENT_CREDIT, PAYMENT_METHODS, STATUS_HELD
from app.i18n import t
from app.printing.receipt import show_bill
from app.services import backup_service, customer_service, medicine_service, period_service, sale_service, stock_service
from app.ui.widgets.helpers import DataTable, FlowLayout, error, info, money_spin, scroll_wrap
from app.utils.dates import today
from app.utils.money import format_pkr, from_paisa, to_paisa
from app.utils.pack import charge_paisa, medicine_unit_prices, pack_to_units, unit_paisa, units_per_pack


class PosPage(QWidget):
    def __init__(self):
        super().__init__()
        self.cart: list[dict] = []
        self.last_sale_id = None
        self._held_id = None
        self._paying = False
        self._selected = None
        self._batches: list[dict] = []
        self._pending_qty: int | None = None
        self._sell_mode = "unit"
        self._price_dirty = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        left = QFrame()
        left.setObjectName("PosLeft")
        left.setMinimumWidth(260)
        left.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        left_outer = QVBoxLayout(left)
        left_outer.setContentsMargins(0, 0, 0, 0)
        left_body = QWidget()
        left_body.setObjectName("PosLeftBody")
        left_scroll = scroll_wrap(left_body)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_outer.addWidget(left_scroll)
        ll = QVBoxLayout(left_body)
        ll.setContentsMargins(10, 10, 10, 10)
        ll.setSpacing(6)

        search_lab = self._muted(t("search_product"))
        self.search = QLineEdit()
        self.search.setObjectName("PosSearch")
        self.search.setPlaceholderText("Name, generic or barcode   ·   F2")
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(self._add_from_search)
        self.search.textChanged.connect(self._suggest)
        self.results = QListWidget()
        self.results.setObjectName("PosResults")
        self.results.setMinimumHeight(72)
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.results.itemClicked.connect(self._pick_result)
        self.results.itemActivated.connect(self._pick_result)
        ll.addWidget(search_lab)
        ll.addWidget(self.search)
        ll.addWidget(self.results, 1)

        self.pick = QFrame()
        self.pick.setObjectName("ProductCard")
        self.pick.setVisible(False)
        pl = QVBoxLayout(self.pick)
        pl.setContentsMargins(10, 8, 10, 8)
        pl.setSpacing(6)
        self.sel_name = QLabel("")
        self.sel_name.setObjectName("ProductName")
        self.sel_name.setWordWrap(True)
        self.sel_meta = QLabel("")
        self.sel_meta.setObjectName("ProductMeta")
        self.sel_meta.setWordWrap(True)
        pl.addWidget(self.sel_name)
        pl.addWidget(self.sel_meta)

        self.section_lab = QLabel("")
        self.section_lab.setObjectName("Muted")
        self.section_lab.setWordWrap(True)
        self.section_lab.setVisible(False)
        pl.addWidget(self.section_lab)

        self.pick_fields = QWidget()
        fields = QVBoxLayout(self.pick_fields)
        fields.setContentsMargins(0, 0, 0, 0)
        fields.setSpacing(6)

        form = QGridLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(4)
        form.setColumnStretch(0, 1)
        form.setColumnStretch(1, 1)
        self.cost = money_spin()
        self.cost.setReadOnly(True)
        self.price = money_spin()
        self.price.valueChanged.connect(self._on_price_edit)
        self.qty = QSpinBox()
        self.qty.setRange(1, 999_999)
        self.qty.setValue(1)
        self.qty.setKeyboardTracking(True)
        self.line_disc = money_spin()
        self.line_disc.hide()
        self.batch_box = QComboBox()
        self.batch_box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.batch_box.setMinimumContentsLength(8)
        self.batch_box.currentIndexChanged.connect(self._batch_changed)
        for spin in (self.cost, self.price, self.qty):
            spin.setMinimumWidth(90)
            spin.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.batch_box.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.cost_lab = self._muted(t("cost_price"))
        self.sale_lab = self._muted(t("price_per_tablet"))
        self.qty_lab = self._muted(t("tablets"))
        self.batch_lab = self._muted(t("batch"))
        form.addWidget(self.cost_lab, 0, 0)
        form.addWidget(self.sale_lab, 0, 1)
        form.addWidget(self.cost, 1, 0)
        form.addWidget(self.price, 1, 1)
        form.addWidget(self.qty_lab, 2, 0)
        form.addWidget(self.batch_lab, 2, 1)
        form.addWidget(self.qty, 3, 0)
        form.addWidget(self.batch_box, 3, 1)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self.mode_unit = QPushButton(t("sell_tablets"))
        self.mode_pack = QPushButton(t("sell_box"))
        self.mode_unit.setCheckable(True)
        self.mode_pack.setCheckable(True)
        self.mode_unit.setChecked(True)
        self.mode_unit.setObjectName("Chip")
        self.mode_pack.setObjectName("Chip")
        self.mode_unit.clicked.connect(lambda: self._set_sell_mode("unit"))
        self.mode_pack.clicked.connect(lambda: self._set_sell_mode("pack"))
        mode_row.addWidget(self.mode_unit)
        mode_row.addWidget(self.mode_pack)
        fields.addLayout(form)
        fields.addLayout(mode_row)

        self.line_total = QLabel("—")
        self.line_total.setObjectName("ProductMeta")
        self.line_total.setWordWrap(True)
        fields.addWidget(self.line_total)
        self.chip_row = QWidget()
        chips = FlowLayout(self.chip_row, spacing=6)
        self._qty_chips = []
        for n in (5, 10, 20, 40):
            btn = QPushButton(str(n))
            btn.setObjectName("Chip")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumWidth(44)
            btn.setMinimumHeight(28)
            btn.clicked.connect(lambda _, q=n: self._set_qty(q))
            chips.addWidget(btn)
            self._qty_chips.append(btn)
        self.pack_chip = QPushButton(t("sell_one_pack"))
        self.pack_chip.setObjectName("ChipGold")
        self.pack_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pack_chip.setMinimumHeight(28)
        self.pack_chip.clicked.connect(self._sell_pack)
        chips.addWidget(self.pack_chip)
        fields.addWidget(self.chip_row)
        self.qty.valueChanged.connect(self._refresh_pick_price)
        self.add_btn = QPushButton(t("add_to_cart"))
        self.add_btn.setObjectName("GoldBtn")
        self.add_btn.setMinimumHeight(38)
        self.add_btn.clicked.connect(self._add_to_cart)
        fields.addWidget(self.add_btn)
        self.pick_fields.setVisible(False)
        pl.addWidget(self.pick_fields)
        ll.addWidget(self.pick)

        right = QFrame()
        right.setObjectName("PosRight")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        cust_bar = QFrame()
        cust_bar.setObjectName("CustomerBar")
        cl = QHBoxLayout(cust_bar)
        cl.setContentsMargins(14, 10, 14, 10)
        cl.addWidget(self._muted(t("customer")))
        self.customer = QComboBox()
        self.customer.setEditable(True)
        self.customer.setMinimumHeight(36)
        self.customer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.customer.setPlaceholderText(t("search_customer"))
        self._reload_customers()
        cl.addWidget(self.customer, 1)
        rl.addWidget(cust_bar)

        header = QFrame()
        header.setObjectName("CartHeader")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 12, 16, 12)
        self.cart_title = QLabel(t("cart"))
        self.cart_title.setObjectName("CartHeaderText")
        self.cart_title.setWordWrap(False)
        self.month_lab = QLabel()
        self.month_lab.setObjectName("Muted")
        self.month_lab.setWordWrap(False)
        self.month_btn = QPushButton(t("new_month"))
        self.month_btn.setObjectName("GoldBtn")
        self.month_btn.setMinimumHeight(32)
        self.month_btn.setMinimumWidth(110)
        self.month_btn.clicked.connect(self._new_month)
        self.cart_count = QLabel("0")
        self.cart_count.setObjectName("CartCount")
        hl.addWidget(self.cart_title)
        hl.addWidget(self.month_lab)
        hl.addStretch()
        hl.addWidget(self.month_btn)
        hl.addWidget(self.cart_count)
        rl.addWidget(header)

        inner = QVBoxLayout()
        inner.setContentsMargins(12, 8, 12, 12)
        inner.setSpacing(8)
        self.table = DataTable(["#", t("brand"), t("rack"), t("qty"), "Rs", t("total")])
        self.table.setSortingEnabled(False)
        self.table.auto_fit = False
        self._fit_cart_columns()
        inner.addWidget(self.table, 1)
        self.empty_cart = QLabel(t("pos_cart_hint"))
        self.empty_cart.setObjectName("EmptyHint")
        self.empty_cart.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_cart.setWordWrap(True)
        inner.addWidget(self.empty_cart)
        cart_actions = QHBoxLayout()
        cart_actions.setSpacing(6)
        self.hold_btn = QPushButton(t("hold_short"))
        self.resume_btn = QPushButton(t("resume_short"))
        self.clear_btn = QPushButton(t("clear"))
        self.clear_btn.setObjectName("GhostBtn")
        self.hold_btn.clicked.connect(self._hold)
        self.resume_btn.clicked.connect(self._resume)
        self.clear_btn.clicked.connect(self.clear_cart)
        for w in (self.hold_btn, self.resume_btn, self.clear_btn):
            w.setMinimumHeight(36)
            w.setMinimumWidth(88)
            w.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            cart_actions.addWidget(w)
        inner.addLayout(cart_actions)
        rl.addLayout(inner, 1)

        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.split.setChildrenCollapsible(False)
        self.split.addWidget(left)
        self.split.addWidget(right)
        self.split.setStretchFactor(0, 1)
        self.split.setStretchFactor(1, 2)
        self.split.setSizes([340, 700])
        root.addWidget(self.split, 1)

        totals = QFrame()
        totals.setObjectName("TotalsBar")
        totals.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        tl = QHBoxLayout(totals)
        tl.setContentsMargins(10, 6, 10, 6)
        tl.setSpacing(8)
        self.bill_disc = money_spin()
        self.bill_disc.hide()
        self.method = QComboBox()
        self.method.addItems(list(PAYMENT_METHODS))
        self.method.setMinimumWidth(90)
        self.method.currentIndexChanged.connect(self._refresh_totals)
        self.paid = money_spin()
        self.paid.setMaximumWidth(140)
        self.paid.valueChanged.connect(self._refresh_totals)
        self.lbl_sub = QLabel()
        self.lbl_gst = QLabel()
        self.lbl_disc = QLabel()
        self.lbl_total = QLabel()
        self.lbl_total.setObjectName("TotalPill")
        self.lbl_total.setWordWrap(False)
        self.lbl_paid = QLabel()
        self.lbl_change = QLabel()
        self.lbl_change.setWordWrap(False)
        self.col_sub = self._col(t("subtotal"), self.lbl_sub)
        self.col_method = self._col(t("payment"), self.method)
        self.col_paid = self._col(t("paid"), self.paid)
        self.col_total = self._col(t("total"), self.lbl_total)
        self.col_change = self._col(t("change"), self.lbl_change)
        self.lbl_total.setObjectName("TotalPill")
        total_font = self.lbl_total.font()
        total_font.setPointSize(14)
        total_font.setBold(True)
        self.lbl_total.setFont(total_font)
        self.lbl_total.setMinimumWidth(130)
        for col in (self.col_sub, self.col_method, self.col_paid, self.col_total, self.col_change):
            tl.addWidget(col)
        tl.addStretch()
        self.pay_btn = QPushButton(t("pay_short"))
        self.pay_btn.setObjectName("GhostBtn")
        self.print_pay_btn = QPushButton(t("print_bill"))
        self.print_pay_btn.setObjectName("GoldBtn")
        for b in (self.pay_btn, self.print_pay_btn):
            b.setMinimumHeight(46)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        self.print_pay_btn.setMinimumWidth(140)
        self.pay_btn.clicked.connect(lambda: self._pay(print_receipt=False))
        self.print_pay_btn.clicked.connect(lambda: self._pay(print_receipt=True))
        tl.addWidget(self.pay_btn)
        tl.addWidget(self.print_pay_btn)
        root.addWidget(totals)

        QShortcut(QKeySequence("Delete"), self, activated=self._remove_line)
        QShortcut(QKeySequence("Escape"), self, activated=self.clear_cart)
        self._apply_section(None)
        self._render_cart()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not hasattr(self, "split"):
            return
        if self.width() < 860:
            self.split.setOrientation(Qt.Orientation.Vertical)
        else:
            self.split.setOrientation(Qt.Orientation.Horizontal)

    def _muted(self, text: str) -> QLabel:
        lab = QLabel(text.upper())
        lab.setObjectName("Muted")
        lab.setWordWrap(False)
        return lab

    def _col(self, title: str, widget) -> QWidget:
        box = QWidget()
        box.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(2)
        lab = QLabel(title.upper())
        lab.setObjectName("Muted")
        lab.setWordWrap(False)
        lay.addWidget(lab)
        if isinstance(widget, QLabel):
            widget.setObjectName("MoneyText")
            widget.setWordWrap(False)
        lay.addWidget(widget)
        box._title = lab
        return box

    def _fit_cart_columns(self) -> None:
        header = self.table.horizontalHeader()
        modes = QHeaderView.ResizeMode
        header.setSectionResizeMode(0, modes.Fixed)
        self.table.setColumnWidth(0, 32)
        header.setSectionResizeMode(1, modes.Stretch)
        header.setSectionResizeMode(2, modes.Fixed)
        self.table.setColumnWidth(2, 88)
        header.setSectionResizeMode(3, modes.Fixed)
        self.table.setColumnWidth(3, 56)
        header.setSectionResizeMode(4, modes.ResizeToContents)
        header.setSectionResizeMode(5, modes.ResizeToContents)
        header.setStretchLastSection(True)

    def focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    def has_open_sale(self) -> bool:
        return bool(self.cart)

    def retranslate(self) -> None:
        self.search.setPlaceholderText("Name, generic or barcode   ·   F2")
        self.table.set_headers(["#", t("brand"), t("rack"), t("qty"), "Rs", t("total")])
        self._fit_cart_columns()
        self.add_btn.setText(t("add_to_cart"))
        self.pack_chip.setText(t("sell_one_pack"))
        self.mode_unit.setText(t("sell_tablets"))
        self.mode_pack.setText(t("sell_box"))
        self.cost_lab.setText(t("cost_price").upper())
        self.sale_lab.setText(t("price_per_tablet").upper())
        self.qty_lab.setText(t("tablets").upper())
        self.batch_lab.setText(t("batch").upper())
        self.cart_title.setText(t("cart"))
        self.month_btn.setText(t("new_month"))
        self.empty_cart.setText(t("pos_cart_hint"))
        if not self._selected:
            self.sel_name.setText("")
            self.sel_meta.setText("")
            self.pick.setVisible(False)
        self.pay_btn.setText(t("pay_short"))
        self.print_pay_btn.setText(t("print_bill"))
        for col, key in (
            (self.col_sub, "subtotal"),
            (self.col_method, "payment"),
            (self.col_paid, "paid"),
            (self.col_total, "total"),
            (self.col_change, "change"),
        ):
            col._title.setText(t(key).upper())
        self.hold_btn.setText(t("hold_short"))
        self.resume_btn.setText(t("resume_short"))
        self.clear_btn.setText(t("clear"))
        self._refresh_totals()
        self._reload_customers()

    def reload(self) -> None:
        self._reload_customers()
        self._refresh_month_lab()
        self._resync_stock()

    def _clear_pick(self) -> None:
        self._selected = None
        self._batches = []
        self.batch_box.clear()
        self._price_dirty = False
        self.sel_name.setText("")
        self.sel_meta.setText("")
        self._apply_section(None)
        self._refresh_pick_price()

    def _resync_stock(self) -> None:
        """Drop cart lines and picks whose medicine was deleted or whose stock is gone since they were added."""
        removed: list[str] = []
        keep: list[dict] = []
        used: dict[int, int] = {}
        for item in self.cart:
            batch = stock_service.get_batch(item["batch_id"])
            med = medicine_service.get_medicine(item["medicine_id"])
            used[item["batch_id"]] = used.get(item["batch_id"], 0) + int(item["qty"])
            if not batch or not med or not med["active"] or used[item["batch_id"]] > int(batch["qty"]):
                removed.append(item.get("brand_name") or "?")
                used[item["batch_id"]] -= int(item["qty"])
                continue
            keep.append(item)
        if removed:
            self.cart = keep
            self._render_cart()
            info(self, f"{t('cart_items_removed')}\n{', '.join(removed)}")
        if self._selected:
            fresh = medicine_service.get_medicine(self._selected["id"])
            if not fresh or not fresh["active"] or not stock_service.sellable_batches(fresh["id"]):
                self._clear_pick()
        text = self.search.text()
        if text.strip():
            self._suggest(text)
        else:
            self.results.clear()

    def _refresh_month_lab(self) -> None:
        cur = period_service.current_period()
        self.month_lab.setText(cur.get("period_key") or "")

    def _new_month(self) -> None:
        try:
            result = period_service.close_previous_month()
            if result.get("already"):
                info(self, t("month_already_closed"))
            else:
                info(self, t("period_closed"))
            self._refresh_month_lab()
        except Exception as exc:
            error(self, exc)

    def _reload_customers(self) -> None:
        current = self.customer.currentData() if self.customer.count() else None
        self.customer.blockSignals(True)
        self.customer.clear()
        self.customer.addItem(t("walk_in"), None)
        for c in customer_service.list_customers(active_only=True):
            self.customer.addItem(f"{c['name']} ({c['phone'] or ''})", c["id"])
        if current:
            idx = self.customer.findData(current)
            if idx >= 0:
                self.customer.setCurrentIndex(idx)
        self.customer.blockSignals(False)

    def _item_kind(self, med: dict | None) -> str:
        cat = ((med or {}).get("category") or "").lower()
        if any(x in cat for x in ("inject", "infusion", "syringe", "surgical")):
            return "surgical"
        if any(x in cat for x in ("syrup", "suspension", "drop", "bottle")):
            return "liquid"
        if any(x in cat for x in ("cream", "ointment")):
            return "topical"
        return "tablet"

    def _apply_section(self, med: dict | None) -> None:
        kind = self._item_kind(med)
        titles = {
            "tablet": t("section_tablet"),
            "surgical": t("section_surgical"),
            "liquid": t("section_liquid"),
            "topical": t("section_topical"),
        }
        qty_labs = {
            "tablet": t("tablets"),
            "surgical": t("qty_units"),
            "liquid": t("qty_bottles"),
            "topical": t("qty_units"),
        }
        price_labs = {
            "tablet": t("price_per_tablet"),
            "surgical": t("price_per_item"),
            "liquid": t("price_per_item"),
            "topical": t("price_per_item"),
        }
        self.section_lab.setText(titles[kind])
        self.section_lab.setVisible(bool(med))
        if self._sell_mode == "pack":
            self.qty_lab.setText(t("packs").upper())
            self.sale_lab.setText(t("pack_sale").upper())
            self.cost_lab.setText(t("pack_cost").upper())
        else:
            self.qty_lab.setText(qty_labs[kind].upper())
            self.sale_lab.setText(price_labs[kind].upper())
            self.cost_lab.setText(t("cost_price").upper())
        tablet = kind == "tablet"
        self.chip_row.setVisible(tablet)
        self.pack_chip.setVisible(tablet)
        self.mode_pack.setVisible(tablet)
        self.mode_unit.setVisible(tablet)
        self.pick_fields.setVisible(bool(med))
        self.pick.setVisible(bool(med))
        self.results.setMaximumHeight(96 if med else 16777215)

    def _split_qty(self, text: str) -> tuple[int | None, str]:
        raw = text.strip()
        m = re.match(r"^(\d{1,5})\s+(.+)$", raw)
        if m:
            return int(m.group(1)), m.group(2)
        if raw.isdigit() and 1 <= int(raw) <= 9999:
            return int(raw), ""
        return None, raw

    def _suggest(self, text: str) -> None:
        self.results.clear()
        qty, q = self._split_qty(text)
        if qty and not q:
            self._pending_qty = qty
            return
        if qty:
            self._pending_qty = qty
        if len(q.strip()) < 1:
            self._apply_section(None)
            return
        groups: dict[str, list] = {}
        for m in medicine_service.search_pos(q):
            groups.setdefault(self._item_kind(m), []).append(m)
        titles = {
            "tablet": t("section_tablet"),
            "surgical": t("section_surgical"),
            "liquid": t("section_liquid"),
            "topical": t("section_topical"),
        }
        for kind in ("tablet", "surgical", "liquid", "topical"):
            items = groups.get(kind) or []
            if not items:
                continue
            head = QListWidgetItem(f"──  {titles[kind]}  ──")
            head.setFlags(Qt.ItemFlag.NoItemFlags)
            self.results.addItem(head)
            for m in items:
                each, _cost = medicine_unit_prices(m)
                unit = "tab" if kind == "tablet" else "pcs"
                label = (
                    f"{m['brand_name']}   ·   {m['generic_name'] or '—'}     "
                    f"{int(m['stock_qty'] or 0)} {unit}   ·   {format_pkr(each)}"
                )
                row = QListWidgetItem(label)
                row.setData(Qt.ItemDataRole.UserRole, m)
                self.results.addItem(row)

    def _pick_result(self, item) -> None:
        med = item.data(Qt.ItemDataRole.UserRole) if item else None
        if med:
            self._select_product(med)

    def _add_from_search(self) -> None:
        qty, q = self._split_qty(self.search.text())
        if qty and not q:
            self._pending_qty = qty
            self.search.clear()
            return
        if self.results.count() == 0:
            return
        item = self.results.item(0) if self.results.currentRow() < 0 else self.results.currentItem()
        if not item:
            return
        med = item.data(Qt.ItemDataRole.UserRole)
        self._select_product(med)
        barcode_q = q or self.search.text().strip()
        if med and med.get("barcode") and med["barcode"] == barcode_q:
            self._add_to_cart()

    def _select_product(self, med: dict | None) -> None:
        if not med:
            return
        fresh = medicine_service.get_medicine(med["id"])
        if fresh:
            med = {**med, **fresh}
        batches = stock_service.sellable_batches(med["id"])
        if not batches:
            expired = stock_service.batches_for_medicine(med["id"], include_empty=False)
            error(self, t("expired_block") if expired else t("insufficient_stock"))
            return
        if med.get("controlled"):
            info(self, t("controlled_warn"))
        self._selected = med
        self._batches = batches
        if self._item_kind(med) != "tablet" and self._sell_mode == "pack":
            self._sell_mode = "unit"
            self.mode_unit.setChecked(True)
            self.mode_pack.setChecked(False)
        self._apply_section(med)
        self.sel_name.setText(f"{med['brand_name']}")
        generic = med.get("generic_name") or ""
        rack = med.get("rack") or ""
        upp = units_per_pack(med)
        stock_qty = int(batches[0]["qty"] or 0)
        reorder = int(med.get("reorder_level") or 0)
        low = t("low_stock") if stock_qty <= reorder else ""
        extra = "  ·  ".join(
            p
            for p in (
                generic,
                med.get("category") or "",
                f"{upp} / box" if self._item_kind(med) == "tablet" else "",
                f"{t('rack')} {rack}" if rack else "",
                f"{stock_qty} in stock",
                low,
            )
            if p
        )
        self.sel_meta.setText(extra)
        self.batch_box.clear()
        for b in batches:
            self.batch_box.addItem(f"{b['batch_no']}  exp {b['expiry']}  {b['qty']}", b)
        start_qty = self._pending_qty or 1
        self.qty.setRange(1, 999_999)
        self.qty.setValue(start_qty)
        self._pending_qty = None
        self._price_dirty = False
        self._refresh_pick_price()

    def _unit_prices(self, batch: dict | None = None) -> tuple[int, int]:
        return medicine_unit_prices(self._selected, batch or self.batch_box.currentData())

    def _set_qty(self, qty: int) -> None:
        self.qty.setValue(max(1, int(qty)))

    def _set_sell_mode(self, mode: str) -> None:
        self._sell_mode = "pack" if mode == "pack" else "unit"
        self.mode_unit.setChecked(self._sell_mode == "unit")
        self.mode_pack.setChecked(self._sell_mode == "pack")
        self._price_dirty = False
        self._apply_section(self._selected)
        if self._sell_mode == "pack" and self._selected:
            self.qty.setValue(1)
        self._refresh_pick_price()

    def _on_price_edit(self) -> None:
        if self.price.hasFocus():
            self._price_dirty = True
        self._refresh_pick_price()

    def _sell_pack(self) -> None:
        if not self._selected:
            return
        self._set_sell_mode("pack")
        self._set_qty(1)

    def _line_charge(self) -> tuple[int, int, int]:
        """Return (unit_paisa, tablets, line_base_paisa) for the current pick."""
        sale, cost = self._unit_prices()
        med = self._selected or {}
        upp = units_per_pack(med)
        pack_sale = int(med.get("sale_paisa") or 0)
        if self._sell_mode == "pack":
            packs = max(1, self.qty.value())
            tablets = pack_to_units(packs, upp)
            box_sale = to_paisa(self.price.value()) if self._price_dirty else (pack_sale or sale * upp)
            box_cost = cost * upp
            self.cost.blockSignals(True)
            self.cost.setValue(from_paisa(box_cost))
            self.cost.blockSignals(False)
            if not self._price_dirty:
                self.price.blockSignals(True)
                self.price.setValue(from_paisa(box_sale))
                self.price.blockSignals(False)
            unit = unit_paisa(to_paisa(self.price.value()), upp)
            return unit, tablets, charge_paisa(to_paisa(self.price.value()), upp, tablets)
        unit = to_paisa(self.price.value()) if self._price_dirty else sale
        self.cost.blockSignals(True)
        self.cost.setValue(from_paisa(cost))
        self.cost.blockSignals(False)
        if not self._price_dirty:
            self.price.blockSignals(True)
            self.price.setValue(from_paisa(unit))
            self.price.blockSignals(False)
        qty = max(1, self.qty.value())
        return unit, qty, unit * qty

    def _refresh_pick_price(self) -> None:
        if not self._selected:
            self.line_total.setText("")
            return
        sale, _tablets, base = self._line_charge()
        qty = self.qty.value()
        self.line_disc.setValue(0)
        kind = "box" if self._sell_mode == "pack" else "tab"
        self.line_total.setText(
            f"{t('line_total')}  {format_pkr(max(0, base))}   ·   {qty} {kind}   ·   {format_pkr(sale)} / tab"
        )

    def _batch_changed(self) -> None:
        b = self.batch_box.currentData()
        if not b:
            return
        self._refresh_pick_price()

    def _add_to_cart(self) -> None:
        if not self._selected:
            error(self, t("search_product"))
            return
        b = self.batch_box.currentData()
        if not b:
            error(self, t("insufficient_stock"))
            return
        if b["expiry"] < today():
            error(self, t("expired_block"))
            return
        sale, tablets, base = self._line_charge()
        _sale, cost = self._unit_prices(b)
        live = stock_service.get_batch(b["id"])
        in_cart = sum(int(x["qty"]) for x in self.cart if x["batch_id"] == b["id"])
        if not live or tablets + in_cart > int(live["qty"]):
            left = int(live["qty"]) - in_cart if live else 0
            error(self, f"{t('insufficient_stock')} ({max(0, left)} left)")
            return
        self.cart.append(
            {
                "medicine_id": self._selected["id"],
                "brand_name": self._selected["brand_name"],
                "batch_id": b["id"],
                "batch_no": b["batch_no"],
                "expiry": b["expiry"],
                "qty": tablets,
                "unit_price_paisa": sale,
                "cost_paisa": cost,
                "discount_paisa": 0,
                "gst_pct": self._selected.get("gst_pct") or 0,
                "line_base_paisa": base,
                "sell_mode": self._sell_mode,
                "units_per_pack": units_per_pack(self._selected),
                "display_qty": self.qty.value(),
                "rack": (self._selected.get("rack") or "").strip(),
            }
        )
        self.search.clear()
        self.results.clear()
        self._clear_pick()
        self._set_sell_mode("unit")
        self._render_cart()
        self.search.setFocus()

    def _render_cart(self) -> None:
        self.table.fill(
            [
                [
                    i + 1,
                    x.get("brand_name") or "",
                    (x.get("rack") or "").strip() or "—",
                    (
                        f"{x.get('display_qty', x['qty'])} {t('packs')}"
                        if x.get("sell_mode") == "pack"
                        else x["qty"]
                    ),
                    x["unit_price_paisa"],
                    (x.get("line_base_paisa") if x.get("line_base_paisa") is not None else x["qty"] * x["unit_price_paisa"]),
                ]
                for i, x in enumerate(self.cart)
            ],
            list(range(len(self.cart))),
            money_cols={4, 5},
        )
        self._fit_cart_columns()
        self._refresh_totals()
        n = len(self.cart)
        self.cart_count.setText(f"{n}")
        self.empty_cart.setVisible(n == 0)
        self.table.setVisible(n > 0)

    def _cart_brand(self, item: dict) -> str:
        name = item.get("brand_name") or ""
        rack = (item.get("rack") or "").strip()
        return f"{name}  ·  {t('rack')} {rack}" if rack else name

    def _cart_totals(self) -> tuple[int, int, int]:
        subtotal = gst = 0
        for item in self.cart:
            raw = item.get("line_base_paisa")
            if raw is None:
                raw = item["qty"] * item["unit_price_paisa"]
            base = raw - item["discount_paisa"]
            subtotal += max(0, base)
            gst += int(round(max(0, base) * float(item.get("gst_pct") or 0) / 100.0))
        disc = to_paisa(self.bill_disc.value())
        total = max(0, subtotal + gst - disc)
        return subtotal, gst, total

    def _refresh_totals(self) -> None:
        sub, gst, total = self._cart_totals()
        paid = to_paisa(self.paid.value())
        change = max(0, paid - total) if self.method.currentText() != PAYMENT_CREDIT else 0
        self.lbl_sub.setText(format_pkr(sub))
        self.lbl_gst.setText(format_pkr(gst))
        self.lbl_total.setText(format_pkr(total))
        self.lbl_change.setText(format_pkr(change))
        self._refresh_month_lab()
        if self.method.currentText() != PAYMENT_CREDIT and not self.paid.hasFocus():
            self.paid.blockSignals(True)
            self.paid.setValue(total / 100.0)
            self.paid.blockSignals(False)

    def _remove_line(self) -> None:
        idx = self.table.selected_id()
        if idx is None:
            return
        if 0 <= idx < len(self.cart):
            self.cart.pop(idx)
            self._render_cart()

    def clear_cart(self) -> None:
        self.cart = []
        self._held_id = None
        self.bill_disc.setValue(0)
        self._render_cart()

    def _pay(self, print_receipt: bool = True) -> None:
        if self._paying:
            return
        if not self.cart:
            error(self, t("cart_empty"))
            return
        method = self.method.currentText()
        customer_id = self.customer.currentData()
        if method == PAYMENT_CREDIT and not customer_id:
            error(self, t("credit_needs_customer"))
            return
        self._paying = True
        try:
            try:
                sid = sale_service.complete_sale(
                    self.cart,
                    method,
                    to_paisa(self.paid.value()),
                    customer_id,
                    to_paisa(self.bill_disc.value()),
                    held_id=self._held_id,
                )
            except Exception as exc:
                error(self, exc)
                return
            self.last_sale_id = sid
            sold = list(self.cart)
            self.clear_cart()
            try:
                show_bill(sale_service.get_sale(sid), parent=self, print_now=print_receipt)
            except Exception as exc:
                error(self, exc)
            backup_service.mirror_now()
            self._warn_low_after_sale(sold)
        finally:
            self._paying = False

    def _warn_low_after_sale(self, sold: list[dict]) -> None:
        names = []
        seen: set[int] = set()
        for item in sold:
            mid = item.get("medicine_id")
            if not mid or mid in seen:
                continue
            seen.add(mid)
            med = medicine_service.get_medicine(mid)
            if not med:
                continue
            qty = sum(int(b.get("qty") or 0) for b in stock_service.batches_for_medicine(mid, include_empty=True))
            if qty <= int(med.get("reorder_level") or 0):
                names.append(med["brand_name"])
        if names:
            info(self, f"{t('low_stock_after_sale')}: {', '.join(names)}")

    def _hold(self) -> None:
        if not self.cart:
            error(self, t("cart_empty"))
            return
        try:
            sale_service.hold_sale(self.cart, self.customer.currentData(), to_paisa(self.bill_disc.value()))
            self.clear_cart()
            info(self, t("success"))
        except Exception as exc:
            error(self, exc)

    def _resume(self) -> None:
        held = sale_service.list_sales(status=STATUS_HELD)
        if not held:
            error(self, t("held_sales"))
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(t("held_sales"))
        box = QVBoxLayout(dlg)
        lst = QListWidget()
        for s in held:
            lst.addItem(f"#{s['id']} {s['ts']} {format_pkr(s['total_paisa'])}")
            lst.item(lst.count() - 1).setData(Qt.ItemDataRole.UserRole, s["id"])
        box.addWidget(lst)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec() and lst.currentItem():
            sid = lst.currentItem().data(Qt.ItemDataRole.UserRole)
            try:
                sale = sale_service.resume_held(sid)
                self.cart = []
                for item in sale["items"]:
                    gst_pct = 0.0
                    base = item["qty"] * item["unit_price_paisa"] - item["discount_paisa"]
                    if base > 0 and item.get("gst_paisa"):
                        gst_pct = item["gst_paisa"] * 100.0 / base
                    self.cart.append(
                        {
                            "medicine_id": item["medicine_id"],
                            "brand_name": item["brand_name"],
                            "rack": (medicine_service.get_medicine(item["medicine_id"]) or {}).get("rack") or "",
                            "batch_id": item["batch_id"],
                            "batch_no": item["batch_no"],
                            "expiry": item["expiry"],
                            "qty": item["qty"],
                            "unit_price_paisa": item["unit_price_paisa"],
                            "cost_paisa": item["cost_paisa"],
                            "discount_paisa": item["discount_paisa"],
                            "gst_pct": gst_pct,
                        }
                    )
                self.bill_disc.setValue((sale["discount_paisa"] or 0) / 100.0)
                if sale.get("customer_id"):
                    idx = self.customer.findData(sale["customer_id"])
                    if idx >= 0:
                        self.customer.setCurrentIndex(idx)
                self._render_cart()
            except Exception as exc:
                error(self, exc)

    def _reprint(self, thermal: bool = True) -> None:
        if not self.last_sale_id:
            error(self, t("select_row"))
            return
        sale = sale_service.get_sale(self.last_sale_id)
        show_bill(sale, parent=self, print_now=thermal)
