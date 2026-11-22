from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap


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


def store_logo_pixmap(size: int = 160) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#6d5efc"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(4, 4, size - 8, size - 8, size // 5, size // 5)
    pen = QPen(QColor("#ffffff"))
    pen.setWidth(max(10, size // 8))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    mid = size // 2
    arm = size // 4
    p.drawLine(mid, mid - arm, mid, mid + arm)
    p.drawLine(mid - arm, mid, mid + arm, mid)
    p.end()
    return pix


def store_banner_pixmap(width: int = 640, height: int = 160) -> QPixmap:
    pix = QPixmap(width, height)
    pix.fill(QColor("#0b0d12"))
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    logo = store_logo_pixmap(height - 24)
    p.drawPixmap(16, 12, logo)
    title = QFont("Segoe UI")
    title.setPixelSize(max(18, height // 4))
    title.setBold(True)
    p.setFont(title)
    p.setPen(QColor("#ffffff"))
    p.drawText(height + 8, height // 2 - 4, "Hadi Pharmacy")
    sub = QFont("Segoe UI")
    sub.setPixelSize(max(12, height // 7))
    p.setFont(sub)
    p.setPen(QColor("#f5c84c"))
    p.drawText(height + 8, height // 2 + height // 4, "Pharmacy POS System")
    p.end()
    return pix
