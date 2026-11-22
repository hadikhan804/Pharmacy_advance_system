from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QLineEdit, QPushButton, QVBoxLayout, QWidget

from app.i18n import t
from app.services import customer_service
from app.ui.widgets.helpers import DataTable, SearchBar, action_button, ask, error, form_dialog, info, safe_delete
from app.utils.money import format_pkr


class CustomersPage(QWidget):
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
        self.table = DataTable([t("name"), t("cnic"), t("phone"), t("address"), t("balance"), t("active")])
        self.table.doubleClicked.connect(lambda _: self._edit_selected())
        layout.addWidget(self.table)
        self.reload()

    def _edit_selected(self) -> None:
        cid = self.table.selected_id()
        if not cid:
            error(self, t("select_row"))
            return
        self._edit(cid)

    def _delete(self) -> None:
        cid = self.table.selected_id()
        if not cid:
            error(self, t("select_row"))
            return
        cur = customer_service.get_customer(cid)
        if safe_delete(self, cur["name"], lambda: customer_service.delete_customer(cid)):
            self.reload()

    def retranslate(self) -> None:
        self.add_btn.setText(t("add"))
        self.edit_btn.setText(t("edit"))
        self.del_btn.setText(t("delete"))
        self.search.edit.setPlaceholderText(t("search"))
        self.table.set_headers([t("name"), t("cnic"), t("phone"), t("address"), t("balance"), t("active")])
        self.reload()

    def reload(self) -> None:
        rows = customer_service.list_customers(self.search.edit.text())
        if not self.show_del.isChecked():
            rows = [r for r in rows if r["active"]]
        self.table.fill(
            [
                [
                    r["name"] if r["active"] else f"{r['name']}  ({t('archived')})",
                    r["cnic"],
                    r["phone"],
                    r["address"],
                    format_pkr(r["balance_paisa"]),
                    t("yes") if r["active"] else t("no"),
                ]
                for r in rows
            ],
            [r["id"] for r in rows],
        )

    def _edit(self, cid) -> None:
        cur = customer_service.get_customer(cid) if cid else None
        name = QLineEdit(cur["name"] if cur else "")
        cnic = QLineEdit(cur["cnic"] if cur else "")
        phone = QLineEdit(cur["phone"] if cur else "")
        address = QLineEdit(cur["address"] if cur else "")
        notes = QLineEdit(cur["notes"] if cur else "")
        active = QCheckBox(t("active"))
        active.setChecked(True if not cur else bool(cur["active"]))
        dlg = form_dialog(
            self,
            t("customers"),
            [
                (t("name"), name),
                (t("cnic"), cnic),
                (t("phone"), phone),
                (t("address"), address),
                (t("notes"), notes),
                ("", active),
            ],
        )
        if dlg.exec():
            if not name.text().strip():
                error(self, t("required"))
                return
            if not cid:
                dup = [
                    c for c in customer_service.list_customers()
                    if c["name"].strip().lower() == name.text().strip().lower()
                    and (c.get("phone") or "") == phone.text().strip()
                ]
                if dup and not ask(self, t("duplicate_customer")):
                    return
            try:
                customer_service.save_customer(
                    {
                        "name": name.text(),
                        "cnic": cnic.text(),
                        "phone": phone.text(),
                        "address": address.text(),
                        "notes": notes.text(),
                        "active": active.isChecked(),
                    },
                    cid,
                )
                info(self, t("success"))
                self.reload()
            except Exception as exc:
                error(self, exc)
