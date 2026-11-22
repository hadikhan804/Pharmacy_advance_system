from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.constants import CATEGORIES
from app.i18n import t
from app.services import medicine_service, settings_service
from app.ui.widgets.helpers import (
    DataTable,
    PriceSlot,
    SearchBar,
    action_button,
    bind_arrow_nav,
    error,
    info,
    money_spin,
    safe_delete,
)
from app.utils.money import format_pkr, from_paisa, to_paisa
from app.utils.pack import charge_paisa, pack_to_units, unit_paisa, units_per_pack

_UNIT_FROM_CAT = {
    "Tablet": "Tab",
    "Capsule": "Cap",
    "Syrup": "Syp",
    "Suspension": "Syp",
    "Injection": "Inj",
    "Infusion": "Inj",
    "Cream": "Crm",
    "Ointment": "Oint",
    "Drops": "Drops",
    "Inhaler": "Other",
    "Sachet": "Sachet",
    "Bottle": "Bottle",
}


def _editable_combo(values: list[str], current: str = "", placeholder: str = "") -> QComboBox:
    box = QComboBox()
    box.setEditable(True)
    box.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    box.addItems(values)
    if placeholder:
        box.lineEdit().setPlaceholderText(placeholder)
    if current:
        idx = box.findText(current)
        if idx >= 0:
            box.setCurrentIndex(idx)
        else:
            box.setEditText(current)
    elif values:
        box.setCurrentIndex(-1)
        box.setEditText("")
    return box


class MedicinesPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.add_btn = QPushButton(t("add"))
        self.add_btn.setObjectName("GoldBtn")
        self.add_btn.clicked.connect(lambda: self._edit(None))
        self.tpl_btn = QPushButton(t("excel_template"))
        self.tpl_btn.setObjectName("GhostBtn")
        self.imp_btn = QPushButton(t("import_excel"))
        self.imp_btn.setObjectName("GhostBtn")
        self.tpl_btn.clicked.connect(self._template)
        self.imp_btn.clicked.connect(self._import)
        self.edit_btn = action_button(t("edit"))
        self.del_btn = action_button(t("delete"), "DangerBtn")
        self.edit_btn.clicked.connect(self._edit_selected)
        self.del_btn.clicked.connect(self._delete)
        self.show_del = QCheckBox(t("show_deleted"))
        self.show_del.toggled.connect(lambda _: self.reload())
        self.search = SearchBar(
            lambda _: self.reload(), [self.show_del, self.add_btn, self.edit_btn, self.del_btn, self.tpl_btn, self.imp_btn]
        )
        layout.addWidget(self.search)
        self.table = DataTable(
            [
                t("brand"),
                t("generic"),
                t("company"),
                t("category"),
                t("cost"),
                t("sale_price"),
                t("rack"),
                t("qty"),
                t("reorder_level"),
            ]
        )
        self.table.doubleClicked.connect(lambda _: self._edit_selected())
        layout.addWidget(self.table)
        self.reload()

    def _edit_selected(self) -> None:
        mid = self.table.selected_id()
        if not mid:
            error(self, t("select_row"))
            return
        self._edit(mid)

    def _delete(self) -> None:
        mid = self.table.selected_id()
        if not mid:
            error(self, t("select_row"))
            return
        med = medicine_service.get_medicine(mid)
        use = medicine_service.medicine_usage(mid)
        detail = t("delete_medicine_hint")
        if use["stock"]:
            detail += "\n" + t("delete_has_stock").replace("{n}", str(use["stock"]))
        if safe_delete(self, med["brand_name"], lambda: medicine_service.delete_medicine(mid), detail):
            self.reload()

    def retranslate(self) -> None:
        self.add_btn.setText(t("add"))
        self.edit_btn.setText(t("edit"))
        self.del_btn.setText(t("delete"))
        self.tpl_btn.setText(t("excel_template"))
        self.imp_btn.setText(t("import_excel"))
        self.show_del.setText(t("show_deleted"))
        self.search.edit.setPlaceholderText(t("search"))
        self.table.set_headers(
            [
                t("brand"),
                t("generic"),
                t("company"),
                t("category"),
                t("cost"),
                t("sale_price"),
                t("rack"),
                t("qty"),
                t("reorder_level"),
            ]
        )
        self.reload()

    def reload(self) -> None:
        rows = medicine_service.list_medicines(self.search.edit.text())
        if not self.show_del.isChecked():
            rows = [r for r in rows if r["active"]]
        self.table.fill(
            [
                [
                    r["brand_name"] if r["active"] else f"{r['brand_name']}  ({t('archived')})",
                    r["generic_name"],
                    r["company_name"],
                    r.get("category") or "",
                    r.get("cost_paisa") or 0,
                    r.get("sale_paisa") or 0,
                    r.get("rack") or "",
                    r["stock_qty"],
                    r["reorder_level"],
                ]
                for r in rows
            ],
            [r["id"] for r in rows],
            money_cols={4, 5},
        )

    def _edit(self, medicine_id) -> None:
        current = medicine_service.get_medicine(medicine_id) if medicine_id else None
        dlg = QDialog(self)
        dlg.setWindowTitle(t("add") if not current else t("edit"))
        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry().height() if screen else 800
        dlg.resize(560, min(760, max(520, avail - 80)))
        dlg.setMinimumSize(480, 420)
        outer = QVBoxLayout(dlg)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form = QGridLayout(inner)
        form.setSpacing(10)
        form.setColumnStretch(0, 1)
        form.setColumnStretch(1, 1)

        brand = QLineEdit(current["brand_name"] if current else "")
        brand.setPlaceholderText("e.g. Panadol Extra")
        generic = QLineEdit(current["generic_name"] if current else "")
        generic.setPlaceholderText("e.g. Paracetamol")

        companies = [c["name"] for c in medicine_service.list_companies(True)]
        formulations = [f["name"] for f in medicine_service.list_formulations(True)]
        company = _editable_combo(companies, current["company_name"] if current else "", "Type company name")
        form_u = _editable_combo(
            formulations,
            current["formulation_name"] if current else "",
            "e.g. Paracetamol 500mg",
        )
        cat = QComboBox()
        cat.addItems(list(CATEGORIES))
        if current and current.get("category"):
            idx = cat.findText(current["category"])
            if idx >= 0:
                cat.setCurrentIndex(idx)
            else:
                cat.addItem(current["category"])
                cat.setCurrentText(current["category"])
        else:
            cat.setCurrentIndex(0)

        boxes = QSpinBox()
        boxes.setRange(0, 1_000_000)
        boxes.setValue(0)
        per_box = QSpinBox()
        per_box.setRange(1, 100_000)
        per_box.setValue(units_per_pack(current) if current else 500)
        cost = money_spin(from_paisa(current.get("cost_paisa") or 0) if current else 0)
        sale = money_spin(from_paisa(current.get("sale_paisa") or 0) if current else 0)
        tab_cost = money_spin()
        tab_sale = money_spin()
        profit = QLabel("—")
        profit.setObjectName("CardValue")
        profit.setWordWrap(True)
        rack = QLineEdit(current.get("rack") or "" if current else "")
        rack.setPlaceholderText("e.g. A-12")
        batch = QLineEdit()
        batch.setPlaceholderText("Batch no.")
        reorder = QSpinBox()
        reorder.setRange(0, 1_000_000)
        reorder.setValue(current["reorder_level"] if current else 0)
        discount = QSpinBox()
        discount.setRange(0, 100)
        discount.setSuffix(" %")
        discount.setValue(int(float(current.get("discount_pct") or 0)) if current else 0)
        expiry = QDateEdit()
        expiry.setCalendarPopup(True)
        expiry.setDisplayFormat("yyyy-MM-dd")
        expiry.setDate(QDate.currentDate().addYears(2))

        def _labeled(title: str, widget) -> QWidget:
            wrap = QWidget()
            box = QVBoxLayout(wrap)
            box.setContentsMargins(0, 0, 0, 0)
            box.setSpacing(4)
            lab = QLabel(title)
            lab.setObjectName("Muted")
            box.addWidget(lab)
            box.addWidget(widget)
            return wrap

        def _refresh_profit() -> None:
            upp = max(1, per_box.value())
            s, c = to_paisa(sale.value()), to_paisa(cost.value())
            tabs = pack_to_units(boxes.value(), upp)
            tab_cost.blockSignals(True)
            tab_sale.blockSignals(True)
            tab_cost.setValue(from_paisa(unit_paisa(c, upp)))
            tab_sale.setValue(from_paisa(unit_paisa(s, upp)))
            tab_cost.blockSignals(False)
            tab_sale.blockSignals(False)
            profit.setText(
                f"{t('profit')}: {format_pkr(s - c)} / {t('packs')}\n"
                f"{t('price_per_tablet')}: {format_pkr(unit_paisa(s, upp))}   ·   "
                f"{t('profit')}: {format_pkr(unit_paisa(s, upp) - unit_paisa(c, upp))} / tab\n"
                f"{tabs} {t('tablets')}  ·  {t('check_pack')}: {format_pkr(charge_paisa(s, upp, tabs))}"
            )

        for w in (boxes, per_box, cost, sale):
            w.valueChanged.connect(lambda _: _refresh_profit())
        _refresh_profit()

        cost_slot = PriceSlot(t("cost_price"), cost)
        sale_slot = PriceSlot(t("sale_price_box"), sale)
        tab_cost_slot = PriceSlot(t("cost_per_tablet"), tab_cost, readonly=True)
        tab_sale_slot = PriceSlot(t("sale_per_tablet"), tab_sale, readonly=True)

        form.addWidget(_labeled(t("brand"), brand), 0, 0)
        form.addWidget(_labeled(t("generic"), generic), 0, 1)
        form.addWidget(_labeled(t("company"), company), 1, 0)
        form.addWidget(_labeled(t("formulation"), form_u), 1, 1)
        form.addWidget(_labeled(t("category"), cat), 2, 0, 1, 2)
        form.addWidget(_labeled(t("stock_size"), boxes), 3, 0)
        form.addWidget(_labeled(t("pack_size"), per_box), 3, 1)
        form.addWidget(cost_slot, 4, 0)
        form.addWidget(sale_slot, 4, 1)
        form.addWidget(tab_cost_slot, 5, 0)
        form.addWidget(tab_sale_slot, 5, 1)
        form.addWidget(profit, 6, 0, 1, 2)
        form.addWidget(_labeled(t("rack"), rack), 7, 0)
        form.addWidget(_labeled(t("batch"), batch), 7, 1)
        form.addWidget(_labeled(t("reorder_level"), reorder), 8, 0)
        form.addWidget(_labeled(t("discount_pct"), discount), 8, 1)
        form.addWidget(_labeled(t("expiry_date"), expiry), 9, 0, 1, 2)

        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        save_btn.setDefault(False)
        save_btn.setAutoDefault(False)
        outer.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        dlg._arrow_nav = bind_arrow_nav(
            [brand, generic, company, form_u, cat, boxes, per_box, cost, sale, rack, batch, reorder, discount, expiry],
            dlg,
        )
        brand.setFocus()
        brand.selectAll()

        if dlg.exec():
            if not brand.text().strip() or not cat.currentText().strip():
                error(self, t("required"))
                return
            sale_p, cost_p = to_paisa(sale.value()), to_paisa(cost.value())
            upp = max(1, per_box.value())
            data = {
                "brand_name": brand.text(),
                "generic_name": generic.text(),
                "company_id": medicine_service.get_or_create_company(company.currentText()),
                "formulation_id": medicine_service.get_or_create_formulation(form_u.currentText()),
                "category": cat.currentText().strip(),
                "unit": _UNIT_FROM_CAT.get(cat.currentText().strip(), "Other"),
                "pack_size": str(upp),
                "units_per_pack": upp,
                "gst_pct": settings_service.default_gst(),
                "barcode": "",
                "controlled": False,
                "reorder_level": reorder.value(),
                "active": True,
                "discount_pct": discount.value(),
                "rack": rack.text(),
                "sale_paisa": sale_p,
                "cost_paisa": cost_p,
                "opening_qty": pack_to_units(boxes.value(), upp),
                "batch_no": batch.text(),
                "expiry": expiry.date().toString("yyyy-MM-dd"),
            }
            try:
                medicine_service.save_medicine(data, medicine_id)
                info(self, t("success"))
                self.reload()
            except Exception as exc:
                error(self, exc)

    def _template(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, t("excel_template"), "medicines_template.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        medicine_service.write_import_template(path)
        info(self, t("success"))

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, t("import_excel"), "", "Excel (*.xlsx)")
        if not path:
            return
        result = medicine_service.import_from_excel(path)
        msg = f"Imported {result['imported']}"
        if result["errors"]:
            msg += "\n" + "\n".join(result["errors"][:12])
        if result["ok"]:
            info(self, msg)
        else:
            error(self, msg)
        self.reload()
