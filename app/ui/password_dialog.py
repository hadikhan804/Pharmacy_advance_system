from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QMessageBox, QVBoxLayout

from app.auth.session import Session
from app.i18n import t
from app.services import user_service


class PasswordDialog(QDialog):
    def __init__(self, parent=None, forced: bool = False):
        super().__init__(parent)
        self.setWindowTitle(t("change_password"))
        self.setModal(True)
        layout = QVBoxLayout(self)
        if forced:
            layout.addWidget(QLabel(t("must_change_password")))
        form = QFormLayout()
        self.new = QLineEdit()
        self.new.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(t("new_password"), self.new)
        form.addRow(t("confirm_password"), self.confirm)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        if forced:
            buttons.button(QDialogButtonBox.StandardButton.Cancel).hide()
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        a, b = self.new.text(), self.confirm.text()
        if len(a) < 6:
            QMessageBox.warning(self, t("error"), t("password_too_short"))
            return
        if a != b:
            QMessageBox.warning(self, t("error"), t("passwords_mismatch"))
            return
        user = Session.current()
        if user:
            user_service.change_password(user.id, a)
            user.must_change_password = False
            Session.backup_secret = a
        self.accept()
