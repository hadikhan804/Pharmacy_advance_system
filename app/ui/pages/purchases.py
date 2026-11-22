from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.constants import PAYMENT_METHODS
from app.i18n import t
from app.services import medicine_service, purchase_service
from app.ui.widgets.helpers import DataTable, SearchBar, ask, error, info, money_spin, qty_spin, safe_delete
from app.utils.dates import today
from app.utils.money import format_pkr, from_paisa, to_paisa
from app.utils.pack import pack_to_units, unit_paisa, units_per_pack


class PurchasesPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.add_btn = QPushButton(t("new_purchase"))
        self.add_btn.setObjectName("GoldBtn")
        self.pay_btn = QPushButton(t("record_payment"))
        self.ret_btn = QPushButton(t("purchase_return"))
        self.del_btn = QPushButton(t("delete_purchase"))
        self.del_btn.setObjectName("DangerBtn")
        self.add_btn.clicked.connect(self._new)
        self.pay_btn.clicked.connect(self._pay)
        self.ret_btn.clicked.connect(self._return)
        self.del_btn.clicked.connect(self._delete)
        self.search = SearchBar(lambda _: self.reload(), [self.add_btn, self.pay_btn, self.ret_btn, self.del_btn])
        layout.addWidget(self.search)
        self.table = DataTable(self._headers())
        layout.addWidget(self.table)
        self.reload()

    def _headers(self) -> list[str]:
        return [t("date"), t("invoice"), t("company"), t("total"), t("paid"), t("due"), t("status")]

    def retranslate(self) -> None:
        self.add_btn.setText(t("new_purchase"))
        self.pay_btn.setText(t("record_payment"))
        self.ret_btn.setText(t("purchase_return"))
        self.del_btn.setText(t("delete_purchase"))
        self.search.edit.setPlaceholderText(t("search"))
        self.table.set_headers(self._headers())
        self.reload()

    def _delete(self) -> None:
        pid = self.table.selected_id()
        if not pid:
            error(self, t("select_row"))
            return
        p = purchase_service.get_purchase(pid)
        reason = QLineEdit()
        from app.ui.widgets.helpers import form_dialog

        dlg = form_dialog(self, t("delete_purchase"), [(t("reason"), reason)])
        if not dlg.exec():
            return
        if not reason.text().strip():
            error(self, t("required"))
            return
        label = f"{p['supplier_name']} {p.get('invoice_no') or ''} ({format_pkr(p['total_paisa'])})"
        if safe_delete(
            self, label, lambda: purchase_service.delete_purchase(pid, reason.text()), t("delete_purchase_hint")
        ):
            self.reload()

    def reload(self) -> None:
        rows = purchase_service.list_purchases(self.search.edit.text())
        self.table.fill(
            [
                [r["date"], r["invoice_no"], r["supplier_name"], r["total_paisa"], r["paid_paisa"], r["due_paisa"], r["status"]]
                for r in rows
            ],
            [r["id"] for r in rows],
            money_cols={3, 4, 5},
        )

    def _new(self) -> None:
        dlg = PurchaseDialog(self)
        if dlg.exec() and dlg.result_ok:
            self.reload()

    def _pay(self) -> None:
        pid = self.table.selected_id()
        if not pid:
            error(self, t("select_row"))
            return
        amount = money_spin()
        method = QComboBox()
        method.addItems([m for m in PAYMENT_METHODS if m != "Credit"])
        notes = QLineEdit()
        from app.ui.widgets.helpers import form_dialog

        dlg = form_dialog(self, t("record_payment"), [(t("amount"), amount), (t("method"), method), (t("notes"), notes)])
        if dlg.exec():
            try:
                purchase_service.add_payment(pid, to_paisa(amount.value()), method.currentText(), notes.text())
                info(self, t("success"))
                self.reload()
            except Exception as exc:
                error(self, exc)

    def _return(self) -> None:
        pid = self.table.selected_id()
        if not pid:
            error(self, t("select_row"))
            return
        purchase = purchase_service.get_purchase(pid)
        dlg = QDialog(self)
        dlg.setWindowTitle(t("purchase_return"))
        dlg.resize(640, 400)
        box = QVBoxLayout(dlg)
        table = DataTable([t("brand"), t("batch"), t("qty"), t("cost")])
        spins = []
        table.setRowCount(len(purchase["items"]))
        from PySide6.QtWidgets import QTableWidgetItem

        for i, item in enumerate(purchase["items"]):
            table.setItem(i, 0, QTableWidgetItem(item["brand_name"]))
            table.setItem(i, 1, QTableWidgetItem(item["batch_no"]))
            spin = QSpinBox()
            spin.setRange(0, item["qty"])
            table.setCellWidget(i, 2, spin)
            table.setItem(i, 3, QTableWidgetItem(format_pkr(item["cost_paisa"])))
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
            lines = [{"purchase_item_id": iid, "qty": sp.value()} for iid, sp in spins if sp.value() > 0]
            try:
                purchase_service.return_items(pid, lines, reason.text())
                info(self, t("success"))
                self.reload()
            except Exception as exc:
                error(self, exc)


class PurchaseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.result_ok = False
        self.lines: list[dict] = []
        self.setWindowTitle(t("new_purchase"))
        self.resize(980, 600)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        self.supplier = QComboBox()
        self.supplier.setEditable(True)
        self.supplier.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        for c in medicine_service.list_companies(active_only=True):
            self.supplier.addItem(c["name"], c["id"])
        self.supplier.setCurrentIndex(-1)
        if self.supplier.lineEdit():
            self.supplier.lineEdit().setPlaceholderText(t("company_type_or_pick"))
        self.invoice = QLineEdit()
        self.invoice.setPlaceholderText(t("invoice"))
        self.date = QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDate(QDate.currentDate())
        self.paid = money_spin()
        self.notes = QLineEdit()
        self.notes.setPlaceholderText(t("notes"))
        form.addRow(t("company"), self.supplier)
        form.addRow(t("invoice"), self.invoice)
        form.addRow(t("date"), self.date)
        form.addRow(t("paid"), self.paid)
        form.addRow(t("notes"), self.notes)
        layout.addLayout(form)

        self.med = QComboBox()
        self.med.setEditable(True)
        self.med.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.med.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.med.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.med.setMinimumContentsLength(8)
        for m in medicine_service.list_medicines(active_only=True):
            self.med.addItem(f"{m['brand_name']} ({m['generic_name'] or ''})", m["id"])
        completer = self.med.completer()
        if completer:
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        if self.med.lineEdit():
            self.med.lineEdit().setPlaceholderText(t("brand"))
            self.med.lineEdit().returnPressed.connect(self._add_line)
        self.med.currentIndexChanged.connect(self._fill_medicine_prices)
        self.med.setCurrentIndex(-1)

        self.batch = QLineEdit()
        self.batch.setPlaceholderText(t("batch"))
        self.batch.returnPressed.connect(self._add_line)
        self.expiry = QDateEdit()
        self.expiry.setCalendarPopup(True)
        self.expiry.setDate(QDate.currentDate().addYears(2))
        self.qty = qty_spin(1)
        self.qty.setMinimum(1)
        self.qty.setToolTip(t("packs"))
        self.cost = money_spin()
        self.sale = money_spin()
        self.add_btn = QPushButton(t("add"))
        self.add_btn.setObjectName("GoldBtn")
        self.add_btn.clicked.connect(self._add_line)

        self.table = DataTable(
            [t("brand"), t("category"), t("batch"), t("expiry_date"), t("packs"), t("pack_cost"), t("pack_sale"), ""]
        )
        self.table.setSortingEnabled(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        layout.addWidget(self.table, 1)
        self._install_editor_row()
        self._fit_columns()

        save = QPushButton(t("save"))
        save.setObjectName("GoldBtn")
        save.setMinimumHeight(44)
        save.clicked.connect(self._save)
        layout.addWidget(save)

    def _install_editor_row(self) -> None:
        self.table.setRowCount(1)
        self.cat_lab = QLineEdit()
        self.cat_lab.setReadOnly(True)
        self.cat_lab.setPlaceholderText(t("category"))
        for col, widget in enumerate(
            (self.med, self.cat_lab, self.batch, self.expiry, self.qty, self.cost, self.sale, self.add_btn)
        ):
            self.table.setCellWidget(0, col, widget)

    def _fit_columns(self) -> None:
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        widths = {1: 110, 2: 110, 3: 130, 4: 80, 5: 120, 6: 120, 7: 80}
        for col, width in widths.items():
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(col, width)

    def _fill_medicine_prices(self) -> None:
        mid, _brand = self._resolve_medicine()
        if not mid:
            if hasattr(self, "cat_lab"):
                self.cat_lab.clear()
            return
        med = medicine_service.get_medicine(mid) or {}
        if hasattr(self, "cat_lab"):
            self.cat_lab.setText(med.get("category") or "")
        if not self.cost.value():
            self.cost.setValue(from_paisa(int(med.get("cost_paisa") or 0)))
        if not self.sale.value():
            self.sale.setValue(from_paisa(int(med.get("sale_paisa") or 0)))

    def _resolve_medicine(self) -> tuple[int | None, str]:
        mid = self.med.currentData()
        label = self.med.currentText().strip()
        if mid:
            return int(mid), label or self.med.itemText(self.med.currentIndex())
        if not label:
            return None, ""
        for i in range(self.med.count()):
            text = self.med.itemText(i)
            if label.lower() == text.lower() or label.lower() in text.lower():
                return int(self.med.itemData(i)), text
        for m in medicine_service.list_medicines(label, active_only=True):
            if m["brand_name"].lower() == label.lower() or label.lower() in (m["brand_name"] or "").lower():
                return int(m["id"]), m["brand_name"]
        return None, label

    def _resolve_supplier(self):
        """Company id for this purchase. A new name creates the company after confirmation."""
        typed = self.supplier.currentText().strip()
        sid = self.supplier.currentData()
        if sid and self.supplier.itemText(self.supplier.currentIndex()) == typed:
            return sid
        if not typed:
            return None
        for i in range(self.supplier.count()):
            if typed.lower() == self.supplier.itemText(i).lower():
                return self.supplier.itemData(i)
        if not ask(self, t("create_company_q").replace("{name}", typed)):
            return None
        return medicine_service.get_or_create_company(typed)

    def _refresh_table(self) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(1 + len(self.lines))
        if self.table.cellWidget(0, 0) is None:
            self._install_editor_row()
        for r, x in enumerate(self.lines, start=1):
            values = [
                x["brand"],
                x.get("category") or "",
                x["batch_no"],
                x["expiry"],
                f"{x.get('packs', 1)} pk · {x['qty']} tab",
                format_pkr(x.get("pack_cost_paisa", x["cost_paisa"] * x["qty"])),
                format_pkr(x.get("pack_sale_paisa", x["sale_paisa"] * x["qty"])),
                "",
            ]
            for c, text in enumerate(values):
                item = QTableWidgetItem(text)
                if c in (4, 5, 6):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(r, c, item)
        self._fit_columns()

    def _add_line(self) -> bool:
        mid, brand = self._resolve_medicine()
        if not mid:
            error(self, t("purchase_need_medicine"))
            self.med.setFocus()
            return False
        if self.qty.value() < 1:
            error(self, t("purchase_need_qty"))
            return False
        med = medicine_service.get_medicine(mid) or {}
        upp = units_per_pack(med)
        packs = self.qty.value()
        pack_cost = to_paisa(self.cost.value())
        pack_sale = to_paisa(self.sale.value())
        tablets = pack_to_units(packs, upp)
        batch = self.batch.text().strip() or f"B{today().replace('-', '')}-{len(self.lines) + 1}"
        self.lines.append(
            {
                "medicine_id": mid,
                "brand": brand,
                "category": med.get("category") or "",
                "batch_no": batch,
                "expiry": self.expiry.date().toString("yyyy-MM-dd"),
                "packs": packs,
                "qty": tablets,
                "pack_cost_one": pack_cost,
                "pack_sale_one": pack_sale,
                "pack_cost_paisa": pack_cost * packs,
                "pack_sale_paisa": pack_sale * packs,
                "cost_paisa": unit_paisa(pack_cost, upp),
                "sale_paisa": unit_paisa(pack_sale, upp),
            }
        )
        self._refresh_table()
        self.batch.clear()
        self.qty.setValue(1)
        self.med.setCurrentIndex(-1)
        if self.med.lineEdit():
            self.med.lineEdit().clear()
        self.med.setFocus()
        return True

    def _has_pending(self) -> bool:
        return bool(self.med.currentText().strip() or self.batch.text().strip() or self.cost.value() or self.sale.value())

    def _save(self) -> None:
        sid = self._resolve_supplier()
        if not sid:
            error(self, t("purchase_need_supplier"))
            return
        if self._has_pending() or not self.lines:
            if not self._add_line():
                return
        if not self.lines:
            error(self, t("purchase_need_line"))
            return
        try:
            purchase_service.create_purchase(
                sid,
                self.invoice.text(),
                self.date.date().toString("yyyy-MM-dd"),
                self.lines,
                to_paisa(self.paid.value()),
                self.notes.text(),
            )
            self.result_ok = True
            self.accept()
        except Exception as exc:
            error(self, exc)
