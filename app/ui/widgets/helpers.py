from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import t
from app.utils.money import format_pkr, from_paisa, to_paisa


def info(parent, text: str) -> None:
    QMessageBox.information(parent, t("success"), text)


def error(parent, text: str) -> None:
    QMessageBox.warning(parent, t("error"), str(text))


def ask(parent, text: str) -> bool:
    return QMessageBox.question(parent, t("confirm"), text) == QMessageBox.StandardButton.Yes


def money_spin(value: float = 0.0) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(0, 10_000_000)
    box.setDecimals(2)
    box.setPrefix("Rs ")
    box.setValue(value)
    return box


def qty_spin(value: int = 1, maximum: int = 1_000_000) -> QSpinBox:
    box = QSpinBox()
    box.setRange(0, maximum)
    box.setValue(value)
    return box


class DataTable(QTableWidget):
    def __init__(self, headers: list[str], parent=None):
        super().__init__(0, len(headers), parent)
        self.setHorizontalHeaderLabels(headers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(40)
        self.setSortingEnabled(True)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    def set_headers(self, headers: list[str]) -> None:
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)

    def fill(self, rows: list[list], row_ids: list | None = None, money_cols: set[int] | None = None) -> None:
        self.setSortingEnabled(False)
        self.setRowCount(0)
        money_cols = money_cols or set()
        for r, row in enumerate(rows):
            self.insertRow(r)
            for c, val in enumerate(row):
                if c in money_cols and isinstance(val, (int, float)):
                    text = format_pkr(int(val))
                else:
                    text = "" if val is None else str(val)
                item = QTableWidgetItem(text)
                if c in money_cols or isinstance(val, (int, float)):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if row_ids is not None:
                    item.setData(Qt.ItemDataRole.UserRole, row_ids[r])
                self.setItem(r, c, item)
        self.setSortingEnabled(True)

    def selected_id(self):
        items = self.selectedItems()
        if not items:
            return None
        return items[0].data(Qt.ItemDataRole.UserRole)


def form_dialog(parent, title: str, fields: list[tuple[str, QWidget]], on_accept=None) -> QDialog:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.resize(460, 100 + 44 * len(fields))
    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(12)
    form = QFormLayout()
    for label, widget in fields:
        form.addRow(label, widget)
    layout.addLayout(form)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    layout.addWidget(buttons)
    return dlg


class SearchBar(QWidget):
    def __init__(self, on_change, extra_buttons: list[QPushButton] | None = None):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(t("search"))
        self.edit.textChanged.connect(on_change)
        layout.addWidget(self.edit, 1)
        for btn in extra_buttons or []:
            layout.addWidget(btn)
