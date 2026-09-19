from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.i18n import t
from app.services import dashboard_service
from app.utils.money import format_pkr


class ClickCard(QFrame):
    def __init__(self, title: str, on_click=None):
        super().__init__()
        self.setObjectName("Card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._on_click = on_click
        box = QVBoxLayout(self)
        box.setContentsMargins(18, 16, 18, 16)
        box.setSpacing(6)
        self.title_lab = QLabel(title)
        self.title_lab.setObjectName("CardTitle")
        self.value = QLabel("—")
        self.value.setObjectName("CardValue")
        box.addWidget(self.title_lab)
        box.addWidget(self.value)

    def mousePressEvent(self, event) -> None:
        if self._on_click:
            self._on_click()
        super().mousePressEvent(event)


class DashboardPage(QWidget):
    def __init__(self, navigate):
        super().__init__()
        self.navigate = navigate
        self.cards: dict[str, ClickCard] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(16)

        hero = QHBoxLayout()
        hero.setSpacing(12)
        for key, label_key, page in (
            ("month_sale", "month_sale", "reports"),
            ("month_profit", "month_profit", "reports"),
        ):
            card = ClickCard(t(label_key), lambda p=page: navigate(p))
            self.cards[key] = card
            hero.addWidget(card, 1)
        self.add_btn = QPushButton("+  " + t("add"))
        self.add_btn.setObjectName("GoldBtn")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setMinimumWidth(120)
        self.add_btn.setMinimumHeight(72)
        self.add_btn.clicked.connect(lambda: navigate("medicines"))
        hero.addWidget(self.add_btn)
        layout.addLayout(hero)

        kpi = QHBoxLayout()
        kpi.setSpacing(12)
        for key, label_key, page, extra in (
            ("stock_sale", "stock_value_sale", "stock", None),
            ("expiring_soon", "expiring_soon", "expiry", None),
            ("low_stock", "low_stock", "stock", {"low": True}),
            ("backup", "last_backup", "settings", None),
        ):
            card = ClickCard(t(label_key), lambda p=page, e=extra: navigate(p, e or {}))
            self.cards[key] = card
            kpi.addWidget(card, 1)
        layout.addLayout(kpi)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.q_pos = QPushButton(t("quick_pos"))
        self.q_pos.setObjectName("ChipGold")
        self.q_pur = QPushButton(t("quick_purchase"))
        self.q_pur.setObjectName("Chip")
        self.q_exp = QPushButton(t("quick_expiry"))
        self.q_exp.setObjectName("Chip")
        self.q_rep = QPushButton(t("quick_reports"))
        self.q_rep.setObjectName("Chip")
        self.q_pos.clicked.connect(lambda: navigate("pos"))
        self.q_pur.clicked.connect(lambda: navigate("purchases"))
        self.q_exp.clicked.connect(lambda: navigate("expiry"))
        self.q_rep.clicked.connect(lambda: navigate("reports"))
        for b in (self.q_pos, self.q_pur, self.q_exp, self.q_rep):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setMinimumHeight(40)
            actions.addWidget(b)
        actions.addStretch()
        layout.addLayout(actions)

        more = QGridLayout()
        more.setSpacing(12)
        extras = [
            ("today_sale", "today_sale", "reports"),
            ("today_profit", "today_profit", "reports"),
            ("week_sale", "week_sale", "reports"),
            ("week_profit", "week_profit", "reports"),
            ("year_sale", "year_sale", "reports"),
            ("year_profit", "year_profit", "reports"),
            ("stock_cost", "stock_value_cost", "stock"),
            ("udhaar", "total_udhaar", "udhaar"),
            ("payables", "total_payables", "payables"),
        ]
        for i, (key, label_key, page) in enumerate(extras):
            card = ClickCard(t(label_key), lambda p=page: navigate(p))
            self.cards[key] = card
            more.addWidget(card, i // 3, i % 3)
        layout.addLayout(more)
        layout.addStretch()
        self.reload()

    def retranslate(self) -> None:
        labels = {
            "today_sale": "today_sale",
            "today_profit": "today_profit",
            "week_sale": "week_sale",
            "week_profit": "week_profit",
            "month_sale": "month_sale",
            "month_profit": "month_profit",
            "year_sale": "year_sale",
            "year_profit": "year_profit",
            "stock_cost": "stock_value_cost",
            "stock_sale": "stock_value_sale",
            "expiring_soon": "expiring_soon",
            "low_stock": "low_stock",
            "udhaar": "total_udhaar",
            "payables": "total_payables",
            "backup": "last_backup",
        }
        for key, label_key in labels.items():
            self.cards[key].title_lab.setText(t(label_key))
        self.add_btn.setText("+  " + t("add"))
        self.q_pos.setText(t("quick_pos"))
        self.q_pur.setText(t("quick_purchase"))
        self.q_exp.setText(t("quick_expiry"))
        self.q_rep.setText(t("quick_reports"))

    def reload(self) -> None:
        d = dashboard_service.summary()
        self.cards["today_sale"].value.setText(format_pkr(d["today"]["sale"]))
        self.cards["today_profit"].value.setText(format_pkr(d["today"]["profit"]))
        self.cards["week_sale"].value.setText(format_pkr(d["week"]["sale"]))
        self.cards["week_profit"].value.setText(format_pkr(d["week"]["profit"]))
        self.cards["month_sale"].value.setText(format_pkr(d["month"]["sale"]))
        self.cards["month_profit"].value.setText(format_pkr(d["month"]["profit"]))
        self.cards["year_sale"].value.setText(format_pkr(d["year"]["sale"]))
        self.cards["year_profit"].value.setText(format_pkr(d["year"]["profit"]))
        self.cards["stock_cost"].value.setText(format_pkr(d["stock_cost"]))
        self.cards["stock_sale"].value.setText(format_pkr(d["stock_sale"]))
        self.cards["expiring_soon"].value.setText(str(d["expiring_soon"]))
        self.cards["low_stock"].value.setText(str(d["low_stock"]))
        self.cards["udhaar"].value.setText(format_pkr(d["udhaar"]))
        self.cards["payables"].value.setText(format_pkr(d["payables"]))
        bak = d.get("backup") or {}
        self.cards["backup"].value.setText(bak.get("last_verified") or "—")
        if bak.get("warning"):
            self.cards["backup"].value.setStyleSheet("color:#f87171; font-size:16px; font-weight:800;")
        else:
            self.cards["backup"].value.setStyleSheet("")
