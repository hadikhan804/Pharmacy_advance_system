from __future__ import annotations

import atexit
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QLockFile, QTimer
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication, QMessageBox, QStyleFactory

from app.auth.session import Session
from app.config import APP_TITLE, ASSETS_DIR, BASE_DIR, data_dir, prepare_data_dir, resource_dir
from app.db.database import close_db, init_db
from app.i18n import i18n
from app.services import settings_service
from app.ui.icon import app_icon
from app.ui.login_window import LoginWindow
from app.ui.main_window import MainWindow


def _dark_palette() -> QPalette:
    pal = QPalette()
    role = QPalette.ColorRole
    group = QPalette.ColorGroup
    colors = {
        role.Window: "#0b0d12",
        role.WindowText: "#f4f5f7",
        role.Base: "#14161f",
        role.AlternateBase: "#101219",
        role.ToolTipBase: "#1b1e2a",
        role.ToolTipText: "#f4f5f7",
        role.PlaceholderText: "#8b8e9a",
        role.Text: "#f4f5f7",
        role.Button: "#191c27",
        role.ButtonText: "#f4f5f7",
        role.BrightText: "#ffffff",
        role.Light: "#2a2e3d",
        role.Midlight: "#222634",
        role.Mid: "#1a1d28",
        role.Dark: "#07080c",
        role.Shadow: "#000000",
        role.Highlight: "#6d5efc",
        role.HighlightedText: "#ffffff",
        role.Link: "#a79bff",
        role.LinkVisited: "#c4b5fd",
    }
    for r, c in colors.items():
        pal.setColor(r, QColor(c))
    for r in (role.WindowText, role.Text, role.ButtonText):
        pal.setColor(group.Disabled, r, QColor("#6b6f7c"))
    return pal


def _load_style(app: QApplication) -> None:
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setPalette(_dark_palette())
    font_dir = ASSETS_DIR / "fonts"
    if font_dir.exists():
        for file in font_dir.glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(file))
    families = set(QFontDatabase.families())
    family = "Segoe UI" if "Segoe UI" in families else "Tahoma"
    if i18n.is_rtl:
        for name in ("Noto Naskh Arabic", "Urdu Typesetting", "Tahoma"):
            if name in families:
                family = name
                break
    app.setFont(QFont(family, 10))
    qss = resource_dir() / "app" / "ui" / "style.qss"
    if not qss.exists():
        qss = Path(__file__).resolve().parent / "ui" / "style.qss"
    if qss.exists():
        app.setStyleSheet(qss.read_text(encoding="utf-8"))


def main() -> None:
    sys.path.insert(0, str(BASE_DIR))
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setOrganizationName(APP_TITLE)
    app.setWindowIcon(app_icon())
    _load_style(app)

    lock = QLockFile(str(data_dir() / "app.lock"))
    lock.setStaleLockTime(30_000)
    if not lock.tryLock(100):
        QMessageBox.warning(None, APP_TITLE, "The app is already running.")
        sys.exit(0)

    try:
        prepared = prepare_data_dir()
    except OSError as exc:
        prepared = {"action": "error", "source": str(exc)}
    init_db()
    atexit.register(close_db)
    from app.services import backup_service

    backup_service.normalize_settings()
    backup_service.mirror_now(force=True)
    from app.services import docs_service

    docs_service.write_folder_docs()
    if prepared.get("action") == "restored_mirror":
        QMessageBox.information(
            None,
            APP_TITLE,
            "Your previous shop data was found and restored.\n\n"
            f"From: {prepared.get('source')}\nNow saved in: {data_dir()}",
        )
    elif prepared.get("action") == "migrated":
        QMessageBox.information(
            None,
            APP_TITLE,
            f"Shop data moved into the data folder:\n{data_dir()}",
        )
    elif prepared.get("action") == "error":
        QMessageBox.warning(None, APP_TITLE, f"Could not prepare the data folder:\n{prepared.get('source')}")
    lang = settings_service.get("language", "en") or "en"
    i18n.load(lang)
    if i18n.is_rtl:
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

    login = LoginWindow()
    login.setWindowIcon(app_icon())
    if login.exec() != LoginWindow.DialogCode.Accepted or not login.user:
        sys.exit(0)
    Session.set(login.user, getattr(login, "password", None))

    closed = None
    try:
        from app.services import period_service

        closed = period_service.maybe_close_previous_month(Session.user_id())
    except Exception:
        closed = None

    window = MainWindow()
    window.setWindowIcon(app_icon())
    window.showMaximized()
    if closed and not closed.get("already"):
        QMessageBox.information(window, i18n.t("period_closed"), f"{closed.get('period_key', '')}")

    def _after_start() -> None:
        backup_service.auto_daily_if_needed()
        from app.ui import launch_alerts

        try:
            launch_alerts.maybe_show(window, window.navigate)
        except Exception:
            pass

    QTimer.singleShot(800, _after_start)
    mirror_timer = QTimer(window)
    mirror_timer.timeout.connect(lambda: backup_service.mirror_now())
    mirror_timer.start(backup_service.MIRROR_EVERY_SECONDS * 1000)
    sys.exit(app.exec())
