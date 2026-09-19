from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap


def app_icon() -> QIcon:
    pix = QPixmap(256, 256)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#6d5efc"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(8, 8, 240, 240, 56, 56)
    pen = QPen(QColor("#ffffff"))
    pen.setWidth(34)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawLine(128, 62, 128, 194)
    p.drawLine(62, 128, 194, 128)
    p.end()
    return QIcon(pix)
