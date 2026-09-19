from __future__ import annotations

from html import escape
from pathlib import Path

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import QPageLayout, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter, QPrintPreviewDialog
from PySide6.QtWidgets import QDialog, QHBoxLayout, QMessageBox, QPushButton, QTextBrowser, QVBoxLayout

from app.config import data_dir

from app.i18n.translator import i18n, t
from app.services import settings_service
from app.utils.money import format_pkr, from_paisa


def _pharmacy_header() -> str:
    info = settings_service.pharmacy_info()
    bits = [f"<h2 style='margin:0'>{escape(info['name'])}</h2>"]
    if info["address"]:
        bits.append(f"<div>{escape(info['address'])}</div>")
    if info["phone"]:
        bits.append(f"<div>{escape(info['phone'])}</div>")
    if info["ntn"]:
        bits.append(f"<div>NTN: {escape(info['ntn'])}</div>")
    return "".join(bits)


def sale_html(sale: dict, thermal: bool = True) -> str:
    info = settings_service.pharmacy_info()
    footer = info["footer_ur"] if i18n.lang == "ur" else info["footer_en"]
    width = "72mm" if thermal else "100%"
    font = "13px" if thermal else "14px"
    rows = []
    for item in sale.get("items") or []:
        line_total = item["qty"] * item["unit_price_paisa"] - item["discount_paisa"]
        rows.append(
            f"<tr><td>{escape(item.get('brand_name',''))}<br>"
            f"<small>{escape(item.get('batch_no',''))} {escape(str(item.get('expiry','')))}</small></td>"
            f"<td align='center'>{item['qty']}</td>"
            f"<td align='right'>{from_paisa(item['unit_price_paisa']):.2f}</td>"
            f"<td align='right'>{from_paisa(line_total):.2f}</td></tr>"
        )
    customer = sale.get("customer_name") or t("walk_in")
    return f"""
    <html><body style="font-family:'Segoe UI','Noto Naskh Arabic','Urdu Typesetting',sans-serif;
         font-size:{font}; width:{width}; color:#111; background:#fff;">
    <div style="text-align:center;border-bottom:2px dashed #333;padding-bottom:8px">
      {_pharmacy_header()}
      <div style="letter-spacing:2px;margin-top:4px"><b>SALE BILL</b></div>
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
        <th align="left">{t('brand')}</th><th>{t('qty')}</th>
        <th align="right">{t('sale_price')}</th><th align="right">{t('total')}</th>
      </tr>
      {''.join(rows)}
    </table>
    <hr style="border:none;border-top:1px dashed #333">
    <table width="100%">
      <tr><td>{t('subtotal')}</td><td align="right">{format_pkr(sale.get('subtotal_paisa'))}</td></tr>
      <tr><td>{t('discount')}</td><td align="right">{format_pkr(sale.get('discount_paisa'))}</td></tr>
      <tr><td>{t('gst')}</td><td align="right">{format_pkr(sale.get('gst_paisa'))}</td></tr>
      <tr><td style="font-size:16px"><b>{t('total')}</b></td>
          <td align="right" style="font-size:16px"><b>{format_pkr(sale.get('total_paisa'))}</b></td></tr>
      <tr><td>{t('paid')}</td><td align="right">{format_pkr(sale.get('paid_paisa'))}</td></tr>
      <tr><td>{t('due')}</td><td align="right">{format_pkr(sale.get('due_paisa'))}</td></tr>
    </table>
    <hr style="border:none;border-top:2px dashed #333">
    <div style="text-align:center">{escape(footer or 'Thank you. Get well soon.')}</div>
    <div style="text-align:center;font-size:11px;margin-top:6px">Software: Yasir Medical Store</div>
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


def _printer(thermal: bool) -> QPrinter:
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    name = settings_service.get("printer_name", "")
    if name:
        printer.setPrinterName(name)
    if thermal:
        page = QPageSize(QSizeF(80, 200), QPageSize.Unit.Millimeter, "80mm")
        layout = QPageLayout(page, QPageLayout.Orientation.Portrait, QMarginsF(3, 3, 3, 3), QPageLayout.Unit.Millimeter)
        printer.setPageLayout(layout)
    else:
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    return printer


def print_html(html: str, thermal: bool = False, pdf_path: str | None = None, parent=None, preview: bool = False) -> bool:
    printer = _printer(thermal)
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
    _paint(html, printer)
    return True


def _paint(html: str, printer: QPrinter) -> None:
    doc = QTextDocument()
    doc.setHtml(html)
    doc.print_(printer)


def bill_path(sale: dict) -> Path:
    folder = data_dir() / "bills"
    folder.mkdir(parents=True, exist_ok=True)
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
    p80.clicked.connect(lambda: print_html(sale_html(sale, True), thermal=True, parent=dlg))
    pa4.clicked.connect(lambda: print_html(html, thermal=False, parent=dlg, preview=True))
    close.clicked.connect(dlg.accept)
    for b in (p80, pa4, close):
        row.addWidget(b)
    box.addLayout(row)
    if print_now:
        print_html(sale_html(sale, True), thermal=True, parent=dlg)
    dlg.exec()


def print_sale(sale: dict, thermal: bool, parent=None) -> None:
    try:
        save_bill(sale)
        show_bill(sale, parent=parent, print_now=thermal)
    except Exception as exc:
        QMessageBox.warning(parent, t("error"), str(exc))
