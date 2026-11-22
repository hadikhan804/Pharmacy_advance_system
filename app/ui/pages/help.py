from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QTextBrowser, QVBoxLayout, QWidget

from app.config import data_dir, resource_dir
from app.i18n import t


def guide_path() -> Path:
    bundled = resource_dir() / "app" / "docs" / "user_guide.md"
    if bundled.exists():
        return bundled
    return Path(__file__).resolve().parents[2] / "docs" / "user_guide.md"


class HelpPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.data_btn = QPushButton(t("open_folder") + " — data")
        self.data_btn.setObjectName("GhostBtn")
        self.data_btn.clicked.connect(self._open_data)
        row.addWidget(self.data_btn)
        row.addStretch()
        layout.addLayout(row)
        self.view = QTextBrowser()
        self.view.setObjectName("HelpView")
        self.view.setOpenExternalLinks(True)
        layout.addWidget(self.view, 1)
        self._load()

    def _load(self) -> None:
        path = guide_path()
        text = path.read_text(encoding="utf-8") if path.exists() else "# User guide\n\nThe guide file is missing. Call 03716931861."
        self.view.document().setDefaultStyleSheet(
            "h1{color:#f5c84c} h2{color:#a99cff;margin-top:18px} table{border-collapse:collapse}"
            " td,th{border:1px solid #2a2d3a;padding:4px 8px} code,pre{background:#14161f;color:#f5c84c}"
        )
        self.view.setMarkdown(text)

    def _open_data(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir())))

    def retranslate(self) -> None:
        self.data_btn.setText(t("open_folder") + " — data")
