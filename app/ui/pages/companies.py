from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QPushButton, QVBoxLayout, QWidget

from app.constants import PAYMENT_METHODS
from app.i18n import t
from app.services import medicine_service, supplier_service
from app.ui.widgets.helpers import DataTable, SearchBar, action_button, error, form_dialog, info, money_spin, safe_delete
from app.utils.money import format_pkr, to_paisa


def _archived(name: str, active) -> str:
    return name if active else f"{name}  ({t('archived')})"


class CompaniesPage(QWidget):
    """Companies are the suppliers: purchases, dues and payments all belong to a company."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.add_btn = action_button(t("add"), "GoldBtn")
        self.edit_btn = action_button(t("edit"))
        self.pay_btn = action_button(t("pay_company"))
        self.del_btn = action_button(t("delete"), "DangerBtn")
        self.add_btn.clicked.connect(lambda: self._edit(None))
        self.edit_btn.clicked.connect(self._edit_selected)
        self.pay_btn.clicked.connect(self._pay)
        self.del_btn.clicked.connect(self._delete)
        self.show_del = QCheckBox(t("show_deleted"))
        self.show_del.toggled.connect(lambda _: self.reload())
        self.search = SearchBar(lambda _: self.reload(), [self.show_del, self.add_btn, self.edit_btn, self.pay_btn, self.del_btn])
        layout.addWidget(self.search)
        self.table = DataTable(self._headers())
        self.table.doubleClicked.connect(lambda _: self._edit_selected())
        layout.addWidget(self.table)
        self.reload()

    def _headers(self) -> list[str]:
        return [t("company"), t("phone"), t("address"), t("medicines"), t("total_payables"), t("active")]

    def retranslate(self) -> None:
        self.add_btn.setText(t("add"))
        self.edit_btn.setText(t("edit"))
        self.pay_btn.setText(t("pay_company"))
        self.del_btn.setText(t("delete"))
        self.search.edit.setPlaceholderText(t("search"))
        self.table.set_headers(self._headers())
        self.reload()

    def reload(self) -> None:
        rows = medicine_service.list_companies_full(self.search.edit.text())
        if not self.show_del.isChecked():
            rows = [r for r in rows if r["active"]]
        self._rows = {r["id"]: r for r in rows}
        self.table.fill(
            [
                [
                    _archived(r["name"], r["active"]),
                    r.get("phone") or "",
                    r.get("address") or "",
                    r["medicine_count"],
                    format_pkr(r["payable_paisa"]),
                    t("yes") if r["active"] else t("no"),
                ]
                for r in rows
            ],
            [r["id"] for r in rows],
        )

    def _selected(self):
        cid = self.table.selected_id()
        if not cid:
            error(self, t("select_row"))
        return cid

    def _edit_selected(self) -> None:
        cid = self._selected()
        if cid:
            self._edit(cid)

    def _edit(self, company_id) -> None:
        cur = self._rows.get(company_id) if company_id else None
        name = QLineEdit(cur["name"] if cur else "")
        phone = QLineEdit((cur or {}).get("phone") or "")
        address = QLineEdit((cur or {}).get("address") or "")
        notes = QLineEdit((cur or {}).get("notes") or "")
        active = QCheckBox(t("active"))
        active.setChecked(True if not cur else bool(cur["active"]))
        dlg = form_dialog(
            self,
            t("company"),
            [(t("name"), name), (t("phone"), phone), (t("address"), address), (t("notes"), notes), ("", active)],
        )
        if dlg.exec():
            try:
                medicine_service.save_company(
                    name.text(), notes.text(), company_id, active.isChecked(), phone.text(), address.text()
                )
                info(self, t("success"))
                self.reload()
            except Exception as exc:
                error(self, exc)

    def _pay(self) -> None:
        cid = self._selected()
        if not cid:
            return
        due = supplier_service.company_payable(cid)
        if due <= 0:
            info(self, t("nothing_due"))
            return
        amount = money_spin(due / 100.0)
        method = QComboBox()
        method.addItems([m for m in PAYMENT_METHODS if m != "Credit"])
        notes = QLineEdit()
        dlg = form_dialog(
            self,
            f"{t('pay_company')} — {self._rows[cid]['name']}  ({format_pkr(due)})",
            [(t("amount"), amount), (t("method"), method), (t("notes"), notes)],
        )
        if dlg.exec():
            try:
                supplier_service.record_payment(cid, to_paisa(amount.value()), method.currentText(), notes.text())
                info(self, t("success"))
                self.reload()
            except Exception as exc:
                error(self, exc)

    def _delete(self) -> None:
        cid = self._selected()
        if not cid:
            return
        row = self._rows[cid]
        detail = t("delete_company_hint")
        if safe_delete(self, row["name"], lambda: medicine_service.delete_company(cid), detail):
            self.reload()


class FormulationsPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.add_btn = action_button(t("add"), "GoldBtn")
        self.edit_btn = action_button(t("edit"))
        self.del_btn = action_button(t("delete"), "DangerBtn")
        self.add_btn.clicked.connect(lambda: self._edit(None))
        self.edit_btn.clicked.connect(self._edit_selected)
        self.del_btn.clicked.connect(self._delete)
        self.show_del = QCheckBox(t("show_deleted"))
        self.show_del.toggled.connect(lambda _: self.reload())
        self.search = SearchBar(lambda _: self.reload(), [self.show_del, self.add_btn, self.edit_btn, self.del_btn])
        layout.addWidget(self.search)
        self.table = DataTable([t("name"), t("notes"), t("active")])
        self.table.doubleClicked.connect(lambda _: self._edit_selected())
        layout.addWidget(self.table)
        self.reload()

    def retranslate(self) -> None:
        self.add_btn.setText(t("add"))
        self.edit_btn.setText(t("edit"))
        self.del_btn.setText(t("delete"))
        self.search.edit.setPlaceholderText(t("search"))
        self.table.set_headers([t("name"), t("notes"), t("active")])
        self.reload()

    def reload(self) -> None:
        q = self.search.edit.text().lower()
        rows = [r for r in medicine_service.list_formulations() if q in r["name"].lower()]
        if not self.show_del.isChecked():
            rows = [r for r in rows if r["active"]]
        self._rows = {r["id"]: r for r in rows}
        self.table.fill(
            [[_archived(r["name"], r["active"]), r["notes"] or "", t("yes") if r["active"] else t("no")] for r in rows],
            [r["id"] for r in rows],
        )

    def _edit_selected(self) -> None:
        fid = self.table.selected_id()
        if not fid:
            error(self, t("select_row"))
            return
        self._edit(fid)

    def _edit(self, fid) -> None:
        cur = self._rows.get(fid) if fid else None
        name = QLineEdit(cur["name"] if cur else "")
        notes = QLineEdit((cur or {}).get("notes") or "")
        active = QCheckBox(t("active"))
        active.setChecked(True if not cur else bool(cur["active"]))
        dlg = form_dialog(self, t("formulations"), [(t("name"), name), (t("notes"), notes), ("", active)])
        if dlg.exec():
            if not name.text().strip():
                error(self, t("required"))
                return
            try:
                medicine_service.save_formulation(name.text(), notes.text(), fid, active.isChecked())
                info(self, t("success"))
                self.reload()
            except Exception as exc:
                error(self, exc)

    def _delete(self) -> None:
        fid = self.table.selected_id()
        if not fid:
            error(self, t("select_row"))
            return
        if safe_delete(self, self._rows[fid]["name"], lambda: medicine_service.delete_formulation(fid)):
            self.reload()
