from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import t
from app.utils.money import format_pkr, from_paisa, to_paisa


class FlowLayout(QLayout):
    """Lays widgets left to right and wraps to a new row when the width runs out."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 6):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._layout(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._layout(rect, apply=True)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _layout(self, rect: QRect, apply: bool) -> int:
        m = self.contentsMargins()
        area = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, row_h = area.x(), area.y(), 0
        rtl = self.parentWidget() is not None and self.parentWidget().layoutDirection() == Qt.LayoutDirection.RightToLeft
        for item in self._items:
            if item.widget() is not None and item.widget().isHidden():
                continue
            hint = item.sizeHint()
            if x + hint.width() > area.right() + 1 and row_h > 0:
                x = area.x()
                y += row_h + self._spacing
                row_h = 0
            if apply:
                px = area.right() + 1 - (x - area.x()) - hint.width() if rtl else x
                item.setGeometry(QRect(QPoint(px, y), hint))
            x += hint.width() + self._spacing
            row_h = max(row_h, hint.height())
        return y + row_h - rect.y() + m.bottom()


def scroll_wrap(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setObjectName("PageScroll")
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    area.setWidget(widget)
    return area


class FormArrowNav(QObject):
    """Move between form fields with arrows / Enter, like a spreadsheet."""

    def __init__(self, widgets: list[QWidget], dialog: QDialog | None = None):
        super().__init__(dialog or (widgets[0] if widgets else None))
        self.widgets = widgets
        self.dialog = dialog
        for a, b in zip(widgets, widgets[1:]):
            QWidget.setTabOrder(a, b)
        for w in widgets:
            w.installEventFilter(self)
            if isinstance(w, QComboBox) and w.isEditable() and w.lineEdit():
                w.lineEdit().installEventFilter(self)

    def _index(self, obj) -> int:
        if obj in self.widgets:
            return self.widgets.index(obj)
        parent = obj.parent() if hasattr(obj, "parent") else None
        if parent in self.widgets:
            return self.widgets.index(parent)
        return -1

    def _move(self, obj, step: int) -> bool:
        idx = self._index(obj)
        if idx < 0:
            return False
        nxt = idx + step
        if nxt >= len(self.widgets):
            if self.dialog and step > 0:
                self.dialog.accept()
            return True
        if nxt < 0:
            return True
        target = self.widgets[nxt]
        target.setFocus(Qt.FocusReason.TabFocusReason)
        if isinstance(target, QLineEdit):
            target.selectAll()
        elif isinstance(target, QComboBox) and target.isEditable() and target.lineEdit():
            target.lineEdit().selectAll()
        elif hasattr(target, "selectAll"):
            try:
                target.selectAll()
            except Exception:
                pass
        return True

    def _line(self, obj) -> QLineEdit | None:
        if isinstance(obj, QLineEdit):
            return obj
        if isinstance(obj, QComboBox) and obj.isEditable():
            return obj.lineEdit()
        return None

    def eventFilter(self, obj, event):
        if event.type() != QEvent.Type.KeyPress:
            return False
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Down):
            return self._move(obj, 1)
        if key == Qt.Key.Key_Up:
            return self._move(obj, -1)
        line = self._line(obj)
        if line and key == Qt.Key.Key_Right and line.cursorPosition() >= len(line.text()):
            return self._move(obj, 1)
        if line and key == Qt.Key.Key_Left and line.cursorPosition() <= 0:
            return self._move(obj, -1)
        return False


def bind_arrow_nav(widgets: list[QWidget], dialog: QDialog | None = None) -> FormArrowNav:
    return FormArrowNav(widgets, dialog)


def info(parent, text: str) -> None:
    QMessageBox.information(parent, t("success"), text)


def error(parent, text: str) -> None:
    QMessageBox.warning(parent, t("error"), str(text))


def ask(parent, text: str) -> bool:
    return QMessageBox.question(parent, t("confirm"), text) == QMessageBox.StandardButton.Yes


def safe_delete(parent, name: str, action, detail: str = "") -> str | None:
    """Confirm, take a backup, then delete or archive. Returns 'deleted', 'archived' or None."""
    msg = t("delete_confirm").replace("{name}", name)
    if detail:
        msg += "\n\n" + detail
    if not ask(parent, msg):
        return None
    try:
        from app.services import backup_service

        backup_service.run_backup("before-delete")
    except Exception as exc:
        if not ask(parent, f"{t('backup_failed_continue')}\n{exc}"):
            return None
    try:
        result = action()
    except Exception as exc:
        error(parent, exc)
        return None
    if result == "archived":
        info(parent, t("archived_ok").replace("{name}", name))
    else:
        info(parent, t("deleted_ok").replace("{name}", name))
    return result or "deleted"


def action_button(text: str, kind: str = "GhostBtn") -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName(kind)
    return btn


def money_spin(value: float = 0.0) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(0, 10_000_000)
    box.setDecimals(2)
    box.setPrefix("Rs ")
    box.setValue(value)
    return box


class PriceSlot(QFrame):
    """Fixed labeled slot so cost and sale never jump around."""

    def __init__(self, title: str, widget: QWidget, readonly: bool = False):
        super().__init__()
        self.setObjectName("PriceSlot")
        box = QVBoxLayout(self)
        box.setContentsMargins(8, 6, 8, 6)
        box.setSpacing(4)
        self.title = QLabel(title.upper())
        self.title.setObjectName("Muted")
        self.title.setWordWrap(False)
        box.addWidget(self.title)
        if readonly and hasattr(widget, "setReadOnly"):
            widget.setReadOnly(True)
        box.addWidget(widget)


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
        self.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
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
        if self.auto_fit:
            self.fit_columns()

    auto_fit = True

    def fit_columns(self, max_width: int = 320) -> None:
        header = self.horizontalHeader()
        header.setResizeContentsPrecision(200)
        last = self.columnCount() - 1
        for c in range(self.columnCount()):
            if c == last and header.stretchLastSection():
                continue
            self.resizeColumnToContents(c)
            self.setColumnWidth(c, min(max(self.columnWidth(c) + 12, 64), max_width))

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
