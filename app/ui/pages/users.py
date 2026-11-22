from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QPushButton, QVBoxLayout, QWidget

from app.auth.session import Session
from app.constants import ROLE_CASHIER, ROLE_OWNER
from app.i18n import t
from app.services import user_service
from app.ui.widgets.helpers import DataTable, error, form_dialog, info


class UsersPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.add_btn = QPushButton(t("add"))
        self.add_btn.setObjectName("GoldBtn")
        self.pwd_btn = QPushButton(t("change_password"))
        self.edit_btn = QPushButton(t("edit"))
        self.edit_btn.setObjectName("GhostBtn")
        self.toggle_btn = QPushButton(t("disable_enable"))
        self.toggle_btn.setObjectName("DangerBtn")
        self.add_btn.clicked.connect(lambda: self._edit(None))
        self.pwd_btn.clicked.connect(self._password)
        self.edit_btn.clicked.connect(self._edit_selected)
        self.toggle_btn.clicked.connect(self._toggle)
        row = QWidget()
        from PySide6.QtWidgets import QHBoxLayout

        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(self.add_btn)
        hl.addWidget(self.edit_btn)
        hl.addWidget(self.pwd_btn)
        hl.addWidget(self.toggle_btn)
        hl.addStretch()
        layout.addWidget(row)
        self.table = DataTable([t("username"), t("role"), t("active"), t("date")])
        self.table.doubleClicked.connect(lambda _: self._edit(self.table.selected_id()))
        layout.addWidget(self.table)
        self.reload()

    def _edit_selected(self) -> None:
        uid = self.table.selected_id()
        if not uid:
            error(self, t("select_row"))
            return
        self._edit(uid)

    def _toggle(self) -> None:
        uid = self.table.selected_id()
        if not uid:
            error(self, t("select_row"))
            return
        cur = user_service.get_user(uid)
        if uid == Session.user_id() and cur["active"]:
            error(self, t("cannot_disable_self"))
            return
        try:
            user_service.set_active(uid, not cur["active"])
            info(self, t("success"))
            self.reload()
        except Exception as exc:
            error(self, exc)

    def retranslate(self) -> None:
        self.add_btn.setText(t("add"))
        self.edit_btn.setText(t("edit"))
        self.toggle_btn.setText(t("disable_enable"))
        self.pwd_btn.setText(t("change_password"))
        self.table.set_headers([t("username"), t("role"), t("active"), t("date")])
        self.reload()

    def reload(self) -> None:
        rows = user_service.list_users()
        self.table.fill(
            [[r["username"], t(r["role"]), t("yes") if r["active"] else t("no"), r["created_at"]] for r in rows],
            [r["id"] for r in rows],
        )

    def _edit(self, uid) -> None:
        cur = user_service.get_user(uid) if uid else None
        username = QLineEdit(cur["username"] if cur else "")
        role = QComboBox()
        role.addItem(t("owner"), ROLE_OWNER)
        role.addItem(t("cashier"), ROLE_CASHIER)
        if cur:
            idx = role.findData(cur["role"])
            if idx >= 0:
                role.setCurrentIndex(idx)
        password = QLineEdit()
        password.setEchoMode(QLineEdit.EchoMode.Password)
        active = QCheckBox(t("active"))
        active.setChecked(True if not cur else bool(cur["active"]))
        fields = [(t("username"), username), (t("role"), role)]
        if not uid:
            fields.append((t("password"), password))
        fields.append(("", active))
        dlg = form_dialog(self, t("users"), fields)
        if dlg.exec():
            if not username.text().strip() or (not uid and len(password.text()) < 6):
                error(self, t("required"))
                return
            try:
                if uid:
                    user_service.update_user(uid, username.text(), role.currentData())
                    user_service.set_active(uid, active.isChecked())
                else:
                    user_service.create_user(username.text(), password.text(), role.currentData())
                info(self, t("success"))
                self.reload()
            except Exception as exc:
                error(self, exc)

    def _password(self) -> None:
        uid = self.table.selected_id()
        if not uid:
            error(self, t("select_row"))
            return
        password = QLineEdit()
        password.setEchoMode(QLineEdit.EchoMode.Password)
        confirm = QLineEdit()
        confirm.setEchoMode(QLineEdit.EchoMode.Password)
        dlg = form_dialog(self, t("change_password"), [(t("new_password"), password), (t("confirm_password"), confirm)])
        if dlg.exec():
            if password.text() != confirm.text() or len(password.text()) < 6:
                error(self, t("passwords_mismatch"))
                return
            user_service.change_password(uid, password.text())
            info(self, t("success"))
