from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
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
from app.ui.widgets.helpers import DataTable, SearchBar, error, info, money_spin
from app.utils.money import format_pkr, from_paisa, to_paisa
from app.utils.pack import pack_to_units, unit_paisa, units_per_pack

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
        self.search = SearchBar(lambda _: self.reload(), [self.add_btn, self.tpl_btn, self.imp_btn])
        layout.addWidget(self.search)
        self.table = DataTable(
            [
                t("brand"),
                t("generic"),
                t("company"),
                t("sale_price"),
                t("cost"),
                t("rack"),
                t("qty"),
                t("reorder_level"),
            ]
        )
        self.table.doubleClicked.connect(lambda _: self._edit(self.table.selected_id()))
        layout.addWidget(self.table)
        self.reload()

    def retranslate(self) -> None:
        self.add_btn.setText(t("add"))
        self.tpl_btn.setText(t("excel_template"))
        self.imp_btn.setText(t("import_excel"))
        self.search.edit.setPlaceholderText(t("search"))
        self.table.set_headers(
            [
                t("brand"),
                t("generic"),
                t("company"),
                t("sale_price"),
                t("cost"),
                t("rack"),
                t("qty"),
                t("reorder_level"),
            ]
        )
        self.reload()

    def reload(self) -> None:
        rows = medicine_service.list_medicines(self.search.edit.text())
        self.table.fill(
            [
                [
                    r["brand_name"],
                    r["generic_name"],
                    r["company_name"],
                    r.get("sale_paisa") or 0,
                    r.get("cost_paisa") or 0,
                    r.get("rack") or "",
                    r["stock_qty"],
                    r["reorder_level"],
                ]
                for r in rows
            ],
            [r["id"] for r in rows],
            money_cols={3, 4},
        )

    def _edit(self, medicine_id) -> None:
        current = medicine_service.get_medicine(medicine_id) if medicine_id else None
        dlg = QDialog(self)
        dlg.setWindowTitle(t("add") if not current else t("edit"))
        dlg.resize(560, 760)
        outer = QVBoxLayout(dlg)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form = QFormLayout(inner)
        form.setSpacing(8)

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
        cat = _editable_combo(list(CATEGORIES), current["category"] if current else "", "Tablet / Syrup / ...")
        if current and current.get("category"):
            cat.setEditText(current["category"])

        boxes = QSpinBox()
        boxes.setRange(0, 1_000_000)
        boxes.setValue(0)
        per_box = QSpinBox()
        per_box.setRange(1, 100_000)
        per_box.setValue(units_per_pack(current) if current else 1)
        cost = money_spin(from_paisa(current.get("cost_paisa") or 0) if current else 0)
        sale = money_spin(from_paisa(current.get("sale_paisa") or 0) if current else 0)
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

        def _refresh_profit() -> None:
            upp = max(1, per_box.value())
            s, c = to_paisa(sale.value()), to_paisa(cost.value())
            tabs = pack_to_units(boxes.value(), upp)
            profit.setText(
                f"{t('profit')}: {format_pkr(s - c)} / box\n"
                f"{t('price_per_tablet')}: {format_pkr(unit_paisa(s, upp))}   ·   "
                f"{t('profit')}: {format_pkr(unit_paisa(s, upp) - unit_paisa(c, upp))} / tab\n"
                f"{t('tablets')} to stock: {tabs}"
            )

        for w in (boxes, per_box, cost, sale):
            w.valueChanged.connect(lambda _: _refresh_profit())
        _refresh_profit()

        for label, w in [
            (t("brand"), brand),
            (t("generic"), generic),
            (t("company"), company),
            (t("formulation"), form_u),
            (t("category"), cat),
            (t("stock_size"), boxes),
            (t("pack_size"), per_box),
            (t("cost_price"), cost),
            (t("sale_price_box"), sale),
            (t("profit"), profit),
            (t("rack"), rack),
            (t("batch"), batch),
            (t("reorder_level"), reorder),
            (t("discount_pct"), discount),
            (t("expiry_date"), expiry),
        ]:
            form.addRow(label, w)

        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        outer.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)

        if dlg.exec():
            if not brand.text().strip():
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
