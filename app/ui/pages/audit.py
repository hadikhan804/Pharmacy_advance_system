from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from app.i18n import t
from app.services import audit_service
from app.ui.widgets.helpers import DataTable, SearchBar


class AuditPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.search = SearchBar(lambda _: self.reload())
        layout.addWidget(self.search)
        self.table = DataTable([t("time"), t("user"), t("action"), t("details")])
        layout.addWidget(self.table)
        self.reload()

    def retranslate(self) -> None:
        self.search.edit.setPlaceholderText(t("search"))
        self.table.set_headers([t("time"), t("user"), t("action"), t("details")])
        self.reload()

    def reload(self) -> None:
        rows = audit_service.list_logs(search=self.search.edit.text())
        self.table.fill(
            [[r["ts"], r["username"], r["action"], r["details"]] for r in rows],
            [r["id"] for r in rows],
        )
