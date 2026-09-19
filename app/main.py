from __future__ import annotations

import atexit
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QLockFile
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QMessageBox

from app.auth.session import Session
from app.config import ASSETS_DIR, BASE_DIR, data_dir, resource_dir
from app.db.database import close_db, init_db
from app.i18n import i18n
from app.services import settings_service
from app.ui.icon import app_icon
from app.ui.login_window import LoginWindow
from app.ui.main_window import MainWindow


def _load_style(app: QApplication) -> None:
    qss = resource_dir() / "app" / "ui" / "style.qss"
    if not qss.exists():
        qss = Path(__file__).resolve().parent / "ui" / "style.qss"
    if qss.exists():
        app.setStyleSheet(qss.read_text(encoding="utf-8"))
    families = set(QFontDatabase.families())
    for family in ("Segoe UI", "Noto Naskh Arabic", "Urdu Typesetting", "Tahoma"):
        if family in families:
            app.setFont(QFont(family, 10))
            break
    font_dir = ASSETS_DIR / "fonts"
    if font_dir.exists():
        for file in font_dir.glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(file))


def main() -> None:
    sys.path.insert(0, str(BASE_DIR))
    app = QApplication(sys.argv)
    app.setApplicationName("Yasir Medical Store")
    app.setOrganizationName("Yasir Medical Store")
    app.setWindowIcon(app_icon())
    _load_style(app)

    lock = QLockFile(str(data_dir() / "app.lock"))
    lock.setStaleLockTime(30_000)
    if not lock.tryLock(100):
        QMessageBox.warning(None, "Yasir Medical Store", "The app is already running.")
        sys.exit(0)

    init_db()
    atexit.register(close_db)
    lang = settings_service.get("language", "en") or "en"
    i18n.load(lang)
    if i18n.is_rtl:
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

    login = LoginWindow()
    login.setWindowIcon(app_icon())
    if login.exec() != LoginWindow.DialogCode.Accepted or not login.user:
        sys.exit(0)
    Session.set(login.user, getattr(login, "password", None))

    window = MainWindow()
    window.setWindowIcon(app_icon())
    window.showMaximized()
    sys.exit(app.exec())
