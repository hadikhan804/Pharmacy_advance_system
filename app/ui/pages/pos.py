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
    QVBoxLayout,
    QWidget,
)

from app.constants import PAYMENT_CREDIT, PAYMENT_METHODS, STATUS_HELD
from app.i18n import t
from app.printing.receipt import show_bill
from app.services import customer_service, medicine_service, sale_service, stock_service
from app.ui.widgets.helpers import DataTable, error, info, money_spin
from app.utils.dates import today
from app.utils.money import format_pkr, from_paisa, to_paisa
from app.utils.pack import unit_paisa, units_per_pack


class PosPage(QWidget):
    def __init__(self):
        super().__init__()
        self.cart: list[dict] = []
        self.last_sale_id = None
        self._held_id = None
        self._selected = None
        self._batches: list[dict] = []
        self._pending_qty: int | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        body = QHBoxLayout()
        body.setSpacing(14)

        left = QFrame()
        left.setObjectName("PosLeft")
        left.setMinimumWidth(460)
        left.setMaximumWidth(520)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 16, 16, 16)
        ll.setSpacing(10)

        search_lab = self._muted(t("search_product"))
        self.search = QLineEdit()
        self.search.setObjectName("PosSearch")
        self.search.setPlaceholderText("Name, generic or barcode   ·   F2")
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(self._add_from_search)
        self.search.textChanged.connect(self._suggest)
        self.results = QListWidget()
        self.results.setObjectName("PosResults")
        self.results.setMinimumHeight(168)
        self.results.itemClicked.connect(self._pick_result)
        self.results.itemActivated.connect(self._pick_result)
        ll.addWidget(search_lab)
        ll.addWidget(self.search)
        ll.addWidget(self.results, 1)

        pick = QFrame()
        pick.setObjectName("ProductCard")
        pl = QVBoxLayout(pick)
        pl.setContentsMargins(12, 12, 12, 12)
        pl.setSpacing(8)
        self.sel_name = QLabel(t("pos_pick_hint"))
        self.sel_name.setObjectName("ProductName")
        self.sel_name.setWordWrap(True)
        self.sel_meta = QLabel("")
        self.sel_meta.setObjectName("ProductMeta")
        self.sel_meta.setWordWrap(True)
        pl.addWidget(self.sel_name)
        pl.addWidget(self.sel_meta)

        self.section_lab = QLabel("")
        self.section_lab.setObjectName("CartHeaderText")
        self.section_lab.setVisible(False)
        pl.addWidget(self.section_lab)

        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)
        self.price = money_spin()
        self.price.setReadOnly(True)
        self.price.setMinimumWidth(140)
        self.qty = QSpinBox()
        self.qty.setRange(1, 999_999)
        self.qty.setValue(1)
        self.qty.setMinimumWidth(140)
        self.qty.setMinimumHeight(36)
        self.qty.setKeyboardTracking(True)
        self.line_disc = money_spin()
        self.batch_box = QComboBox()
        self.batch_box.setMinimumWidth(140)
        self.batch_box.currentIndexChanged.connect(self._batch_changed)
        self.price_lab = self._muted(t("price_per_tablet"))
        self.qty_lab = self._muted(t("tablets"))
        form.addWidget(self.price_lab, 0, 0)
        form.addWidget(self.price, 1, 0)
        form.addWidget(self.qty_lab, 0, 1)
        form.addWidget(self.qty, 1, 1)
        form.addWidget(self._muted(t("line_discount")), 2, 0)
        form.addWidget(self.line_disc, 3, 0)
        form.addWidget(self._muted(t("batch")), 2, 1)
        form.addWidget(self.batch_box, 3, 1)
        pl.addLayout(form)
        self.line_total = QLabel("—")
        self.line_total.setObjectName("ProductMeta")
        pl.addWidget(self.line_total)
        self.chip_row = QWidget()
        chips = QHBoxLayout(self.chip_row)
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setSpacing(6)
        self._qty_chips = []
        for n in (5, 10, 20, 40):
            btn = QPushButton(str(n))
            btn.setObjectName("Chip")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumWidth(48)
            btn.clicked.connect(lambda _, q=n: self._set_qty(q))
            chips.addWidget(btn)
            self._qty_chips.append(btn)
        self.pack_chip = QPushButton(t("sell_one_pack"))
        self.pack_chip.setObjectName("ChipGold")
        self.pack_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pack_chip.clicked.connect(self._sell_pack)
        chips.addWidget(self.pack_chip)
        chips.addStretch()
        pl.addWidget(self.chip_row)
        self.qty.valueChanged.connect(self._refresh_pick_price)
        self.line_disc.valueChanged.connect(self._refresh_pick_price)
        self.add_btn = QPushButton(t("add_to_cart"))
        self.add_btn.setObjectName("GoldBtn")
        self.add_btn.setMinimumHeight(46)
        self.add_btn.clicked.connect(self._add_to_cart)
        pl.addWidget(self.add_btn)
        ll.addWidget(pick)

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
        self.cart_count = QLabel("0")
        self.cart_count.setObjectName("CartCount")
        hl.addWidget(self.cart_title)
        hl.addStretch()
        hl.addWidget(self.cart_count)
        rl.addWidget(header)

        inner = QVBoxLayout()
        inner.setContentsMargins(12, 8, 12, 12)
        inner.setSpacing(8)
        self.table = DataTable(
            ["#", t("brand"), t("batch"), t("qty"), t("sale_price"), t("discount"), t("total")]
        )
        self.table.setSortingEnabled(False)
        self._fit_cart_columns()
        inner.addWidget(self.table, 1)
        self.empty_cart = QLabel(t("pos_cart_hint"))
        self.empty_cart.setObjectName("EmptyHint")
        self.empty_cart.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_cart.setWordWrap(True)
        inner.addWidget(self.empty_cart)
        self.chip_wrap = QWidget()
        self.chip_layout = QHBoxLayout(self.chip_wrap)
        self.chip_layout.setContentsMargins(0, 0, 0, 0)
        inner.addWidget(self.chip_wrap)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.pay_btn = QPushButton(t("checkout"))
        self.pay_btn.setObjectName("GoldBtn")
        self.print_pay_btn = QPushButton(t("checkout_print"))
        self.print_pay_btn.setObjectName("DarkBtn")
        self.hold_btn = QPushButton(t("hold_sale"))
        self.resume_btn = QPushButton(t("resume"))
        self.clear_btn = QPushButton(t("clear"))
        self.clear_btn.setObjectName("GhostBtn")
        self.pay_btn.clicked.connect(lambda: self._pay(print_receipt=False))
        self.print_pay_btn.clicked.connect(lambda: self._pay(print_receipt=True))
        self.hold_btn.clicked.connect(self._hold)
        self.resume_btn.clicked.connect(self._resume)
        self.clear_btn.clicked.connect(self.clear_cart)
        for w in (self.pay_btn, self.print_pay_btn):
            w.setMinimumHeight(44)
            actions.addWidget(w, 2)
        for w in (self.hold_btn, self.resume_btn, self.clear_btn):
            w.setMinimumHeight(44)
            actions.addWidget(w, 1)
        inner.addLayout(actions)
        rl.addLayout(inner, 1)

        body.addWidget(left)
        body.addWidget(right, 1)
        root.addLayout(body, 1)

        totals = QFrame()
        totals.setObjectName("TotalsBar")
        tl = QHBoxLayout(totals)
        self.bill_disc = money_spin()
        self.bill_disc.valueChanged.connect(self._on_bill_disc)
        self.method = QComboBox()
        self.method.addItems(list(PAYMENT_METHODS))
        self.method.currentIndexChanged.connect(self._refresh_totals)
        self.paid = money_spin()
        self.paid.valueChanged.connect(self._refresh_totals)
        self.lbl_sub = QLabel()
        self.lbl_gst = QLabel()
        self.lbl_disc = QLabel()
        self.lbl_total = QLabel()
        self.lbl_total.setObjectName("TotalPill")
        self.lbl_paid = QLabel()
        self.lbl_change = QLabel()
        for w in (
            self._col(t("subtotal"), self.lbl_sub),
            self._col(t("gst"), self.lbl_gst),
            self._col(t("bill_discount"), self.bill_disc),
            self._col(t("payment"), self.method),
            self._col(t("paid_lbl"), self.paid),
            self.lbl_total,
            self._col(t("change"), self.lbl_change),
        ):
            tl.addWidget(w)
        root.addWidget(totals)

        QShortcut(QKeySequence("Delete"), self, activated=self._remove_line)
        QShortcut(QKeySequence("Escape"), self, activated=self.clear_cart)
        self._apply_section(None)
        self._render_cart()

    def _muted(self, text: str) -> QLabel:
        lab = QLabel(text.upper())
        lab.setObjectName("Muted")
        return lab

    def _col(self, title: str, widget) -> QWidget:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(2)
        lab = QLabel(title.upper())
        lab.setObjectName("Muted")
        lay.addWidget(lab)
        if isinstance(widget, QLabel):
            widget.setObjectName("MoneyText")
        lay.addWidget(widget)
        box._title = lab
        return box

    def _fit_cart_columns(self) -> None:
        header = self.table.horizontalHeader()
        modes = QHeaderView.ResizeMode
        header.setSectionResizeMode(0, modes.Fixed)
        self.table.setColumnWidth(0, 40)
        header.setSectionResizeMode(1, modes.Stretch)
        header.setSectionResizeMode(2, modes.Fixed)
        self.table.setColumnWidth(2, 88)
        header.setSectionResizeMode(3, modes.Fixed)
        self.table.setColumnWidth(3, 52)
        header.setSectionResizeMode(4, modes.Fixed)
        self.table.setColumnWidth(4, 108)
        header.setSectionResizeMode(5, modes.Fixed)
        self.table.setColumnWidth(5, 96)
        header.setSectionResizeMode(6, modes.Fixed)
        self.table.setColumnWidth(6, 112)
        header.setStretchLastSection(False)

    def focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    def has_open_sale(self) -> bool:
        return bool(self.cart)

    def retranslate(self) -> None:
        self.search.setPlaceholderText("Name, generic or barcode   ·   F2")
        self.table.set_headers(["#", t("brand"), t("batch"), t("qty"), t("sale_price"), t("discount"), t("total")])
        self._fit_cart_columns()
        self.add_btn.setText(t("add_to_cart"))
        self.pack_chip.setText(t("sell_one_pack"))
        self.cart_title.setText(t("cart"))
        self.empty_cart.setText(t("pos_cart_hint"))
        if not self._selected:
            self.sel_name.setText(t("pos_pick_hint"))
            self.sel_meta.setText("")
        self.pay_btn.setText(t("checkout"))
        self.print_pay_btn.setText(t("checkout_print"))
        self.hold_btn.setText(t("hold_sale"))
        self.resume_btn.setText(t("resume"))
        self.clear_btn.setText(t("clear"))
        self._refresh_totals()
        self._reload_customers()

    def reload(self) -> None:
        self._reload_customers()

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
        self.qty_lab.setText(qty_labs[kind].upper())
        self.price_lab.setText(price_labs[kind].upper())
        tablet = kind == "tablet"
        self.chip_row.setVisible(tablet)
        self.pack_chip.setVisible(tablet)

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
        first = None
        for kind in ("tablet", "surgical", "liquid", "topical"):
            items = groups.get(kind) or []
            if not items:
                continue
            head = QListWidgetItem(f"──  {titles[kind]}  ──")
            head.setFlags(Qt.ItemFlag.NoItemFlags)
            self.results.addItem(head)
            for m in items:
                if first is None:
                    first = m
                upp = units_per_pack(m)
                each = unit_paisa(int(m.get("sale_paisa") or 0), upp)
                unit = "tab" if kind == "tablet" else "pcs"
                label = (
                    f"{m['brand_name']}   ·   {m['generic_name'] or '—'}     "
                    f"{int(m['stock_qty'] or 0)} {unit}   ·   {format_pkr(each)}"
                )
                row = QListWidgetItem(label)
                row.setData(Qt.ItemDataRole.UserRole, m)
                self.results.addItem(row)
        self._apply_section(first)

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
        batches = stock_service.sellable_batches(med["id"])
        if not batches:
            expired = stock_service.batches_for_medicine(med["id"], include_empty=False)
            error(self, t("expired_block") if expired else t("insufficient_stock"))
            return
        if med.get("controlled"):
            info(self, t("controlled_warn"))
        self._selected = med
        self._batches = batches
        self._apply_section(med)
        self.sel_name.setText(f"{med['brand_name']}")
        generic = med.get("generic_name") or ""
        rack = med.get("rack") or ""
        upp = units_per_pack(med)
        extra = "  ·  ".join(
            p
            for p in (
                generic,
                med.get("category") or "",
                f"{upp} / box" if self._item_kind(med) == "tablet" else "",
                f"Rack {rack}" if rack else "",
                f"{batches[0]['qty']} in stock",
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
        self._refresh_pick_price()

    def _unit_prices(self, batch: dict | None = None) -> tuple[int, int]:
        b = batch or self.batch_box.currentData() or {}
        med = self._selected or {}
        upp = units_per_pack(med)
        sale = int(b.get("sale_paisa") or 0)
        cost = int(b.get("cost_paisa") or 0)
        pack_sale = int(med.get("sale_paisa") or 0)
        if upp > 1 and pack_sale and sale == pack_sale:
            sale = unit_paisa(sale, upp)
            cost = unit_paisa(cost, upp)
        elif upp > 1 and sale > pack_sale // 2 and pack_sale and sale >= pack_sale:
            sale = unit_paisa(sale, upp)
            cost = unit_paisa(cost, upp)
        return sale, cost

    def _set_qty(self, qty: int) -> None:
        self.qty.setValue(max(1, int(qty)))

    def _sell_pack(self) -> None:
        if not self._selected:
            return
        self._set_qty(units_per_pack(self._selected))

    def _refresh_pick_price(self) -> None:
        if not self._selected:
            self.line_total.setText("")
            return
        sale, _cost = self._unit_prices()
        self.price.setValue(from_paisa(sale))
        qty = self.qty.value()
        pct = float(self._selected.get("discount_pct") or 0)
        disc = int(round(sale * qty * pct / 100.0))
        if not self.line_disc.hasFocus():
            self.line_disc.blockSignals(True)
            self.line_disc.setValue(from_paisa(disc))
            self.line_disc.blockSignals(False)
        total = sale * qty - to_paisa(self.line_disc.value())
        self.line_total.setText(f"{t('line_total')}  {format_pkr(max(0, total))}")

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
        if self.qty.value() > b["qty"]:
            error(self, t("insufficient_stock"))
            return
        sale, cost = self._unit_prices(b)
        self.cart.append(
            {
                "medicine_id": self._selected["id"],
                "brand_name": self._selected["brand_name"],
                "batch_id": b["id"],
                "batch_no": b["batch_no"],
                "expiry": b["expiry"],
                "qty": self.qty.value(),
                "unit_price_paisa": sale,
                "cost_paisa": cost,
                "discount_paisa": to_paisa(self.line_disc.value()),
                "gst_pct": self._selected.get("gst_pct") or 0,
            }
        )
        self.search.clear()
        self.results.clear()
        self._selected = None
        self.sel_name.setText(t("pos_pick_hint"))
        self.sel_meta.setText("")
        self._apply_section(None)
        self._render_cart()
        self.search.setFocus()

    def _render_cart(self) -> None:
        self.table.fill(
            [
                [
                    i + 1,
                    x["brand_name"],
                    x["batch_no"],
                    x["qty"],
                    x["unit_price_paisa"],
                    x["discount_paisa"],
                    x["qty"] * x["unit_price_paisa"] - x["discount_paisa"],
                ]
                for i, x in enumerate(self.cart)
            ],
            list(range(len(self.cart))),
            money_cols={4, 5, 6},
        )
        self._fit_cart_columns()
        self._render_chips()
        self._refresh_totals()
        n = len(self.cart)
        self.cart_count.setText(f"{n}")
        self.empty_cart.setVisible(n == 0)
        self.table.setVisible(n > 0)

    def _render_chips(self) -> None:
        while self.chip_layout.count():
            item = self.chip_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for i, x in enumerate(self.cart):
            if not x["discount_paisa"]:
                continue
            btn = QPushButton(f"{x['brand_name']}  −{format_pkr(x['discount_paisa'])}   ×")
            btn.setObjectName("Chip")
            btn.clicked.connect(lambda _, idx=i: self._clear_line_discount(idx))
            self.chip_layout.addWidget(btn)
        if self.bill_disc.value() > 0:
            bill = QPushButton(f"{t('bill_discount')}  −{format_pkr(to_paisa(self.bill_disc.value()))}   ×")
            bill.setObjectName("Chip")
            bill.clicked.connect(self._clear_bill_discount)
            self.chip_layout.addWidget(bill)
        self.chip_layout.addStretch()

    def _clear_bill_discount(self) -> None:
        self.bill_disc.setValue(0)
        self._render_cart()

    def _on_bill_disc(self) -> None:
        self._render_chips()
        self._refresh_totals()

    def _clear_line_discount(self, idx: int) -> None:
        if 0 <= idx < len(self.cart):
            self.cart[idx]["discount_paisa"] = 0
            self._render_cart()

    def _cart_totals(self) -> tuple[int, int, int]:
        subtotal = gst = 0
        for item in self.cart:
            base = item["qty"] * item["unit_price_paisa"] - item["discount_paisa"]
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
        self.lbl_total.setText(f"{t('total')}  {format_pkr(total)}")
        self.lbl_change.setText(format_pkr(change))
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
        if not self.cart:
            error(self, t("cart_empty"))
            return
        method = self.method.currentText()
        customer_id = self.customer.currentData()
        if method == PAYMENT_CREDIT and not customer_id:
            error(self, t("credit_needs_customer"))
            return
        try:
            sid = sale_service.complete_sale(
                self.cart,
                method,
                to_paisa(self.paid.value()),
                customer_id,
                to_paisa(self.bill_disc.value()),
                held_id=self._held_id,
            )
            self.last_sale_id = sid
            sale = sale_service.get_sale(sid)
            show_bill(sale, parent=self, print_now=print_receipt)
            self.clear_cart()
        except Exception as exc:
            error(self, exc)

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
