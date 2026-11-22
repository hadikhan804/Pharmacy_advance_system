"""Direct ESC/POS printing for 80mm thermal printers (Black Copper BC-86AC and similar).

The slip is sent as one RAW spooler job, so the Windows driver cannot add its
own roll-length page. The job ends with a short feed and a cut command, which
makes the printer stop right after the footer.
"""
from __future__ import annotations

import ctypes
import sys
import textwrap
from ctypes import wintypes

ESC = b"\x1b"
GS = b"\x1d"
INIT = ESC + b"@"
ALIGN_LEFT = ESC + b"a\x00"
ALIGN_CENTER = ESC + b"a\x01"
BOLD_ON = ESC + b"E\x01"
BOLD_OFF = ESC + b"E\x00"
SIZE_NORMAL = GS + b"!\x00"
SIZE_DOUBLE = GS + b"!\x11"
SIZE_TALL = GS + b"!\x01"
CUT = GS + b"V\x42\x00"

PRINTER_STATUS = {
    0x00000001: "paused",
    0x00000002: "error",
    0x00000008: "paper jam",
    0x00000010: "paper out",
    0x00000080: "offline",
    0x00000400: "printing",
    0x00400000: "door open",
    0x00001000: "not available",
}


def available() -> bool:
    return sys.platform == "win32"


if available():
    _ws = ctypes.WinDLL("winspool.drv", use_last_error=True)

    class DOC_INFO_1(ctypes.Structure):
        _fields_ = [
            ("pDocName", wintypes.LPWSTR),
            ("pOutputFile", wintypes.LPWSTR),
            ("pDatatype", wintypes.LPWSTR),
        ]

    class PRINTER_DEFAULTS(ctypes.Structure):
        _fields_ = [
            ("pDatatype", wintypes.LPWSTR),
            ("pDevMode", ctypes.c_void_p),
            ("DesiredAccess", wintypes.DWORD),
        ]

    class PRINTER_INFO_2(ctypes.Structure):
        _fields_ = [
            ("pServerName", wintypes.LPWSTR),
            ("pPrinterName", wintypes.LPWSTR),
            ("pShareName", wintypes.LPWSTR),
            ("pPortName", wintypes.LPWSTR),
            ("pDriverName", wintypes.LPWSTR),
            ("pComment", wintypes.LPWSTR),
            ("pLocation", wintypes.LPWSTR),
            ("pDevMode", ctypes.c_void_p),
            ("pSepFile", wintypes.LPWSTR),
            ("pPrintProcessor", wintypes.LPWSTR),
            ("pDatatype", wintypes.LPWSTR),
            ("pParameters", wintypes.LPWSTR),
            ("pSecurityDescriptor", ctypes.c_void_p),
            ("Attributes", wintypes.DWORD),
            ("Priority", wintypes.DWORD),
            ("DefaultPriority", wintypes.DWORD),
            ("StartTime", wintypes.DWORD),
            ("UntilTime", wintypes.DWORD),
            ("Status", wintypes.DWORD),
            ("cJobs", wintypes.DWORD),
            ("AveragePPM", wintypes.DWORD),
        ]

    _ws.OpenPrinterW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.HANDLE), ctypes.c_void_p]
    _ws.OpenPrinterW.restype = wintypes.BOOL
    _ws.ClosePrinter.argtypes = [wintypes.HANDLE]
    _ws.ClosePrinter.restype = wintypes.BOOL
    _ws.StartDocPrinterW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(DOC_INFO_1)]
    _ws.StartDocPrinterW.restype = wintypes.DWORD
    _ws.EndDocPrinter.argtypes = [wintypes.HANDLE]
    _ws.EndDocPrinter.restype = wintypes.BOOL
    _ws.StartPagePrinter.argtypes = [wintypes.HANDLE]
    _ws.StartPagePrinter.restype = wintypes.BOOL
    _ws.EndPagePrinter.argtypes = [wintypes.HANDLE]
    _ws.EndPagePrinter.restype = wintypes.BOOL
    _ws.WritePrinter.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    _ws.WritePrinter.restype = wintypes.BOOL
    _ws.GetPrinterW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    _ws.GetPrinterW.restype = wintypes.BOOL
    _ws.SetPrinterW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    _ws.SetPrinterW.restype = wintypes.BOOL
    _ws.GetDefaultPrinterW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    _ws.GetDefaultPrinterW.restype = wintypes.BOOL


def _open(name: str, admin: bool = False) -> "wintypes.HANDLE":
    handle = wintypes.HANDLE()
    defaults = None
    if admin:
        defaults = PRINTER_DEFAULTS(None, None, 0x0000000C)
    ok = _ws.OpenPrinterW(name, ctypes.byref(handle), ctypes.byref(defaults) if defaults else None)
    if not ok:
        raise OSError(f"Cannot open printer '{name}' ({ctypes.get_last_error()})")
    return handle


def default_printer() -> str:
    if not available():
        return ""
    size = wintypes.DWORD(0)
    _ws.GetDefaultPrinterW(None, ctypes.byref(size))
    if not size.value:
        return ""
    buf = ctypes.create_unicode_buffer(size.value)
    if _ws.GetDefaultPrinterW(buf, ctypes.byref(size)):
        return buf.value
    return ""


def printer_state(name: str) -> dict:
    """Pending job count and readable status flags for a printer."""
    out = {"jobs": 0, "status": [], "port": "", "driver": ""}
    if not available() or not name:
        return out
    handle = _open(name)
    try:
        needed = wintypes.DWORD(0)
        _ws.GetPrinterW(handle, 2, None, 0, ctypes.byref(needed))
        if not needed.value:
            return out
        buf = ctypes.create_string_buffer(needed.value)
        if not _ws.GetPrinterW(handle, 2, buf, needed, ctypes.byref(needed)):
            return out
        info = ctypes.cast(buf, ctypes.POINTER(PRINTER_INFO_2)).contents
        out["jobs"] = int(info.cJobs)
        out["port"] = info.pPortName or ""
        out["driver"] = info.pDriverName or ""
        out["status"] = [label for bit, label in PRINTER_STATUS.items() if info.Status & bit]
        return out
    finally:
        _ws.ClosePrinter(handle)


def purge_queue(name: str) -> None:
    """Cancel every waiting job on the printer (needs rights to manage the printer)."""
    handle = _open(name, admin=True)
    try:
        if not _ws.SetPrinterW(handle, 0, None, 3):
            raise OSError(f"Windows refused to clear the queue ({ctypes.get_last_error()})")
    finally:
        _ws.ClosePrinter(handle)


def send_raw(name: str, data: bytes, doc_name: str = "Hadi Pharmacy bill") -> int:
    if not available():
        raise OSError("Direct printing needs Windows")
    handle = _open(name)
    try:
        info = DOC_INFO_1(doc_name, None, "RAW")
        job = _ws.StartDocPrinterW(handle, 1, ctypes.byref(info))
        if not job:
            raise OSError(f"Printer '{name}' did not accept the job ({ctypes.get_last_error()})")
        try:
            if not _ws.StartPagePrinter(handle):
                raise OSError("StartPagePrinter failed")
            buf = ctypes.create_string_buffer(data, len(data))
            written = wintypes.DWORD(0)
            ok = _ws.WritePrinter(handle, buf, len(data), ctypes.byref(written))
            _ws.EndPagePrinter(handle)
            if not ok or written.value != len(data):
                raise OSError("Printer write was incomplete")
        finally:
            _ws.EndDocPrinter(handle)
        return int(job)
    finally:
        _ws.ClosePrinter(handle)


def _enc(text: str) -> bytes:
    return text.encode("cp437", errors="replace")


def _wrap(text: str, width: int) -> list[str]:
    text = " ".join(str(text or "").split())
    if not text:
        return []
    return textwrap.wrap(text, width=width, break_long_words=True) or [text[:width]]


def _pair(left: str, right: str, width: int) -> str:
    left = str(left)
    right = str(right)
    space = width - len(right) - 1
    if space < 1:
        return (left + " " + right)[:width]
    return left[:space].ljust(space) + " " + right


def _money(paisa) -> str:
    return f"{int(paisa or 0) / 100:,.2f}"


def build_sale_slip(sale: dict, shop: dict, policy: str, width: int = 48, feed_lines: int = 4, cut: bool = True) -> bytes:
    width = max(24, min(int(width or 48), 64))
    dash = "-" * width
    out = bytearray()
    out += INIT + ALIGN_CENTER

    name = shop.get("name") or "Hadi Pharmacy"
    out += BOLD_ON + SIZE_DOUBLE
    for line in _wrap(name, width // 2):
        out += _enc(line) + b"\n"
    out += SIZE_NORMAL + BOLD_OFF
    for key in ("address",):
        for line in _wrap(shop.get(key) or "", width):
            out += _enc(line) + b"\n"
    if shop.get("phone"):
        out += BOLD_ON + _enc(f"Ph: {shop['phone']}") + b"\n" + BOLD_OFF
    if shop.get("ntn"):
        out += _enc(f"NTN: {shop['ntn']}") + b"\n"
    out += BOLD_ON + b"SALE BILL\n" + BOLD_OFF
    out += ALIGN_LEFT + _enc(dash) + b"\n"

    ts = str(sale.get("ts") or sale.get("date") or "")[:16]
    out += _enc(_pair(f"Bill: {sale.get('invoice_no') or sale.get('id') or ''}", ts, width)) + b"\n"
    customer = sale.get("customer_name") or "Walk-in"
    out += _enc(_pair(f"Customer: {customer}"[: width - 12], str(sale.get("payment_method") or ""), width)) + b"\n"
    out += _enc(dash) + b"\n"

    qty_w, rate_w, total_w = 5, 9, 11
    name_w = width - qty_w - rate_w - total_w
    out += BOLD_ON + _enc(
        "Item".ljust(name_w) + "Qty".rjust(qty_w) + "Rate".rjust(rate_w) + "Total".rjust(total_w)
    ) + b"\n" + BOLD_OFF
    for item in sale.get("items") or []:
        qty = int(item.get("qty") or 0)
        unit = int(item.get("unit_price_paisa") or 0)
        total = qty * unit - int(item.get("discount_paisa") or 0)
        parts = _wrap(item.get("brand_name") or "", name_w - 1) or [""]
        first = parts[0].ljust(name_w)
        out += _enc(
            first + str(qty).rjust(qty_w) + _money(unit).rjust(rate_w) + _money(total).rjust(total_w)
        ) + b"\n"
        for extra in parts[1:]:
            out += _enc(extra) + b"\n"
    out += _enc(dash) + b"\n"

    out += _enc(_pair("Subtotal", _money(sale.get("subtotal_paisa")), width)) + b"\n"
    if sale.get("discount_paisa"):
        out += _enc(_pair("Discount", "-" + _money(sale.get("discount_paisa")), width)) + b"\n"
    if sale.get("gst_paisa"):
        out += _enc(_pair("GST", _money(sale.get("gst_paisa")), width)) + b"\n"
    out += BOLD_ON + SIZE_TALL + _enc(_pair("TOTAL Rs", _money(sale.get("total_paisa")), width)) + b"\n"
    out += SIZE_NORMAL + BOLD_OFF
    paid = int(sale.get("paid_paisa") or 0)
    total = int(sale.get("total_paisa") or 0)
    out += _enc(_pair("Paid", _money(paid), width)) + b"\n"
    if sale.get("due_paisa"):
        out += _enc(_pair("Due", _money(sale.get("due_paisa")), width)) + b"\n"
    elif paid > total:
        out += _enc(_pair("Change", _money(paid - total), width)) + b"\n"
    out += _enc(dash) + b"\n"

    out += ALIGN_CENTER
    for line in _wrap(policy, width):
        out += _enc(line) + b"\n"
    out += _enc("Thank you - Software: Hadi Pharmacy") + b"\n"
    out += ESC + b"d" + bytes([max(0, min(int(feed_lines), 10))])
    if cut:
        out += CUT
    return bytes(out)


def build_test_slip(printer: str, width: int = 48) -> bytes:
    dash = "-" * width
    out = bytearray(INIT + ALIGN_CENTER + BOLD_ON + b"Hadi Pharmacy\n" + BOLD_OFF)
    out += b"Printer test\n" + _enc(printer[:width]) + b"\n" + ALIGN_LEFT + _enc(dash) + b"\n"
    out += _enc("1234567890" * (width // 10) + "1234567890"[: width % 10]) + b"\n"
    out += _enc(dash) + b"\n" + ALIGN_CENTER
    out += b"If this slip stopped and cut here,\nprinting is set up correctly.\n"
    out += ESC + b"d\x04" + CUT
    return bytes(out)
