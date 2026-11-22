from __future__ import annotations

import base64
import time
from html import escape
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QMarginsF, QSizeF, QTimer
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter, QPrinterInfo, QPrintPreviewDialog
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from app.config import BILL_RETURN_POLICY_EN, BILL_RETURN_POLICY_UR, STORE_PHONE, bills_dir
from app.i18n.translator import i18n, t
from app.printing import escpos
from app.services import settings_service
from app.utils.money import format_pkr, from_paisa


def _logo_data_uri() -> str:
    info = settings_service.pharmacy_info()
    raw = b""
    path = (info.get("logo_path") or "").strip()
    if path and Path(path).is_file():
        raw = Path(path).read_bytes()
    if not raw:
        from app.ui.icon import store_logo_pixmap

        pix = store_logo_pixmap(128)
        buf = QByteArray()
        device = QBuffer(buf)
        device.open(QIODevice.OpenModeFlag.WriteOnly)
        pix.save(device, "PNG")
        raw = bytes(buf)
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def _pharmacy_header() -> str:
    info = settings_service.pharmacy_info()
    phone = (info.get("phone") or "").strip() or STORE_PHONE
    bits = [
        f"<img src='{_logo_data_uri()}' width='72' height='72' style='display:block;margin:0 auto 6px auto' />",
        f"<h2 style='margin:0;letter-spacing:0.5px'>{escape(info['name'] or 'Hadi Pharmacy')}</h2>",
        "<div style='color:#555;margin-top:2px'>Pharmacy POS System</div>",
    ]
    if info.get("address"):
        bits.append(f"<div>{escape(info['address'])}</div>")
    bits.append(f"<div style='margin-top:4px;font-size:15px'><b>Ph: {escape(phone)}</b></div>")
    if info.get("ntn"):
        bits.append(f"<div>NTN: {escape(info['ntn'])}</div>")
    return "".join(bits)


def _footer_html() -> str:
    info = settings_service.pharmacy_info()
    policy = BILL_RETURN_POLICY_UR if i18n.lang == "ur" else BILL_RETURN_POLICY_EN
    extra = (info["footer_ur"] if i18n.lang == "ur" else info["footer_en"] or "").strip()
    if extra and extra != policy:
        return f"{escape(extra)}<br>{escape(policy)}"
    return escape(policy)


def sale_html(sale: dict, thermal: bool = True) -> str:
    if thermal:
        return _sale_html_thermal(sale)
    footer = _footer_html()
    rows = []
    for i, item in enumerate(sale.get("items") or [], start=1):
        line_total = item["qty"] * item["unit_price_paisa"] - item["discount_paisa"]
        extra = []
        if item.get("batch_no"):
            extra.append(str(item.get("batch_no")))
        if item.get("expiry"):
            extra.append(str(item.get("expiry")))
        meta = f"<br><small>{escape('  ·  '.join(extra))}</small>" if extra else ""
        rows.append(
            f"<tr>"
            f"<td align='center'>{i}</td>"
            f"<td>{escape(item.get('brand_name') or '')}{meta}</td>"
            f"<td align='center'>{item['qty']}</td>"
            f"<td align='right'>{from_paisa(item['unit_price_paisa']):.2f}</td>"
            f"<td align='right'>{from_paisa(line_total):.2f}</td>"
            f"</tr>"
        )
    customer = sale.get("customer_name") or t("walk_in")
    return f"""
    <html><body style="font-family:'Segoe UI',sans-serif; font-size:14px; color:#111; background:#fff;">
    <div style="text-align:center;border-bottom:2px dashed #333;padding-bottom:8px">
      {_pharmacy_header()}
      <div style="margin-top:4px"><b>SALE BILL</b></div>
    </div>
    <table width="100%" style="margin-top:8px">
      <tr><td>{t('invoice')}</td><td align="right"><b>{escape(str(sale.get('invoice_no') or ''))}</b></td></tr>
      <tr><td>{t('date')}</td><td align="right">{escape(str(sale.get('ts') or sale.get('date') or ''))}</td></tr>
      <tr><td>{t('customer')}</td><td align="right">{escape(str(customer))}</td></tr>
      <tr><td>{t('payment')}</td><td align="right">{escape(str(sale.get('payment_method') or ''))}</td></tr>
    </table>
    <hr style="border:none;border-top:1px dashed #333">
    <table width="100%" cellspacing="0" cellpadding="3">
      <tr>
        <th align="center">#</th>
        <th align="left">{t('brand')}</th>
        <th>{t('qty')}</th>
        <th align="right">{t('sale_price')}</th>
        <th align="right">{t('total')}</th>
      </tr>
      {''.join(rows) or '<tr><td colspan="5" align="center">—</td></tr>'}
    </table>
    <hr style="border:none;border-top:1px dashed #333">
    <table width="100%">
      <tr><td>{t('subtotal')}</td><td align="right">{format_pkr(sale.get('subtotal_paisa'))}</td></tr>
      {f"<tr><td>{t('gst')}</td><td align='right'>{format_pkr(sale.get('gst_paisa'))}</td></tr>" if sale.get("gst_paisa") else ""}
      <tr><td style="font-size:16px"><b>{t('total')}</b></td>
          <td align="right" style="font-size:16px"><b>{format_pkr(sale.get('total_paisa'))}</b></td></tr>
      <tr><td>{t('paid')}</td><td align="right">{format_pkr(sale.get('paid_paisa'))}</td></tr>
      {f"<tr><td>{t('due')}</td><td align='right'>{format_pkr(sale.get('due_paisa'))}</td></tr>" if sale.get("due_paisa") else ""}
    </table>
    <hr style="border:none;border-top:2px dashed #333">
    <div style="text-align:center;font-size:12px;margin-top:4px"><b>{footer}</b></div>
    <div style="text-align:center;font-size:11px;margin-top:6px">Software: Hadi Pharmacy</div>
    </body></html>
    """


def _sale_html_thermal(sale: dict) -> str:
    """Narrow 80mm slip. No wide tables — those wrap and force extra paper on BC-86AC."""
    info = settings_service.pharmacy_info()
    phone = (info.get("phone") or "").strip() or STORE_PHONE
    name = escape(info.get("name") or "Hadi Pharmacy")
    lines = []
    for item in sale.get("items") or []:
        line_total = item["qty"] * item["unit_price_paisa"] - item["discount_paisa"]
        brand = escape((item.get("brand_name") or "")[:22])
        lines.append(
            f"<tr><td>{brand}</td>"
            f"<td align='center'>{item['qty']}</td>"
            f"<td align='right'>{from_paisa(line_total):.2f}</td></tr>"
        )
    customer = escape(str(sale.get("customer_name") or t("walk_in")))
    return f"""
    <html><body style="font-family:'Consolas','Segoe UI',monospace;font-size:11px;
         width:68mm;margin:0;padding:0;color:#000;background:#fff;">
    <div style="text-align:center;font-size:13px;font-weight:700">{name}</div>
    <div style="text-align:center">Ph: {escape(phone)}</div>
    <div style="text-align:center;margin:3px 0">SALE BILL</div>
    <div>{t('invoice')}: {escape(str(sale.get('invoice_no') or ''))}</div>
    <div>{t('date')}: {escape(str(sale.get('ts') or sale.get('date') or '')[:16])}</div>
    <div>{t('customer')}: {customer}</div>
    <div>{t('payment')}: {escape(str(sale.get('payment_method') or ''))}</div>
    <div style="border-top:1px dashed #000;margin:4px 0"></div>
    <table width="100%" cellspacing="0" cellpadding="1" style="font-size:11px">
      <tr><td><b>Item</b></td><td align="center"><b>Qty</b></td><td align="right"><b>Rs</b></td></tr>
      {''.join(lines) or '<tr><td colspan="3">—</td></tr>'}
    </table>
    <div style="border-top:1px dashed #000;margin:4px 0"></div>
    <table width="100%" style="font-size:12px">
      <tr><td><b>{t('total')}</b></td><td align="right"><b>{format_pkr(sale.get('total_paisa'))}</b></td></tr>
      <tr><td>{t('paid')}</td><td align="right">{format_pkr(sale.get('paid_paisa'))}</td></tr>
    </table>
    <div style="border-top:1px dashed #000;margin:4px 0"></div>
    <div style="text-align:center;font-size:10px">{_footer_html()}</div>
    </body></html>
    """


def report_html(title: str, columns: list[str], rows: list[list[str]], summary: str = "") -> str:
    head = "".join(f"<th>{escape(c)}</th>" for c in columns)
    body = []
    for row in rows:
        tds = "".join(f"<td>{escape(str(c))}</td>" for c in row)
        body.append(f"<tr>{tds}</tr>")
    return f"""
    <html><body style="font-family:'Segoe UI','Noto Naskh Arabic',sans-serif; font-size:12px;">
    <div style="text-align:center">{_pharmacy_header()}<h3>{escape(title)}</h3></div>
    <p>{escape(summary)}</p>
    <table border="1" cellspacing="0" cellpadding="4" width="100%" style="border-collapse:collapse;">
      <tr style="background:#6d5efc;color:#fff">{head}</tr>
      {''.join(body)}
    </table>
    </body></html>
    """


THERMAL_DPI = 203


def _thermal_doc(html: str) -> tuple[QTextDocument, float]:
    doc = QTextDocument()
    doc.setDocumentMargin(2)
    doc.setTextWidth(int(72 / 25.4 * THERMAL_DPI))
    doc.setHtml(html)
    height_px = max(int(doc.size().height()) + 12, 80)
    height_mm = min(max(height_px * 25.4 / THERMAL_DPI + 8, 50), 280)
    return doc, height_mm


def _printer(thermal: bool, height_mm: float = 80) -> QPrinter:
    mode = QPrinter.PrinterMode.ScreenResolution if thermal else QPrinter.PrinterMode.HighResolution
    printer = QPrinter(mode)
    name = settings_service.get("printer_name", "")
    if name:
        printer.setPrinterName(name)
    if thermal:
        printer.setResolution(THERMAL_DPI)
        page = QPageSize(QSizeF(80, height_mm), QPageSize.Unit.Millimeter, "80mm-slip")
        layout = QPageLayout(page, QPageLayout.Orientation.Portrait, QMarginsF(2, 2, 2, 4), QPageLayout.Unit.Millimeter)
        printer.setPageLayout(layout)
        printer.setFullPage(False)
    else:
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    return printer


def print_html(html: str, thermal: bool = False, pdf_path: str | None = None, parent=None, preview: bool = False) -> bool:
    doc, height_mm = _thermal_doc(html) if thermal else (None, 80)
    printer = _printer(thermal, height_mm)
    if pdf_path:
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(pdf_path)
    elif preview and parent is not None:
        dlg = QPrintPreviewDialog(printer, parent)
        dlg.paintRequested.connect(lambda p, h=html: _paint(h, p))
        dlg.exec()
        return True
    elif parent is not None and not settings_service.get("printer_name"):
        dlg = QPrintDialog(printer, parent)
        if dlg.exec() != QPrintDialog.DialogCode.Accepted:
            return False
    if doc is not None:
        painter = QPainter(printer)
        try:
            doc.drawContents(painter)
        finally:
            painter.end()
    else:
        _paint(html, printer)
    return True


def _paint(html: str, printer: QPrinter) -> None:
    doc = QTextDocument()
    doc.setHtml(html)
    doc.print_(printer)


_print_busy = False
_last_print = {"key": None, "at": 0.0}
REPEAT_GUARD_SECONDS = 5.0


def _slip_policy() -> str:
    info = settings_service.pharmacy_info()
    extra = (info.get("footer_en") or "").strip()
    if extra and extra != BILL_RETURN_POLICY_EN:
        return f"{extra} {BILL_RETURN_POLICY_EN}"
    return BILL_RETURN_POLICY_EN


def slip_bytes(sale: dict) -> bytes:
    info = settings_service.pharmacy_info()
    shop = {
        "name": info.get("name") or "Hadi Pharmacy",
        "address": info.get("address") or "",
        "phone": (info.get("phone") or "").strip() or STORE_PHONE,
        "ntn": info.get("ntn") or "",
    }
    try:
        width = int(settings_service.get("thermal_width", "48") or 48)
    except ValueError:
        width = 48
    try:
        feed = int(settings_service.get("thermal_feed", "4") or 4)
    except ValueError:
        feed = 4
    return escpos.build_sale_slip(sale, shop, _slip_policy(), width=width, feed_lines=feed)


def choose_receipt_printer(parent=None, force: bool = False) -> str:
    name = settings_service.get("printer_name", "")
    names = QPrinterInfo.availablePrinterNames()
    if name and name in names and not force:
        return name
    if not names:
        QMessageBox.warning(parent, t("error"), t("no_printers"))
        return ""
    guess = escpos.default_printer()
    for n in names:
        low = n.lower()
        if any(k in low for k in ("bc-86", "bc86", "black copper", "pos", "thermal", "80")):
            guess = n
            break
    dlg = QDialog(parent)
    dlg.setWindowTitle(t("printer_pick"))
    box = QVBoxLayout(dlg)
    lab = QLabel(t("printer_pick_hint"))
    lab.setWordWrap(True)
    box.addWidget(lab)
    combo = QComboBox()
    combo.addItems(names)
    if guess in names:
        combo.setCurrentText(guess)
    box.addWidget(combo)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    box.addWidget(buttons)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return ""
    chosen = combo.currentText()
    settings_service.set_value("printer_name", chosen)
    return chosen


def _check_queue(name: str, parent) -> bool:
    try:
        state = escpos.printer_state(name)
    except OSError:
        return True
    problems = [s for s in state["status"] if s != "printing"]
    if state["jobs"] > 0:
        msg = t("printer_queue_waiting").replace("{n}", str(state["jobs"]))
        choice = QMessageBox.question(
            parent,
            t("printer"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
        )
        if choice == QMessageBox.StandardButton.Cancel:
            return False
        if choice == QMessageBox.StandardButton.Yes:
            try:
                escpos.purge_queue(name)
            except OSError as exc:
                QMessageBox.warning(parent, t("printer"), f"{t('queue_clear_failed')}\n{exc}")
                return False
    if problems:
        msg = t("printer_status_warn").replace("{status}", ", ".join(problems))
        if QMessageBox.question(parent, t("printer"), msg) != QMessageBox.StandardButton.Yes:
            return False
    return True


def print_receipt(sale: dict, parent=None) -> bool:
    """Send one 80mm bill. Repeats of the same bill within a few seconds are ignored."""
    global _print_busy
    key = str(sale.get("invoice_no") or sale.get("id") or "")
    now = time.monotonic()
    if _print_busy:
        return False
    if key and _last_print["key"] == key and now - _last_print["at"] < REPEAT_GUARD_SECONDS:
        return False
    _print_busy = True
    try:
        mode = settings_service.get("receipt_mode", "direct") or "direct"
        if mode == "direct" and escpos.available():
            name = choose_receipt_printer(parent)
            if not name or not _check_queue(name, parent):
                return False
            escpos.send_raw(name, slip_bytes(sale), f"Bill {key}")
        elif not print_html(sale_html(sale, True), thermal=True, parent=parent):
            return False
        _last_print.update(key=key, at=time.monotonic())
        return True
    except Exception as exc:
        QMessageBox.warning(parent, t("error"), f"{t('print_failed')}\n{exc}")
        return False
    finally:
        _print_busy = False


def print_test_slip(parent=None) -> bool:
    name = choose_receipt_printer(parent)
    if not name:
        return False
    try:
        if settings_service.get("receipt_mode", "direct") == "direct" and escpos.available():
            width = int(settings_service.get("thermal_width", "48") or 48)
            escpos.send_raw(name, escpos.build_test_slip(name, width), "Printer test")
        else:
            print_html("<div style='text-align:center'><b>Hadi Pharmacy</b><br>Printer test</div>", thermal=True, parent=parent)
        return True
    except Exception as exc:
        QMessageBox.warning(parent, t("error"), f"{t('print_failed')}\n{exc}")
        return False


def bill_path(sale: dict) -> Path:
    folder = bills_dir()
    name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(sale.get("invoice_no") or sale.get("id")))
    return folder / f"{name}.html"


def save_bill(sale: dict) -> Path:
    path = bill_path(sale)
    path.write_text(sale_html(sale, thermal=False), encoding="utf-8")
    return path


def show_bill(sale: dict, parent=None, print_now: bool = False) -> None:
    html = sale_html(sale, thermal=False)
    try:
        save_bill(sale)
    except OSError:
        pass
    dlg = QDialog(parent)
    dlg.setWindowTitle(f"{t('invoice')} {sale.get('invoice_no') or ''}")
    dlg.resize(480, 680)
    box = QVBoxLayout(dlg)
    view = QTextBrowser()
    view.setHtml(html)
    box.addWidget(view, 1)
    row = QHBoxLayout()
    p80 = QPushButton(t("print_80"))
    pa4 = QPushButton(t("print_a4"))
    close = QPushButton(t("cancel"))
    p80.setObjectName("GoldBtn")

    def _print_80() -> None:
        p80.setEnabled(False)
        try:
            print_receipt(sale, dlg)
        finally:
            QTimer.singleShot(int(REPEAT_GUARD_SECONDS * 1000), lambda: p80.setEnabled(True))

    p80.clicked.connect(_print_80)
    pa4.clicked.connect(lambda: print_html(html, thermal=False, parent=dlg, preview=True))
    close.clicked.connect(dlg.accept)
    for b in (p80, pa4, close):
        row.addWidget(b)
    box.addLayout(row)
    close.setDefault(True)
    if print_now:
        QTimer.singleShot(0, _print_80)
    dlg.exec()


def print_sale(sale: dict, thermal: bool, parent=None) -> None:
    try:
        save_bill(sale)
        show_bill(sale, parent=parent, print_now=thermal)
    except Exception as exc:
        QMessageBox.warning(parent, t("error"), str(exc))
