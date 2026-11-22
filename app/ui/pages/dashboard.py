from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from app.i18n import t
from app.services import dashboard_service, period_service
from app.ui.widgets.helpers import FlowLayout, error, info
from app.utils.money import format_pkr

CARD_MIN_W = 210
CARD_MIN_H = 92


class ClickCard(QFrame):
    def __init__(self, title: str, on_click=None, accent: str = "", big: bool = False):
        super().__init__()
        self.setObjectName("Card")
        if accent:
            self.setProperty("accent", accent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._on_click = on_click
        self.setMinimumSize(CARD_MIN_W, CARD_MIN_H)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        box = QVBoxLayout(self)
        box.setContentsMargins(16, 12, 16, 12)
        box.setSpacing(4)
        self.title_lab = QLabel(title)
        self.title_lab.setObjectName("CardTitle")
        self.title_lab.setWordWrap(False)
        self.value = QLabel("—")
        self.value.setObjectName("CardValue")
        self.value.setWordWrap(False)
        font = QFont(self.value.font())
        font.setPointSize(18 if big else 15)
        font.setBold(True)
        self.value.setFont(font)
        box.addWidget(self.title_lab)
        box.addWidget(self.value)
        box.addStretch()

    def mousePressEvent(self, event) -> None:
        if self._on_click:
            self._on_click()
        super().mousePressEvent(event)


class CardGrid(QWidget):
    """Grid that picks its column count from the available width."""

    def __init__(self, cards: list[QWidget], max_cols: int = 4):
        super().__init__()
        self.cards = cards
        self.max_cols = max_cols
        self._cols = 0
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(12)
        self._place(max_cols)

    def _place(self, cols: int) -> None:
        if cols == self._cols:
            return
        self._cols = cols
        for c in self.cards:
            self.grid.removeWidget(c)
        for i, c in enumerate(self.cards):
            self.grid.addWidget(c, i // cols, i % cols)
        for col in range(self.max_cols):
            self.grid.setColumnStretch(col, 1 if col < cols else 0)

    def resizeEvent(self, event) -> None:
        cols = max(1, min(self.max_cols, (event.size().width() + 12) // (CARD_MIN_W + 12)))
        self._place(cols)
        super().resizeEvent(event)


def _section(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setObjectName("SectionTitle")
    return lab


class DashboardPage(QWidget):
    def __init__(self, navigate):
        super().__init__()
        self.navigate = navigate
        self.cards: dict[str, ClickCard] = {}
        self.sections: dict[str, QLabel] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 8, 8)
        layout.setSpacing(12)

        period = QFrame()
        period.setObjectName("PeriodStrip")
        pl = QHBoxLayout(period)
        pl.setContentsMargins(14, 10, 14, 10)
        pl.setSpacing(10)
        self.period_badge = QLabel()
        self.period_badge.setObjectName("PeriodBadge")
        self.period_lab = QLabel()
        self.period_lab.setObjectName("PeriodText")
        self.period_lab.setWordWrap(True)
        self.close_btn = QPushButton(t("close_month"))
        self.close_btn.setObjectName("GoldBtn")
        self.close_btn.clicked.connect(self._close_month)
        self.q_month = QPushButton(t("this_month"))
        self.q_month.setObjectName("GhostBtn")
        self.q_month.clicked.connect(lambda: navigate("reports"))
        pl.addWidget(self.period_badge)
        pl.addWidget(self.period_lab, 1)
        pl.addWidget(self.q_month)
        pl.addWidget(self.close_btn)
        layout.addWidget(period)

        actions_w = QWidget()
        actions = FlowLayout(actions_w, spacing=8)
        self.q_pos = QPushButton(t("quick_pos"))
        self.q_pos.setObjectName("GoldBtn")
        self.add_btn = QPushButton("+  " + t("add"))
        self.q_pur = QPushButton(t("quick_purchase"))
        self.q_exp = QPushButton(t("quick_expiry"))
        self.q_rep = QPushButton(t("quick_reports"))
        for b in (self.add_btn, self.q_pur, self.q_exp, self.q_rep):
            b.setObjectName("GhostBtn")
        self.q_pos.clicked.connect(lambda: navigate("pos"))
        self.add_btn.clicked.connect(lambda: navigate("medicines"))
        self.q_pur.clicked.connect(lambda: navigate("purchases"))
        self.q_exp.clicked.connect(lambda: navigate("expiry", {"months6": True}))
        self.q_rep.clicked.connect(lambda: navigate("reports"))
        for b in (self.q_pos, self.add_btn, self.q_pur, self.q_exp, self.q_rep):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setMinimumHeight(38)
            actions.addWidget(b)
        layout.addWidget(actions_w)

        groups = [
            (
                "sec_sales",
                [
                    ("month_sale", "month_sale", "reports", None, "purple", True),
                    ("month_profit", "month_profit", "reports", None, "green", True),
                    ("today_sale", "today_sale", "reports", None, "", False),
                    ("today_profit", "today_profit", "reports", None, "", False),
                    ("week_sale", "week_sale", "reports", None, "", False),
                    ("week_profit", "week_profit", "reports", None, "", False),
                    ("year_sale", "year_sale", "reports", None, "", False),
                    ("year_profit", "year_profit", "reports", None, "", False),
                ],
            ),
            (
                "sec_stock",
                [
                    ("stock_sale", "stock_value_sale", "stock", None, "", False),
                    ("stock_cost", "stock_value_cost", "stock", None, "", False),
                    ("expiring_soon", "expiring_soon", "expiry", {"months6": True}, "gold", False),
                    ("low_stock", "low_stock", "stock", {"low": True}, "red", False),
                ],
            ),
            (
                "sec_money",
                [
                    ("udhaar", "total_udhaar", "udhaar", None, "", False),
                    ("payables", "total_payables", "payables", None, "", False),
                    ("backup", "last_backup", "settings", None, "", False),
                ],
            ),
        ]
        self._labels: dict[str, str] = {}
        for sec_key, items in groups:
            head = _section(t(sec_key))
            self.sections[sec_key] = head
            layout.addWidget(head)
            cards = []
            for key, label_key, page, extra, accent, big in items:
                card = ClickCard(t(label_key), lambda p=page, e=extra: navigate(p, e) if e else navigate(p), accent, big)
                self.cards[key] = card
                self._labels[key] = label_key
                cards.append(card)
            layout.addWidget(CardGrid(cards))
        layout.addStretch()
        self.reload()

    def retranslate(self) -> None:
        for key, label_key in self._labels.items():
            self.cards[key].title_lab.setText(t(label_key))
        for key, lab in self.sections.items():
            lab.setText(t(key))
        self.add_btn.setText("+  " + t("add"))
        self.q_pos.setText(t("quick_pos"))
        self.q_pur.setText(t("quick_purchase"))
        self.q_exp.setText(t("quick_expiry"))
        self.q_rep.setText(t("quick_reports"))
        self.close_btn.setText(t("close_month"))
        self.q_month.setText(t("this_month"))

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
        self.cards["backup"].value.setText((bak.get("last_verified") or "—")[:16])
        self.cards["backup"].value.setProperty("warn", bool(bak.get("warning")))
        self.cards["backup"].value.style().unpolish(self.cards["backup"].value)
        self.cards["backup"].value.style().polish(self.cards["backup"].value)
        cur = period_service.current_period()
        closes = period_service.list_closes(1)
        last = closes[0]["period_key"] if closes else "—"
        self.period_badge.setText(cur["period_key"])
        self.period_lab.setText(
            f"{t('current_period')}   ·   {t('closed_periods')}: {last}"
        )

    def _close_month(self) -> None:
        try:
            result = period_service.close_previous_month()
            if result.get("already"):
                info(self, t("month_already_closed"))
            else:
                info(self, t("period_closed"))
            self.reload()
        except Exception as exc:
            error(self, exc)
