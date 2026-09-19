from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget

from app.i18n import t
from app.services import supplier_service
from app.ui.widgets.helpers import DataTable, SearchBar, error, form_dialog, info
from app.utils.money import format_pkr


class SuppliersPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.add_btn = QPushButton(t("add"))
        self.add_btn.setObjectName("GoldBtn")
        self.add_btn.clicked.connect(lambda: self._edit(None))
        self.search = SearchBar(lambda _: self.reload(), [self.add_btn])
        layout.addWidget(self.search)
        self.table = DataTable([t("name"), t("phone"), t("address"), t("total_payables"), t("active")])
        self.table.doubleClicked.connect(lambda _: self._edit(self.table.selected_id()))
        layout.addWidget(self.table)
        self.reload()

    def retranslate(self) -> None:
        self.add_btn.setText(t("add"))
        self.search.edit.setPlaceholderText(t("search"))
        self.table.set_headers([t("name"), t("phone"), t("address"), t("total_payables"), t("active")])
        self.reload()

    def reload(self) -> None:
        rows = supplier_service.list_suppliers(self.search.edit.text())
        self.table.fill(
            [
                [r["name"], r["phone"], r["address"], format_pkr(r["payable_paisa"]), "Yes" if r["active"] else "No"]
                for r in rows
            ],
            [r["id"] for r in rows],
        )

    def _edit(self, sid) -> None:
        cur = supplier_service.get_supplier(sid) if sid else None
        name = QLineEdit(cur["name"] if cur else "")
        phone = QLineEdit(cur["phone"] if cur else "")
        address = QLineEdit(cur["address"] if cur else "")
        notes = QLineEdit(cur["notes"] if cur else "")
        active = QCheckBox(t("active"))
        active.setChecked(True if not cur else bool(cur["active"]))
        dlg = form_dialog(
            self,
            t("suppliers"),
            [(t("name"), name), (t("phone"), phone), (t("address"), address), (t("notes"), notes), ("", active)],
        )
        if dlg.exec():
            if not name.text().strip():
                error(self, t("required"))
                return
            try:
                supplier_service.save_supplier(
                    {
                        "name": name.text(),
                        "phone": phone.text(),
                        "address": address.text(),
                        "notes": notes.text(),
                        "active": active.isChecked(),
                    },
                    sid,
                )
                info(self, t("success"))
                self.reload()
            except Exception as exc:
                error(self, exc)
