from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.auth.session import Session
from app.config import APP_TITLE
from app.i18n import i18n, t
from app.ui.pages.audit import AuditPage
from app.ui.pages.companies import CompaniesPage
from app.ui.pages.customers import CustomersPage
from app.ui.pages.dashboard import DashboardPage
from app.ui.pages.expiry import ExpiryPage
from app.ui.pages.formulations import FormulationsPage
from app.ui.pages.help import HelpPage
from app.ui.pages.medicines import MedicinesPage
from app.ui.pages.payables import PayablesPage
from app.ui.pages.pos import PosPage
from app.ui.pages.purchases import PurchasesPage
from app.ui.pages.reports import ReportsPage
from app.ui.pages.sales import SalesPage
from app.ui.pages.settings import SettingsPage
from app.ui.pages.stock import StockPage
from app.ui.pages.udhaar import UdhaarPage
from app.ui.pages.users import UsersPage
from app.ui.widgets.helpers import FlowLayout, scroll_wrap

UNWRAPPED_PAGES = {"pos", "settings", "help"}

OWNER_NAV = [
    "dashboard",
    "pos",
    "medicines",
    "stock",
    "purchases",
    "sales",
    "customers",
    "companies",
    "formulations",
    "udhaar",
    "payables",
    "expiry",
    "reports",
    "users",
    "audit",
    "settings",
    "help",
]

NAV_SHORT = {
    "dashboard": "Home",
    "pos": "POS",
    "medicines": "Medicines",
    "stock": "Stock",
    "purchases": "Purchases",
    "sales": "Sales",
    "customers": "Customers",
    "companies": "Companies",
    "formulations": "Forms",
    "udhaar": "Udhaar",
    "payables": "Payables",
    "expiry": "Expiry",
    "reports": "Reports",
    "users": "Users",
    "audit": "Audit",
    "settings": "Settings",
    "help": "Help",
}


def _nav_label(key: str) -> str:
    return t(f"nav_{key}") if t(f"nav_{key}") != f"nav_{key}" else NAV_SHORT.get(key, t(key))


def _fit_btn(btn: QPushButton) -> None:
    btn.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    btn.setMinimumHeight(30)
    btn.adjustSize()
    btn.setMinimumWidth(max(52, btn.sizeHint().width()))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1360, 860)
        self.setMinimumSize(1024, 680)
        self._nav_buttons: dict[str, QPushButton] = {}
        self._holders: dict[str, QWidget] = {}

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QFrame()
        header.setObjectName("AppHeader")
        header_l = QVBoxLayout(header)
        header_l.setContentsMargins(12, 8, 12, 8)
        header_l.setSpacing(8)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        self.mark = QLabel("✚")
        self.mark.setObjectName("BrandMark")
        self.mark.setFixedSize(32, 32)
        self.mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand_title = QLabel(APP_TITLE)
        self.brand_title.setObjectName("BrandTitle")
        self.brand_title.setWordWrap(False)
        self.user_lab = QLabel()
        self.user_lab.setObjectName("UserRole")
        self.user_lab.setWordWrap(False)
        brand_row.addWidget(self.mark)
        brand_row.addWidget(self.brand_title)
        brand_row.addWidget(self.user_lab)
        brand_row.addStretch()
        self.chip_search = self._chip("F2")
        self.chip_hold = self._chip("F8")
        self.chip_pay = self._chip("F9", gold=True)
        self.chip_print = self._chip("F10")
        self.chip_search.setToolTip("Search")
        self.chip_hold.setToolTip("Hold")
        self.chip_pay.setToolTip("Pay")
        self.chip_print.setToolTip("Print")
        for c in (self.chip_search, self.chip_hold, self.chip_pay, self.chip_print):
            brand_row.addWidget(c)
        self.notify_btn = QPushButton("🔔")
        self.notify_btn.setObjectName("IconBtn")
        self.notify_btn.setFixedSize(36, 36)
        self.notify_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.avatar = QLabel()
        self.avatar.setObjectName("UserAvatar")
        self.avatar.setFixedSize(32, 32)
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logout_btn = QPushButton(t("logout"))
        self.logout_btn.setObjectName("LogoutBtn")
        _fit_btn(self.logout_btn)
        brand_row.addWidget(self.notify_btn)
        brand_row.addWidget(self.avatar)
        brand_row.addWidget(self.logout_btn)
        header_l.addLayout(brand_row)

        nav_wrap = QWidget()
        nav_wrap.setObjectName("TopNavBar")
        self.nav_layout = FlowLayout(nav_wrap, spacing=6)
        header_l.addWidget(nav_wrap)
        outer.addWidget(header)

        self.stack = QStackedWidget()
        self.pages = {}
        self.pos_page = PosPage()
        factories = {
            "dashboard": lambda: DashboardPage(self.navigate),
            "pos": lambda: self.pos_page,
            "medicines": MedicinesPage,
            "companies": CompaniesPage,
            "formulations": FormulationsPage,
            "customers": CustomersPage,
            "stock": StockPage,
            "purchases": PurchasesPage,
            "sales": SalesPage,
            "udhaar": UdhaarPage,
            "payables": PayablesPage,
            "expiry": ExpiryPage,
            "reports": ReportsPage,
            "users": UsersPage,
            "audit": AuditPage,
            "help": HelpPage,
            "settings": lambda: SettingsPage(self.apply_language, self.pos_page.has_open_sale, self.close),
        }

        keys = OWNER_NAV if Session.is_owner() else ["pos", "stock", "sales", "reports", "help"]
        for key in keys:
            btn = QPushButton(_nav_label(key))
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setObjectName("TopNav")
            btn.setAutoExclusive(True)
            _fit_btn(btn)
            btn.clicked.connect(lambda _, k=key: self.navigate(k))
            self.nav_layout.addWidget(btn)
            self._nav_buttons[key] = btn
            self._add_page(key, factories[key]())

        if Session.is_owner() and "settings" not in self.pages:
            self._add_page("settings", factories["settings"]())

        self.notify_btn.clicked.connect(lambda: self.navigate("expiry") if "expiry" in self.pages else None)
        self.logout_btn.clicked.connect(self.close)
        self.chip_search.clicked.connect(self._focus_search)
        self.chip_hold.clicked.connect(lambda: self._pos_action(self.pos_page._hold))
        self.chip_pay.clicked.connect(lambda: self._pos_action(lambda: self.pos_page._pay(True)))
        self.chip_print.clicked.connect(lambda: self._pos_action(lambda: self.pos_page._reprint(True)))

        shell = QFrame()
        shell.setObjectName("ContentShell")
        shell_l = QVBoxLayout(shell)
        shell_l.setContentsMargins(12, 8, 12, 8)
        shell_l.setSpacing(8)
        self.heading = QLabel()
        self.heading.setObjectName("PageHeading")
        self.heading.setWordWrap(False)
        self.heading.hide()
        shell_l.addWidget(self.heading)
        shell_l.addWidget(self.stack, 1)
        outer.addWidget(shell, 1)

        QShortcut(QKeySequence("F2"), self, activated=self._focus_search)
        QShortcut(QKeySequence("F1"), self, activated=lambda: self.navigate("help"))
        QShortcut(QKeySequence("F8"), self, activated=lambda: self._pos_action(self.pos_page._hold))
        QShortcut(QKeySequence("F9"), self, activated=lambda: self._pos_action(lambda: self.pos_page._pay(True)))
        QShortcut(QKeySequence("F10"), self, activated=lambda: self._pos_action(lambda: self.pos_page._reprint(True)))

        self._refresh_user()
        self.navigate("dashboard" if Session.is_owner() else "pos")

    def _add_page(self, key: str, page: QWidget) -> None:
        self.pages[key] = page
        holder = page if key in UNWRAPPED_PAGES else scroll_wrap(page)
        self._holders[key] = holder
        self.stack.addWidget(holder)

    def _chip(self, text: str, gold: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("ChipGold" if gold else "Chip")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(32)
        btn.setMinimumWidth(44)
        return btn

    def _refresh_user(self) -> None:
        user = Session.current()
        if not user:
            self.user_lab.setText("")
            self.avatar.setText("?")
            return
        self.user_lab.setText(f"{user.username} / {t(user.role)}")
        self.avatar.setText((user.username or "U")[:1].upper())

    def _pos_action(self, action) -> None:
        if self._current_key() != "pos" or QApplication.activeModalWidget() is not None:
            return
        action()

    def _focus_search(self) -> None:
        self.navigate("pos")
        self.pos_page.focus_search()

    def navigate(self, key: str, extra: dict | None = None) -> None:
        if key not in self.pages:
            return
        for k, btn in self._nav_buttons.items():
            btn.setChecked(k == key)
        self.stack.setCurrentWidget(self._holders[key])
        self.heading.setText(t(key))
        show_pos = key == "pos"
        for c in (self.chip_search, self.chip_hold, self.chip_pay, self.chip_print):
            c.setVisible(show_pos)
        page = self.pages[key]
        if extra and hasattr(page, "apply_filter"):
            page.apply_filter(extra)
        elif hasattr(page, "reload"):
            page.reload()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.pos_page.has_open_sale():
            if QMessageBox.question(self, t("confirm"), t("cart_open_close")) != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        try:
            from app.services import backup_service

            backup_service.event_backup("close")
        except Exception:
            pass
        try:
            from app.services import docs_service

            docs_service.write_folder_docs()
        except Exception:
            pass
        event.accept()

    def apply_language(self, lang: str) -> None:
        i18n.load(lang)
        rtl = Qt.LayoutDirection.RightToLeft if i18n.is_rtl else Qt.LayoutDirection.LeftToRight
        self.setLayoutDirection(rtl)
        self.setWindowTitle(t("app_title"))
        self.brand_title.setText(t("app_title"))
        self._refresh_user()
        for key, btn in self._nav_buttons.items():
            btn.setText(_nav_label(key))
            _fit_btn(btn)
        self.logout_btn.setText(t("logout"))
        _fit_btn(self.logout_btn)
        self.heading.setText(t(self._current_key()))
        for page in self.pages.values():
            if hasattr(page, "retranslate"):
                page.retranslate()

    def _current_key(self) -> str:
        current = self.stack.currentWidget()
        for k, p in self._holders.items():
            if p is current:
                return k
        return "pos"
