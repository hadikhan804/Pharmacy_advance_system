from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from app.config import EXPIRY_ALERT_DAYS
from app.i18n import t
from app.services import settings_service, stock_service
from app.ui.widgets.helpers import DataTable


class ExpiryPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.tables: dict[str, DataTable] = {}
        self._build_tabs()
        self.reload()

    def _build_tabs(self) -> None:
        self.tabs.clear()
        self.tables.clear()
        headers = [t("brand"), t("batch"), t("expiry_date"), t("qty"), t("sale_price"), t("days_left"), t("company")]
        for days in settings_service.expiry_windows():
            table = DataTable(headers)
            self.tables[str(days)] = table
            if days >= EXPIRY_ALERT_DAYS:
                label = t("expiry_6_months")
            else:
                label = f"{days} {t('expiry_date')}"
            self.tabs.addTab(table, label)
        expired = DataTable([t("brand"), t("batch"), t("expiry_date"), t("qty"), t("sale_price"), t("company")])
        self.tables["expired"] = expired
        self.tabs.addTab(expired, t("expired"))

    def apply_filter(self, extra: dict) -> None:
        self.reload()
        if extra.get("week"):
            keys = [k for k in self.tables if k != "expired"]
            if keys:
                self.tabs.setCurrentIndex(0)
        if extra.get("months6"):
            keys = list(self.tables.keys())
            if str(EXPIRY_ALERT_DAYS) in keys:
                self.tabs.setCurrentIndex(keys.index(str(EXPIRY_ALERT_DAYS)))

    def retranslate(self) -> None:
        self._build_tabs()
        self.reload()

    def reload(self) -> None:
        for days, table in list(self.tables.items()):
            if days == "expired":
                rows = stock_service.expired()
                table.fill(
                    [[r["brand_name"], r["batch_no"], r["expiry"], r["qty"], r["sale_paisa"], r["company_name"]] for r in rows],
                    [r["id"] for r in rows],
                    money_cols={4},
                )
            else:
                rows = stock_service.expiring_within(int(days))
                table.fill(
                    [
                        [r["brand_name"], r["batch_no"], r["expiry"], r["qty"], r["sale_paisa"], r["days_left"], r["company_name"]]
                        for r in rows
                    ],
                    [r["id"] for r in rows],
                    money_cols={4},
                )
