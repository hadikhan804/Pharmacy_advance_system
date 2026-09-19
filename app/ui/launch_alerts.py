from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout

from app.i18n import t
from app.services import stock_service


class LaunchAlertDialog(QDialog):
    def __init__(self, parent, navigate, exp_n: int, low_n: int):
        super().__init__(parent)
        self.navigate = navigate
        self.setWindowTitle(t("app_title"))
        self.setModal(True)
        layout = QVBoxLayout(self)
        msg = t("launch_alert").replace("{exp}", str(exp_n)).replace("{low}", str(low_n))
        lab = QLabel(msg)
        lab.setWordWrap(True)
        layout.addWidget(lab)
        if exp_n:
            btn_e = QPushButton(t("expiry"))
            btn_e.setObjectName("GoldBtn")
            btn_e.clicked.connect(lambda: self._go("expiry", {"week": True}))
            layout.addWidget(btn_e)
        if low_n:
            btn_l = QPushButton(t("low_stock"))
            btn_l.clicked.connect(lambda: self._go("stock", {"low": True}))
            layout.addWidget(btn_l)
        close = QPushButton(t("cancel"))
        close.setObjectName("GhostBtn")
        close.clicked.connect(self.accept)
        layout.addWidget(close)

    def _go(self, page: str, extra: dict) -> None:
        self.navigate(page, extra)
        self.accept()


def maybe_show(parent, navigate) -> None:
    exp = stock_service.expiring_within(7)
    low = stock_service.low_stock()
    if not exp and not low:
        return
    LaunchAlertDialog(parent, navigate, len(exp), len(low)).exec()
