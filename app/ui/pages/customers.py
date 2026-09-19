from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QLineEdit, QPushButton, QVBoxLayout, QWidget

from app.i18n import t
from app.services import customer_service
from app.ui.widgets.helpers import DataTable, SearchBar, error, form_dialog, info
from app.utils.money import format_pkr


class CustomersPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.add_btn = QPushButton(t("add"))
        self.add_btn.setObjectName("GoldBtn")
        self.add_btn.clicked.connect(lambda: self._edit(None))
        self.search = SearchBar(lambda _: self.reload(), [self.add_btn])
        layout.addWidget(self.search)
        self.table = DataTable([t("name"), t("cnic"), t("phone"), t("address"), t("balance"), t("active")])
        self.table.doubleClicked.connect(lambda _: self._edit(self.table.selected_id()))
        layout.addWidget(self.table)
        self.reload()

    def retranslate(self) -> None:
        self.add_btn.setText(t("add"))
        self.search.edit.setPlaceholderText(t("search"))
        self.table.set_headers([t("name"), t("cnic"), t("phone"), t("address"), t("balance"), t("active")])
        self.reload()

    def reload(self) -> None:
        rows = customer_service.list_customers(self.search.edit.text())
        self.table.fill(
            [
                [r["name"], r["cnic"], r["phone"], r["address"], format_pkr(r["balance_paisa"]), "Yes" if r["active"] else "No"]
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
