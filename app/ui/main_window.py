from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
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
from app.ui.pages.medicines import MedicinesPage
from app.ui.pages.payables import PayablesPage
from app.ui.pages.pos import PosPage
from app.ui.pages.purchases import PurchasesPage
from app.ui.pages.reports import ReportsPage
from app.ui.pages.sales import SalesPage
from app.ui.pages.settings import SettingsPage
from app.ui.pages.stock import StockPage
from app.ui.pages.suppliers import SuppliersPage
from app.ui.pages.udhaar import UdhaarPage
from app.ui.pages.users import UsersPage

OWNER_NAV = [
    ("dashboard", "dashboard", "⌂"),
    ("pos", "pos", "▣"),
    ("medicines", "medicines", "💊"),
    ("companies", "companies", "🏭"),
    ("formulations", "formulations", "🧪"),
    ("suppliers", "suppliers", "🚚"),
    ("customers", "customers", "👤"),
    ("stock", "stock", "📦"),
    ("purchases", "purchases", "🧾"),
    ("sales", "sales", "↩"),
    ("udhaar", "udhaar", "💳"),
    ("payables", "payables", "₨"),
    ("expiry", "expiry", "⏰"),
    ("reports", "reports", "📈"),
    ("users", "users", "👥"),
    ("audit", "audit", "📋"),
]


class NavButton(QPushButton):
    def __init__(self, icon: str, text: str):
        super().__init__()
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("NavButton")
        self.setMinimumHeight(44)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 8, 4)
        lay.setSpacing(10)
        self.icon_lab = QLabel(icon)
        self.icon_lab.setObjectName("NavIcon")
        self.icon_lab.setFixedSize(34, 34)
        self.icon_lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_lab = QLabel(text)
        self.text_lab.setObjectName("NavText")
        self.icon_lab.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.text_lab.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        lay.addWidget(self.icon_lab)
        lay.addWidget(self.text_lab, 1)
        self.toggled.connect(self._sync_icon)
        self._sync_icon(False)

    def _sync_icon(self, checked: bool) -> None:
        if checked:
            self.icon_lab.setStyleSheet(
                "background:#6d5efc; color:#ffffff; border-radius:10px; font-size:14px; font-weight:700;"
            )
            self.text_lab.setStyleSheet("background:transparent; color:#ffffff; font-size:13px; font-weight:700;")
        else:
            self.icon_lab.setStyleSheet(
                "background:#181b25; color:#9aa0ae; border-radius:10px; font-size:14px; font-weight:700;"
            )
            self.text_lab.setStyleSheet("background:transparent; color:#b8bcc8; font-size:13px; font-weight:600;")

    def set_label(self, text: str) -> None:
        self.text_lab.setText(text)

    def set_collapsed(self, collapsed: bool) -> None:
        self.text_lab.setVisible(not collapsed)
        self.setToolTip(self.text_lab.text() if collapsed else "")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1360, 860)
        self._nav_buttons: dict[str, NavButton] = {}
        self._collapsed = False

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(248)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(14, 18, 14, 14)
        side.setSpacing(6)

        brand = QFrame()
        brand.setObjectName("BrandBar")
        brand_l = QHBoxLayout(brand)
        brand_l.setContentsMargins(2, 0, 2, 8)
        brand_l.setSpacing(10)
        self.mark = QLabel("✚")
        self.mark.setObjectName("BrandMark")
        self.mark.setFixedSize(36, 36)
        self.mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.brand_title = QLabel(APP_TITLE)
        self.brand_title.setObjectName("BrandTitle")
        self.brand_title.setWordWrap(True)
        self.user_lab = QLabel()
        self.user_lab.setObjectName("UserRole")
        titles.addWidget(self.brand_title)
        titles.addWidget(self.user_lab)
        self.brand_titles = QWidget()
        self.brand_titles.setLayout(titles)
        brand_l.addWidget(self.mark)
        brand_l.addWidget(self.brand_titles, 1)
        side.addWidget(brand)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_wrap = QWidget()
        nav_wrap.setObjectName("Root")
        self.nav_layout = QVBoxLayout(nav_wrap)
        self.nav_layout.setContentsMargins(0, 8, 0, 0)
        self.nav_layout.setSpacing(3)
        scroll.setWidget(nav_wrap)
        side.addWidget(scroll, 1)

        self.stack = QStackedWidget()
        self.pages = {}
        self.pos_page = PosPage()
        factories = {
            "dashboard": lambda: DashboardPage(self.navigate),
            "pos": lambda: self.pos_page,
            "medicines": MedicinesPage,
            "companies": CompaniesPage,
            "formulations": FormulationsPage,
            "suppliers": SuppliersPage,
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
            "settings": lambda: SettingsPage(self.apply_language, self.pos_page.has_open_sale, self.close),
        }

        nav = OWNER_NAV if Session.is_owner() else [("pos", "pos", "▣")]
        for key, label_key, icon in nav:
            btn = NavButton(icon, t(label_key))
            btn.clicked.connect(lambda _, k=key: self.navigate(k))
            self.nav_layout.addWidget(btn)
            self._nav_buttons[key] = btn
            page = factories[key]()
            self.pages[key] = page
            self.stack.addWidget(page)
        self.nav_layout.addStretch()

        if Session.is_owner():
            settings_page = factories["settings"]()
            self.pages["settings"] = settings_page
            self.stack.addWidget(settings_page)
            self.settings_btn = NavButton("⚙", t("settings"))
            self.settings_btn.clicked.connect(lambda: self.navigate("settings"))
            self._nav_buttons["settings"] = self.settings_btn
            side.addWidget(self.settings_btn)
        else:
            self.settings_btn = None

        self.logout_btn = QPushButton(t("logout"))
        self.logout_btn.setObjectName("LogoutBtn")
        self.logout_btn.clicked.connect(self.close)
        side.addWidget(self.logout_btn)

        shell = QFrame()
        shell.setObjectName("ContentShell")
        shell_l = QVBoxLayout(shell)
        shell_l.setContentsMargins(22, 16, 22, 18)
        shell_l.setSpacing(14)

        self.top = QFrame()
        self.top.setObjectName("TopBar")
        top_l = QHBoxLayout(self.top)
        top_l.setContentsMargins(0, 0, 0, 0)
        top_l.setSpacing(10)
        self.menu_btn = QPushButton("☰")
        self.menu_btn.setObjectName("MenuBtn")
        self.menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.menu_btn.setFixedSize(40, 40)
        self.menu_btn.clicked.connect(self._toggle_sidebar)
        self.heading = QLabel()
        self.heading.setObjectName("PageHeading")
        top_l.addWidget(self.menu_btn)
        top_l.addWidget(self.heading)
        top_l.addStretch()
        self.chip_search = self._chip("F2 Search", False)
        self.chip_hold = self._chip("F8 Hold", False)
        self.chip_pay = self._chip("F9 Pay", True)
        self.chip_print = self._chip("F10 Print", False)
        self.chip_search.clicked.connect(self._focus_search)
        self.chip_hold.clicked.connect(self.pos_page._hold)
        self.chip_pay.clicked.connect(self.pos_page._pay)
        self.chip_print.clicked.connect(lambda: self.pos_page._reprint(True))
        for c in (self.chip_search, self.chip_hold, self.chip_pay, self.chip_print):
            top_l.addWidget(c)
        self.notify_btn = QPushButton("🔔")
        self.notify_btn.setObjectName("IconBtn")
        self.notify_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.notify_btn.setFixedSize(40, 40)
        self.notify_btn.clicked.connect(lambda: self.navigate("expiry") if "expiry" in self.pages else None)
        self.avatar = QLabel()
        self.avatar.setObjectName("UserAvatar")
        self.avatar.setFixedSize(32, 32)
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_l.addWidget(self.notify_btn)
        top_l.addWidget(self.avatar)
        shell_l.addWidget(self.top)
        shell_l.addWidget(self.stack, 1)

        outer.addWidget(self.sidebar)
        outer.addWidget(shell, 1)

        QShortcut(QKeySequence("F2"), self, activated=self._focus_search)
        QShortcut(QKeySequence("F8"), self, activated=self.pos_page._hold)
        QShortcut(QKeySequence("F9"), self, activated=self.pos_page._pay)
        QShortcut(QKeySequence("F10"), self, activated=lambda: self.pos_page._reprint(True))

        self._refresh_user()
        self.navigate("dashboard" if Session.is_owner() else "pos")

    def _chip(self, text: str, gold: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("ChipGold" if gold else "Chip")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    def _refresh_user(self) -> None:
        user = Session.current()
        if not user:
            self.user_lab.setText("")
            self.avatar.setText("?")
            return
        self.user_lab.setText(f"{user.username} / {t(user.role)}")
        self.avatar.setText((user.username or "U")[:1].upper())

    def _toggle_sidebar(self) -> None:
        self._collapsed = not self._collapsed
        self.sidebar.setFixedWidth(76 if self._collapsed else 248)
        self.brand_titles.setVisible(not self._collapsed)
        self.logout_btn.setVisible(not self._collapsed)
        for btn in self._nav_buttons.values():
            btn.set_collapsed(self._collapsed)

    def _focus_search(self) -> None:
        self.navigate("pos")
        self.pos_page.focus_search()

    def navigate(self, key: str, extra: dict | None = None) -> None:
        if key not in self.pages:
            return
        for k, btn in self._nav_buttons.items():
            btn.setChecked(k == key)
        self.stack.setCurrentWidget(self.pages[key])
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
        event.accept()

    def apply_language(self, lang: str) -> None:
        i18n.load(lang)
        rtl = Qt.LayoutDirection.RightToLeft if i18n.is_rtl else Qt.LayoutDirection.LeftToRight
        self.setLayoutDirection(rtl)
        self.sidebar.setLayoutDirection(rtl)
        self.setWindowTitle(t("app_title"))
        self.brand_title.setText(t("app_title"))
        self._refresh_user()
        for key, btn in self._nav_buttons.items():
            btn.set_label(t(key))
            btn.set_collapsed(self._collapsed)
        self.logout_btn.setText(t("logout"))
        self.heading.setText(t(self._current_key()))
        for page in self.pages.values():
            if hasattr(page, "retranslate"):
                page.retranslate()

    def _current_key(self) -> str:
        current = self.stack.currentWidget()
        for k, p in self.pages.items():
            if p is current:
                return k
        return "pos"
