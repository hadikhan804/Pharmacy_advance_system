from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout

from app.config import APP_SUBTITLE, APP_TITLE
from app.i18n import t
from app.services import user_service
from app.ui.widgets.helpers import error


class LoginWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.user = None
        self.password = None
        self.setObjectName("LoginDialog")
        self.setWindowTitle(APP_TITLE)
        self.setFixedSize(440, 480)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(44, 40, 44, 36)
        root.setSpacing(12)

        mark = QLabel("✚")
        mark.setObjectName("BrandMark")
        mark.setFixedSize(56, 56)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wrap = QVBoxLayout()
        wrap.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        wrap.addWidget(mark, alignment=Qt.AlignmentFlag.AlignHCenter)
        title = QLabel(APP_TITLE)
        title.setObjectName("BrandTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:22px; font-weight:800; color:#ffffff;")
        sub = QLabel(APP_SUBTITLE)
        sub.setObjectName("BrandSub")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wrap.addWidget(title)
        wrap.addWidget(sub)
        root.addLayout(wrap)
        root.addSpacing(16)

        self.user_edit = QLineEdit()
        self.user_edit.setMinimumHeight(42)
        self.user_edit.setPlaceholderText(t("username"))
        self.pass_edit = QLineEdit()
        self.pass_edit.setMinimumHeight(42)
        self.pass_edit.setPlaceholderText(t("password"))
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        root.addWidget(self.user_edit)
        root.addWidget(self.pass_edit)

        btn = QPushButton(t("sign_in"))
        btn.setObjectName("GoldBtn")
        btn.setMinimumHeight(48)
        btn.clicked.connect(self._login)
        self.pass_edit.returnPressed.connect(self._login)
        self.user_edit.returnPressed.connect(self.pass_edit.setFocus)
        root.addWidget(btn)
        root.addStretch()

    def _login(self) -> None:
        user = user_service.authenticate(self.user_edit.text().strip(), self.pass_edit.text())
        if not user:
            error(self, t("invalid_login"))
            return
        self.user = user
        self.password = self.pass_edit.text()
        self.accept()
