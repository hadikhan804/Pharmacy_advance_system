from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QLineEdit, QPushButton, QVBoxLayout, QWidget

from app.i18n import t
from app.services import medicine_service
from app.ui.widgets.helpers import DataTable, SearchBar, error, form_dialog, info


class _NamedEntityPage(QWidget):
    def __init__(self, title_key: str, list_fn, save_fn):
        super().__init__()
        self.title_key = title_key
        self.list_fn = list_fn
        self.save_fn = save_fn
        layout = QVBoxLayout(self)
        self.add_btn = QPushButton(t("add"))
        self.add_btn.setObjectName("GoldBtn")
        self.add_btn.clicked.connect(lambda: self._edit(None))
        self.search = SearchBar(lambda _: self.reload(), [self.add_btn])
        layout.addWidget(self.search)
        self.table = DataTable([t("name"), t("notes"), t("active")])
        self.table.doubleClicked.connect(lambda _: self._edit(self.table.selected_id()))
        layout.addWidget(self.table)
        self.reload()

    def retranslate(self) -> None:
        self.add_btn.setText(t("add"))
        self.search.edit.setPlaceholderText(t("search"))
        self.table.set_headers([t("name"), t("notes"), t("active")])
        self.reload()

    def reload(self) -> None:
        q = self.search.edit.text()
        rows = [r for r in self.list_fn() if q.lower() in r["name"].lower()]
        self.table.fill(
            [[r["name"], r["notes"] or "", "Yes" if r["active"] else "No"] for r in rows],
            [r["id"] for r in rows],
        )

    def _edit(self, entity_id) -> None:
        current = None
        if entity_id:
            current = next((r for r in self.list_fn() if r["id"] == entity_id), None)
        name = QLineEdit(current["name"] if current else "")
        notes = QLineEdit(current["notes"] if current else "")
        active = QCheckBox(t("active"))
        active.setChecked(True if not current else bool(current["active"]))
        dlg = form_dialog(self, t(self.title_key), [(t("name"), name), (t("notes"), notes), ("", active)])
        if dlg.exec():
            if not name.text().strip():
                error(self, t("required"))
                return
            try:
                self.save_fn(name.text(), notes.text(), entity_id, active.isChecked())
                info(self, t("success"))
                self.reload()
            except Exception as exc:
                error(self, exc)


class CompaniesPage(_NamedEntityPage):
    def __init__(self):
        super().__init__("companies", medicine_service.list_companies, medicine_service.save_company)


class FormulationsPage(_NamedEntityPage):
    def __init__(self):
        super().__init__("formulations", medicine_service.list_formulations, medicine_service.save_formulation)
