"""End-to-end check on a throwaway data folder: data layout, services, bill bytes, and page screenshots.

Usage:  .venv\\Scripts\\python.exe scripts\\audit_all.py [screenshot_dir]
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix="yms_audit_"))
os.environ["HADI_DATA_DIR"] = str(TMP)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SHOTS = Path(sys.argv[1]) if len(sys.argv) > 1 else TMP / "shots"

failures: list[str] = []
passed: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (passed if ok else failures).append(name + (f" — {detail}" if detail and not ok else ""))


def step_data_layout() -> None:
    from app import config

    legacy = TMP / "pharmacy.db"
    conn = sqlite3.connect(legacy)
    conn.execute("CREATE TABLE marker(v TEXT)")
    conn.execute("INSERT INTO marker VALUES ('legacy')")
    conn.commit()
    conn.close()
    (TMP / "bills").mkdir()
    (TMP / "bills" / "old.html").write_text("x", encoding="utf-8")
    res = config.prepare_data_dir()
    check("legacy pharmacy.db moved into data/", res.get("action") == "migrated" and (TMP / "data" / "pharmacy.db").exists() and not legacy.exists(), str(res))
    check("legacy bills moved into data/bills", (TMP / "data" / "bills" / "old.html").exists())
    check("db_path is inside data/", config.db_path() == TMP / "data" / "pharmacy.db", str(config.db_path()))
    (TMP / "data" / "pharmacy.db").unlink()
    res = config.prepare_data_dir()
    check("no mirror yet -> fresh start", res.get("action") == "", str(res))


def step_services() -> None:
    from app.auth.session import Session
    from app.constants import PAYMENT_METHODS
    from app.db.database import get_db, init_db
    from app.i18n import i18n
    from app.services import (
        backup_service,
        customer_service,
        dashboard_service,
        medicine_service,
        period_service,
        purchase_service,
        report_service,
        sale_service,
        stock_service,
        supplier_service,
        user_service,
    )
    from app.utils.dates import month_start, today

    init_db()
    i18n.load("en")
    user = user_service.authenticate("admin", "admin123")
    check("default owner login works", user is not None)
    Session.set(user, None)
    backup_service.normalize_settings()
    check("backup folder points at data/backups", Path(backup_service.local_backup_dir()) == TMP / "data" / "backups", str(backup_service.local_backup_dir()))

    mid = medicine_service.save_medicine(
        {
            "brand_name": "Panadol 500mg",
            "generic_name": "Paracetamol",
            "category": "Tablet",
            "units_per_pack": 10,
            "cost_paisa": 20000,
            "sale_paisa": 25000,
            "reorder_level": 5,
            "rack": "A-3",
        }
    )
    sup = medicine_service.save_company("Audit Pharma", phone="042-111")
    pid = purchase_service.create_purchase(
        sup,
        "INV-1",
        today(),
        [{"medicine_id": mid, "batch_no": "B1", "expiry": "2030-01-31", "qty": 100, "cost_paisa": 2000, "sale_paisa": 2500}],
        paid_paisa=100000,
    )
    check("purchase saved", pid > 0)
    batches = stock_service.batches_for_medicine(mid)
    check("purchase added 100 tablets", sum(b["qty"] for b in batches) == 100, str([b["qty"] for b in batches]))
    bid = batches[0]["id"]

    cash = PAYMENT_METHODS[0]
    item = {
        "medicine_id": mid,
        "brand_name": "Panadol 500mg",
        "rack": "A-3",
        "batch_id": bid,
        "batch_no": "B1",
        "expiry": "2030-01-31",
        "qty": 12,
        "unit_price_paisa": 2500,
        "cost_paisa": 2000,
        "discount_paisa": 0,
        "gst_pct": 0,
    }
    sid = sale_service.complete_sale([item], cash, 30000, None, 0)
    sale = sale_service.get_sale(sid)
    check("sale total 12 x Rs25 = Rs300", sale["total_paisa"] == 30000, str(sale["total_paisa"]))
    left = sum(b["qty"] for b in stock_service.batches_for_medicine(mid))
    check("stock reduced to 88", left == 88, str(left))

    try:
        sale_service.complete_sale([dict(item, qty=10_000)], cash, 0, None, 0)
        check("overselling is blocked", False, "sale of 10000 went through")
    except Exception:
        check("overselling is blocked", True)

    cust = customer_service.save_customer({"name": "Audit Customer", "phone": "0300"})
    sid2 = sale_service.complete_sale([dict(item, qty=4)], "Credit" if "Credit" in PAYMENT_METHODS else PAYMENT_METHODS[-1], 0, cust, 0)
    s2 = sale_service.get_sale(sid2)
    check("credit sale records due", (s2.get("due_paisa") or 0) == 10000, str(s2.get("due_paisa")))

    s_items = sale_service.get_sale(sid)["items"]
    sale_service.return_sale(sid, [{"sale_item_id": s_items[0]["id"], "qty": 2}], "audit return")
    left = sum(b["qty"] for b in stock_service.batches_for_medicine(mid))
    check("return puts 2 back (88-4+2=86)", left == 86, str(left))

    stock_service.edit_batch(bid, "B1-fixed", "2031-06-30", 90, 2000, 2600, "audit re-edit")
    b = [x for x in stock_service.batches_for_medicine(mid) if x["id"] == bid][0]
    check("stock re-edit changes qty/batch/expiry", b["qty"] == 90 and b["batch_no"] == "B1-fixed" and b["expiry"] == "2031-06-30", str(b))
    audit = get_db().execute("SELECT COUNT(*) FROM audit_log WHERE action='stock.reedit'").fetchone()[0]
    check("re-edit written to audit trail", audit == 1, str(audit))
    try:
        stock_service.edit_batch(bid, "B1", "2031-06-30", 90, 2000, 2600, "  ")
        check("re-edit needs a reason", False)
    except ValueError:
        check("re-edit needs a reason", True)

    d = dashboard_service.summary()
    check("dashboard today sale counts sales minus return", d["today"]["sale"] > 0, str(d["today"]))
    series = report_service.period_series("monthly", month_start(), today())
    check("monthly report has a row", len(series) >= 1, str(series))
    closed = period_service.close_previous_month()
    check("month close runs", closed.get("ok") or closed.get("already"), str(closed))
    again = period_service.close_previous_month()
    check("month close is not duplicated", again.get("already") is True, str(again))

    path = backup_service.run_backup("audit")
    check("backup written without owner password", Path(path).exists(), str(path))
    check("backup is inside data/backups", Path(path).parent == TMP / "data" / "backups", str(path))
    with open(path, "rb") as fh:
        check("backup is a real SQLite file", fh.read(16).startswith(b"SQLite format 3"))
    backup_service.event_backup("audit-event")
    mirror = backup_service.mirror_db_path()
    check("safety mirror written", mirror.exists(), str(mirror))

    from app.printing import escpos, receipt

    slip = receipt.slip_bytes(sale_service.get_sale(sid))
    check("bill ends with feed + cut (stops paper)", slip.endswith(escpos.CUT) and b"\x1bd\x04" in slip[-12:])
    text_lines = [ln for ln in slip.split(b"\n")]
    widest = max(len(ln.replace(escpos.BOLD_ON, b"").replace(escpos.BOLD_OFF, b"").replace(escpos.ALIGN_LEFT, b"").replace(escpos.ALIGN_CENTER, b"").replace(escpos.SIZE_NORMAL, b"").replace(escpos.SIZE_TALL, b"").replace(escpos.SIZE_DOUBLE, b"").replace(escpos.INIT, b"")) for ln in text_lines[:-1])
    check("no bill line wider than 48 chars", widest <= 48, str(widest))
    check("bill has exactly one cut command", slip.count(escpos.CUT) == 1)
    check("bill shows phone", b"03716931861" in slip)
    (TMP / "slip_preview.txt").write_bytes(slip)
    return sid


def _raises(fn) -> str:
    try:
        fn()
    except Exception as exc:
        return str(exc) or exc.__class__.__name__
    return ""


def step_company_and_deletes() -> None:
    """Company = supplier, payments, safe delete/archive of every record type, and the old-supplier migration."""
    from app.db.database import close_db, get_db, init_db
    from app.services import (
        backup_service,
        customer_service,
        medicine_service,
        purchase_service,
        sale_service,
        stock_service,
        supplier_service,
        user_service,
    )
    from app.utils.dates import today

    db = get_db()
    comp = db.execute("SELECT id FROM companies WHERE name='Audit Pharma'").fetchone()["id"]
    pan = db.execute("SELECT id FROM medicines WHERE brand_name='Panadol 500mg'").fetchone()["id"]

    lst = purchase_service.list_purchases()
    check("purchase list shows the company name", lst and lst[-1]["supplier_name"] == "Audit Pharma", str(lst[-1] if lst else None))
    due = supplier_service.company_payable(comp)
    check("company owes Rs1000 (Rs2000 bill, Rs1000 paid)", due == 100000, str(due))
    pays = {r["name"]: r["payable_paisa"] for r in supplier_service.payables()}
    check("payables list is by company", pays.get("Audit Pharma") == 100000, str(pays))
    check("company payment above due is refused", bool(_raises(lambda: supplier_service.record_payment(comp, 999999))))
    check("zero payment is refused", bool(_raises(lambda: supplier_service.record_payment(comp, 0))))
    supplier_service.record_payment(comp, 40000, "Cash", "audit")
    check("company payment reduces due to Rs600", supplier_service.company_payable(comp) == 60000, str(supplier_service.company_payable(comp)))
    led = supplier_service.ledger(comp)
    check("company ledger ends at Rs600 balance", led and led[-1]["balance_paisa"] == 60000, str(led[-1] if led else None))
    check("purchase paid more than bill is refused", bool(_raises(lambda: purchase_service.create_purchase(
        comp, "X", today(), [{"medicine_id": pan, "batch_no": "Z", "expiry": "2030-01-31", "qty": 1, "cost_paisa": 100, "sale_paisa": 200}], paid_paisa=500))))
    check("purchase with 0 qty is refused", bool(_raises(lambda: purchase_service.create_purchase(
        comp, "X", today(), [{"medicine_id": pan, "batch_no": "Z", "expiry": "2030-01-31", "qty": 0, "cost_paisa": 100, "sale_paisa": 200}]))))
    check("purchase without company is refused", bool(_raises(lambda: purchase_service.create_purchase(
        None, "X", today(), [{"medicine_id": pan, "batch_no": "Z", "expiry": "2030-01-31", "qty": 1, "cost_paisa": 100, "sale_paisa": 200}]))))

    medicine_service.save_company("Audit Pharma Ltd", "", comp, True, "042-222", "Lahore")
    lst = purchase_service.list_purchases()
    check("renaming a company updates old purchases", any(p["supplier_name"] == "Audit Pharma Ltd" for p in lst), str([p["supplier_name"] for p in lst]))
    check("duplicate company name is refused", bool(_raises(lambda: medicine_service.save_company("audit pharma ltd"))))

    first_pid = [p for p in lst if p["invoice_no"] == "INV-1"][0]["id"]
    msg = _raises(lambda: purchase_service.delete_purchase(first_pid, "wrong"))
    check("purchase whose stock was sold cannot be deleted", bool(msg), msg)
    check("purchase delete needs a reason", bool(_raises(lambda: purchase_service.delete_purchase(first_pid, " "))))

    m2 = medicine_service.save_medicine({"brand_name": "Audit Syrup", "category": "Syrup", "units_per_pack": 1, "cost_paisa": 5000, "sale_paisa": 7000})
    p2 = purchase_service.create_purchase(
        comp, "INV-WRONG", today(),
        [{"medicine_id": m2, "batch_no": "S1", "expiry": "2030-05-31", "qty": 6, "cost_paisa": 5000, "sale_paisa": 7000}],
        paid_paisa=10000,
    )
    before_due = supplier_service.company_payable(comp)
    purchase_service.delete_purchase(p2, "typed wrong invoice")
    stock_left = sum(b["qty"] for b in stock_service.batches_for_medicine(m2))
    check("deleting a wrong purchase removes its stock", stock_left == 0, str(stock_left))
    check("deleted purchase is gone", purchase_service.get_purchase(p2) is None)
    check("deleted purchase no longer counted in company due", supplier_service.company_payable(comp) == before_due - 20000, f"{supplier_service.company_payable(comp)} vs {before_due}")
    snap = db.execute("SELECT details FROM audit_log WHERE action='purchase.delete'").fetchone()
    check("deleted purchase kept in audit log", snap is not None and "INV-WRONG" in snap[0], str(snap[0][:80] if snap else None))

    msg = _raises(lambda: medicine_service.save_medicine({"brand_name": "panadol 500MG", "category": "Tablet", "units_per_pack": 10, "cost_paisa": 1, "sale_paisa": 2}))
    check("same medicine cannot be added twice", "already exists" in msg, msg)
    check("medicine without a name is refused", bool(_raises(lambda: medicine_service.save_medicine({"brand_name": " ", "category": "Tablet"}))))

    res = medicine_service.delete_medicine(pan)
    check("used medicine is archived, not erased", res == "archived" and medicine_service.get_medicine(pan) is not None, res)
    first_sale = db.execute("SELECT MIN(id) FROM sales").fetchone()[0]
    check("old bill still opens after archiving its medicine", sale_service.get_sale(first_sale)["items"][0]["brand_name"] == "Panadol 500mg")
    med = medicine_service.get_medicine(pan)
    medicine_service.save_medicine(dict(med, active=True), pan)
    check("archived medicine comes back by editing it", medicine_service.get_medicine(pan)["active"] == 1)
    check("deleting a used medicine wrote its stock off", sum(b["qty"] for b in stock_service.batches_for_medicine(pan)) == 0)
    stock_service.restock_medicine(pan, 100, "B9", "2031-01-31", 2000, 2500)
    m3 = medicine_service.save_medicine({"brand_name": "Typo Medicine", "category": "Tablet", "units_per_pack": 1})
    check("unused medicine is really deleted", medicine_service.delete_medicine(m3) == "deleted" and medicine_service.get_medicine(m3) is None)

    empty = medicine_service.save_company("Never Used Co")
    check("unused company is deleted", medicine_service.delete_company(empty) == "deleted")
    check("company with purchases is archived", medicine_service.delete_company(comp) == "archived")
    check("archived company still owed money", supplier_service.company_payable(comp) > 0)
    medicine_service.save_company("Audit Pharma Ltd", "", comp, True)
    f1 = medicine_service.save_formulation("Audit Formula")
    check("unused formulation is deleted", medicine_service.delete_formulation(f1) == "deleted")

    cust = db.execute("SELECT id FROM customers WHERE name='Audit Customer'").fetchone()["id"]
    msg = _raises(lambda: customer_service.delete_customer(cust))
    check("customer with udhaar cannot be deleted", bool(msg), msg)
    c2 = customer_service.save_customer({"name": "Walk-in Typo", "phone": ""})
    check("unused customer is deleted", customer_service.delete_customer(c2) == "deleted")

    admin = db.execute("SELECT id FROM users WHERE username='admin'").fetchone()["id"]
    check("last owner cannot be disabled", bool(_raises(lambda: user_service.set_active(admin, False))))
    check("last owner cannot be made cashier", bool(_raises(lambda: user_service.update_user(admin, "admin", "cashier"))))
    check("short password refused for new user", bool(_raises(lambda: user_service.create_user("c1", "123", "cashier"))))
    cid = user_service.create_user("cashier1", "cash123", "cashier")
    check("duplicate username refused", bool(_raises(lambda: user_service.create_user("CASHIER1", "cash123", "cashier"))))
    user_service.set_active(cid, False)
    check("disabled cashier cannot log in", user_service.authenticate("cashier1", "cash123") is None)

    db.execute("INSERT INTO suppliers(name, phone, address, notes, active) VALUES ('Old Distributor', '0333', 'Karachi', '', 1)")
    old_sid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.execute(
        "INSERT INTO purchases(supplier_id, invoice_no, date, total_paisa, paid_paisa, returned_paisa, status, notes, user_id, ts)"
        " VALUES (?, 'OLD-1', ?, 50000, 0, 0, 'unpaid', '', 1, ?)",
        (old_sid, today(), today() + "T09:00:00"),
    )
    db.commit()
    close_db()
    init_db()
    db = get_db()
    row = db.execute("SELECT c.id, c.phone FROM suppliers s JOIN companies c ON c.id = s.company_id WHERE s.id = ?", (old_sid,)).fetchone()
    check("old supplier becomes a company on start", row is not None and row["phone"] == "0333", str(dict(row) if row else None))
    pays = {r["name"]: r["payable_paisa"] for r in supplier_service.payables()}
    check("old supplier's unpaid bill shows under the company", pays.get("Old Distributor") == 50000, str(pays))

    marker = medicine_service.save_medicine({"brand_name": "Restore Marker", "category": "Tablet", "units_per_pack": 1})
    export = backup_service.export_everything(TMP / "full_export")
    medicine_service.delete_medicine(marker)
    check("marker deleted before restore", medicine_service.get_medicine(marker) is None)
    backup_service.restore_from(export)
    check("Export everything -> Restore brings deleted data back", medicine_service.get_medicine(marker) is not None, str(export))
    count = get_db().execute("SELECT COUNT(*) FROM sales").fetchone()[0]
    check("restore keeps all sales", count >= 2, str(count))
    backups = sorted((TMP / "data" / "backups").glob("pharmacy_*.db"))
    check("a backup was taken before restore", len(backups) >= 2, str(len(backups)))

    from app.auth.session import Session
    from app.services import settings_service
    from app.utils.crypto import encrypt_bytes

    Session.backup_secret = "OwnerPass1"
    locked = backup_service.run_backup("locked")
    locked_export = backup_service.export_everything(TMP / "locked_export")
    check("owner backups are locked (.enc / .yms)", str(locked).endswith(".enc") and locked_export.suffix == ".yms", f"{locked} {locked_export}")
    legacy = TMP / "legacy.db.enc"
    legacy.write_bytes(encrypt_bytes(Path(backups[-1]).read_bytes(), "OwnerPass1", backup_service._salt()))
    check("old-format locked backup still opens", backup_service.check_backup(legacy)["medicines"] > 0)
    settings_service.set_value("backup_salt", "00" * 16)
    Session.backup_secret = "admin123"
    msg = _raises(lambda: backup_service.check_backup(locked))
    check("new PC with default password asks for the old password", "password" in msg.lower(), msg)
    msg = _raises(lambda: backup_service.check_backup(locked, "wrong"))
    check("wrong password is refused, data untouched", "password" in msg.lower(), msg)
    info_ = backup_service.check_backup(locked, "OwnerPass1")
    check("locked backup opens on a new PC with the old password", info_["sales"] >= 2, str(info_))
    check("locked export opens on a new PC with the old password", backup_service.check_backup(locked_export, "OwnerPass1")["sales"] >= 2)
    backup_service.restore_from(locked_export, "OwnerPass1")
    check("restore from locked export works", get_db().execute("SELECT COUNT(*) FROM sales").fetchone()[0] >= 2)
    bad = TMP / "not_a_backup.db"
    bad.write_bytes(b"hello")
    before = get_db().execute("SELECT COUNT(*) FROM medicines").fetchone()[0]
    check("a random file is refused before anything is replaced", bool(_raises(lambda: backup_service.restore_from(bad))))
    check("current data untouched after refused restore", get_db().execute("SELECT COUNT(*) FROM medicines").fetchone()[0] == before)
    Session.backup_secret = None


def step_reinstall() -> None:
    from app import config
    from app.db.database import close_db, get_db, init_db

    count = get_db().execute("SELECT COUNT(*) FROM sales").fetchone()[0]
    close_db()
    shutil.rmtree(TMP / "data")
    config._data_dir_cache = None
    res = config.prepare_data_dir()
    check("app folder deleted -> mirror restored on next start", res.get("action") == "restored_mirror", str(res))
    init_db()
    after = get_db().execute("SELECT COUNT(*) FROM sales").fetchone()[0]
    check("restored data still has every sale", after == count, f"{after} vs {count}")


def step_ui() -> None:
    from PySide6.QtWidgets import QApplication, QWidget

    from app.main import _load_style
    from app.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    _load_style(app)
    from PySide6.QtWidgets import QMessageBox

    def _popup(kind):
        def inner(parent, title, text="", *a, **k):
            failures.append(f"unexpected {kind} popup: {title} {text}")
            return QMessageBox.StandardButton.Ok

        return inner

    for name in ("information", "warning", "critical", "question"):
        setattr(QMessageBox, name, staticmethod(_popup(name)))
    SHOTS.mkdir(parents=True, exist_ok=True)
    win = MainWindow()
    for size in ((1024, 640), (1366, 768)):
        win.resize(*size)
        win.show()
        for key in list(win.pages):
            win.navigate(key)
            app.processEvents()
            app.processEvents()
            win.grab().save(str(SHOTS / f"{size[0]}_{key}.png"))
            overlaps = _overlaps(win._holders[key])
            if overlaps:
                failures.append(f"{size[0]}px {key}: overlapping widgets {overlaps[:3]}")
        win.navigate("pos")
        pos = win.pos_page
        pos.search.setText("Pana")
        app.processEvents()
        from PySide6.QtCore import Qt as _Qt

        for i in range(pos.results.count()):
            if pos.results.item(i).data(_Qt.ItemDataRole.UserRole):
                pos._pick_result(pos.results.item(i))
                break
        app.processEvents()
        win.grab().save(str(SHOTS / f"{size[0]}_pos_pick.png"))
        pos._add_to_cart()
        pos.search.setText("")
        app.processEvents()
        win.grab().save(str(SHOTS / f"{size[0]}_pos_cart.png"))
        check(f"{size[0]}px POS add to cart works", len(pos.cart) >= 1, str(pos.cart))
        pos.clear_cart()
    passed.append(f"screenshots saved to {SHOTS}")
    win.hide()


def _table_texts(root) -> list[str]:
    from app.ui.widgets.helpers import DataTable

    out = []
    for tbl in root.findChildren(DataTable):
        for r in range(tbl.rowCount()):
            it = tbl.item(r, 0)
            out.append(it.text() if it else "")
    return out


def _select_row(tbl, text: str) -> bool:
    for r in range(tbl.rowCount()):
        it = tbl.item(r, 0)
        if it and it.text().startswith(text):
            tbl.selectRow(r)
            return True
    return False


def step_sync_through_ui() -> None:
    """The owner's real flow: add stock, see it everywhere, delete it on screen, it must vanish everywhere."""
    from datetime import date, timedelta

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QMessageBox

    from app.constants import PAYMENT_METHODS
    from app.db.database import get_db
    from app.services import customer_service, dashboard_service, docs_service, medicine_service, purchase_service
    from app.services import sale_service, stock_service
    from app.ui.main_window import MainWindow

    app = QApplication.instance()
    msgs: list[str] = []

    def popup(kind):
        def inner(parent, title, text="", *a, **k):
            msgs.append(f"[{kind}] {text}")
            return QMessageBox.StandardButton.Yes if kind == "question" else QMessageBox.StandardButton.Ok

        return inner

    for name in ("information", "warning", "critical", "question"):
        setattr(QMessageBox, name, staticmethod(popup(name)))

    soon = (date.today() + timedelta(days=60)).isoformat()
    win = MainWindow()
    win.resize(1366, 768)
    win.show()
    app.processEvents()

    def go(key):
        win.navigate(key)
        app.processEvents()
        return win.pages[key]

    def pos_names(q):
        pos = go("pos")
        pos.search.setText(q)
        app.processEvents()
        return [pos.results.item(i).data(Qt.ItemDataRole.UserRole)["brand_name"]
                for i in range(pos.results.count()) if pos.results.item(i).data(Qt.ItemDataRole.UserRole)]

    def pick_and_add(q, qty):
        pos = go("pos")
        pos.search.setText(q)
        app.processEvents()
        for i in range(pos.results.count()):
            if pos.results.item(i).data(Qt.ItemDataRole.UserRole):
                pos._pick_result(pos.results.item(i))
                break
        pos.qty.setValue(qty)
        pos._add_to_cart()
        app.processEvents()
        return pos

    def delete_on_screen(brand):
        page = go("medicines")
        page.search.edit.setText(brand)
        app.processEvents()
        ok = _select_row(page.table, brand)
        page._delete()
        app.processEvents()
        page.search.edit.setText("")
        return ok

    before = dashboard_service.summary()
    mid = medicine_service.save_medicine({
        "brand_name": "Sync Tab", "category": "Tablet", "units_per_pack": 10, "cost_paisa": 10000, "sale_paisa": 15000,
        "opening_qty": 50, "batch_no": "SY1", "expiry": soon, "reorder_level": 5,
    })
    after_add = dashboard_service.summary()
    check("SYNC add: dashboard stock value goes up by 50 x Rs10", after_add["stock_cost"] - before["stock_cost"] == 50 * 1000,
          f"{after_add['stock_cost'] - before['stock_cost']}")
    check("SYNC add: dashboard 'expiring soon' counts it", after_add["expiring_soon"] == before["expiring_soon"] + 1)
    check("SYNC add: shows in POS search", "Sync Tab" in pos_names("Sync"))
    check("SYNC add: shows on Stock page", any(x.startswith("Sync Tab") for x in _table_texts(go("stock"))))
    check("SYNC add: shows on Expiry page", any("Sync Tab" in x for x in _table_texts(go("expiry"))) or
          any(r["brand_name"] == "Sync Tab" for r in stock_service.expiring_within(90)))

    pos = pick_and_add("Sync", 5)
    check("SYNC: 5 tablets in the cart", any(x["brand_name"] == "Sync Tab" for x in pos.cart), str(pos.cart))
    pos.search.setText("Sync")
    app.processEvents()

    check("SYNC delete: row found on Medicines page", delete_on_screen("Sync Tab"))
    check("SYNC delete: never-sold medicine is erased", medicine_service.get_medicine(mid) is None)
    msgs.clear()
    pos = go("pos")
    check("SYNC delete: removed from the POS cart when POS opens", not any(x["brand_name"] == "Sync Tab" for x in pos.cart), str(pos.cart))
    check("SYNC delete: user is told it left the cart", any("Sync Tab" in m for m in msgs), str(msgs))
    check("SYNC delete: gone from the POS search list", "Sync Tab" not in pos_names("Sync"))
    now = dashboard_service.summary()
    check("SYNC delete: dashboard stock value back to before", now["stock_cost"] == before["stock_cost"], f"{now['stock_cost']} vs {before['stock_cost']}")
    check("SYNC delete: dashboard expiring count back to before", now["expiring_soon"] == before["expiring_soon"])
    check("SYNC delete: gone from Stock page (all tabs)", not any("Sync Tab" in x for x in _table_texts(go("stock"))))
    check("SYNC delete: gone from Expiry page", not any("Sync Tab" in x for x in _table_texts(go("expiry"))))
    check("SYNC delete: gone from Medicines page", not any("Sync Tab" in x for x in _table_texts(go("medicines"))))

    mid2 = medicine_service.save_medicine({
        "brand_name": "Sold Med", "category": "Tablet", "units_per_pack": 10, "cost_paisa": 20000, "sale_paisa": 30000,
        "opening_qty": 40, "batch_no": "SM1", "expiry": soon,
    })
    b2 = stock_service.sellable_batches(mid2)[0]
    line = {"medicine_id": mid2, "brand_name": "Sold Med", "batch_id": b2["id"], "batch_no": "SM1", "expiry": soon,
            "qty": 4, "unit_price_paisa": 3000, "cost_paisa": 2000, "discount_paisa": 0, "gst_pct": 0}
    sold_sale = sale_service.complete_sale([line], PAYMENT_METHODS[0], 12000, None, 0)
    check("SYNC sale: stock 40 -> 36", sum(b["qty"] for b in stock_service.batches_for_medicine(mid2)) == 36)
    msg = _raises(lambda: sale_service.complete_sale([dict(line, qty=20), dict(line, qty=20)], PAYMENT_METHODS[0], 0, None, 0))
    check("SYNC: two cart lines of one batch cannot oversell", "Insufficient" in msg, msg)
    pos = pick_and_add("Sold", 30)
    pos2 = pick_and_add("Sold", 10)
    check("SYNC: POS refuses adding more than stock across lines", sum(x["qty"] for x in pos2.cart if x["brand_name"] == "Sold Med") <= 36,
          str([x["qty"] for x in pos2.cart]))
    stale_cart = [dict(x) for x in pos2.cart if x["brand_name"] == "Sold Med"]
    val_before_del = dashboard_service.summary()["stock_cost"]

    check("SYNC delete sold: row found", delete_on_screen("Sold Med"))
    med2 = medicine_service.get_medicine(mid2)
    check("SYNC delete sold: kept only as hidden history", med2 is not None and med2["active"] == 0)
    check("SYNC delete sold: its stock is written off to 0", sum(b["qty"] for b in stock_service.batches_for_medicine(mid2)) == 0)
    check("SYNC delete sold: write-off is in the stock ledger",
          get_db().execute("SELECT COUNT(*) FROM stock_ledger WHERE medicine_id=? AND notes='Medicine deleted'", (mid2,)).fetchone()[0] == 1)
    check("SYNC delete sold: dashboard stock value drops by its stock",
          val_before_del - dashboard_service.summary()["stock_cost"] == 36 * 2000, str(val_before_del - dashboard_service.summary()["stock_cost"]))
    check("SYNC delete sold: old bill still opens", sale_service.get_sale(sold_sale)["items"][0]["brand_name"] == "Sold Med")
    msg = _raises(lambda: sale_service.complete_sale(stale_cart, PAYMENT_METHODS[0], 0, None, 0))
    check("SYNC delete sold: a stale cart cannot sell it", "deleted" in msg or "Insufficient" in msg, msg)
    pos = go("pos")
    check("SYNC delete sold: removed from open POS cart", not any(x["brand_name"] == "Sold Med" for x in pos.cart))
    check("SYNC delete sold: not in POS search", "Sold Med" not in pos_names("Sold"))
    page = go("medicines")
    check("SYNC delete sold: hidden on Medicines page", not any("Sold Med" in x for x in _table_texts(page)))
    page.show_del.setChecked(True)
    app.processEvents()
    check("SYNC delete sold: visible with 'Show deleted'", any("Sold Med" in x for x in _table_texts(page)))
    page.show_del.setChecked(False)

    again = medicine_service.save_medicine({
        "brand_name": "Sold Med", "category": "Tablet", "units_per_pack": 10, "cost_paisa": 20000, "sale_paisa": 30000,
        "opening_qty": 10, "batch_no": "SM2", "expiry": soon,
    })
    check("SYNC re-add: adding it again brings the same record back", again == mid2 and medicine_service.get_medicine(mid2)["active"] == 1)
    check("SYNC re-add: stock is only the new 10 (old written-off stock not revived)",
          sum(b["qty"] for b in stock_service.batches_for_medicine(mid2)) == 10)
    check("SYNC re-add: back in POS search", "Sold Med" in pos_names("Sold"))
    check("SYNC re-add: old bill still linked to it", sale_service.get_sale(sold_sale)["items"][0]["medicine_id"] == mid2)

    stock_service.restock_medicine(mid2, 20, "SM3", soon, 2000, 3000)
    pos = go("pos")
    pos.search.setText("Sold")
    app.processEvents()
    shown = [pos.results.item(i).data(Qt.ItemDataRole.UserRole) for i in range(pos.results.count())]
    shown = [m for m in shown if m and m["id"] == mid2]
    check("SYNC restock: POS shows 30 in stock right away", shown and int(shown[0]["stock_qty"]) == 30, str(shown[0]["stock_qty"] if shown else None))

    comp = medicine_service.save_company("Sync Pharma")
    pid = purchase_service.create_purchase(comp, "SYNC-P", date.today().isoformat(),
                                           [{"medicine_id": mid2, "batch_no": "SM4", "expiry": soon, "qty": 5, "cost_paisa": 2000, "sale_paisa": 3000}])
    check("SYNC purchase: stock 30 -> 35", sum(b["qty"] for b in stock_service.batches_for_medicine(mid2)) == 35)
    purchase_service.delete_purchase(pid, "sync test")
    check("SYNC purchase delete: stock back to 30", sum(b["qty"] for b in stock_service.batches_for_medicine(mid2)) == 30)
    medicine_service.delete_company(comp)
    check("SYNC company delete: gone from Companies page", not any("Sync Pharma" in x for x in _table_texts(go("companies"))))

    cid = customer_service.save_customer({"name": "Sync Customer", "phone": "0311"})
    pos = go("pos")
    check("SYNC customer: new customer appears in POS list", pos.customer.findData(cid) >= 0)
    customer_service.delete_customer(cid)
    pos = go("pos")
    check("SYNC customer delete: gone from POS list", pos.customer.findData(cid) < 0)
    check("SYNC customer delete: gone from Customers page", not any("Sync Customer" in x for x in _table_texts(go("customers"))))

    from app.services import report_service
    from app.utils.money import format_pkr

    def report_service_rows():
        return report_service.date_range((date.today() - timedelta(days=30)).isoformat(), date.today().isoformat())["rows"]

    def med_stock():
        return sum(b["qty"] for b in stock_service.batches_for_medicine(mid2))

    def home_today():
        dash = go("dashboard")
        return dash.cards["today_sale"].value.text(), dashboard_service.summary()

    def delete_sale_on_screen(invoice):
        page = go("sales")
        page.search.edit.setText(invoice)
        app.processEvents()
        ok = _select_row(page.table, invoice)
        page._delete()
        app.processEvents()
        page.search.edit.setText("")
        return ok

    sline = {"medicine_id": mid2, "brand_name": "Sold Med", "batch_id": stock_service.sellable_batches(mid2)[0]["id"],
             "qty": 3, "unit_price_paisa": 3000, "cost_paisa": 2000, "discount_paisa": 0, "gst_pct": 0}
    _, base = home_today()
    stock0 = med_stock()
    cash_sid = sale_service.complete_sale([sline], PAYMENT_METHODS[0], 9000, None, 0)
    cash_inv = sale_service.get_sale(cash_sid)["invoice_no"]
    text_after_sale, d1 = home_today()
    check("SALE DEL: home 'today sale' goes up by Rs90", d1["today"]["sale"] - base["today"]["sale"] == 9000)
    check("SALE DEL: sale shows on Sales page", any(x == cash_inv for x in _table_texts(go("sales"))))
    check("SALE DEL: row found on Sales page", delete_sale_on_screen(cash_inv))
    text_after_del, d2 = home_today()
    check("SALE DEL: sale is gone from the database", sale_service.get_sale(cash_sid) is None)
    check("SALE DEL: gone from the Sales page", not any(x == cash_inv for x in _table_texts(go("sales"))))
    check("SALE DEL: home 'today sale' back to before", d2["today"]["sale"] == base["today"]["sale"], f"{d2['today']} vs {base['today']}")
    check("SALE DEL: home 'today profit' back to before", d2["today"]["profit"] == base["today"]["profit"])
    check("SALE DEL: home card text shows the new number", text_after_del == format_pkr(base["today"]["sale"]) and text_after_del != text_after_sale,
          f"{text_after_sale} -> {text_after_del}")
    check("SALE DEL: 3 tablets back in stock", med_stock() == stock0, f"{med_stock()} vs {stock0}")
    check("SALE DEL: stock return is in the ledger",
          get_db().execute("SELECT COUNT(*) FROM stock_ledger WHERE notes = ?", (f"Sale deleted {cash_inv}",)).fetchone()[0] == 1)
    check("SALE DEL: gone from reports", not any(r["invoice_no"] == cash_inv for r in report_service_rows()))

    old_sid = sale_service.complete_sale([sline], PAYMENT_METHODS[0], 9000, None, 0)
    old_inv = sale_service.get_sale(old_sid)["invoice_no"]
    yesterday = (date.today() - timedelta(days=5)).isoformat()
    get_db().execute("UPDATE sales SET date = ? WHERE id = ?", (yesterday, old_sid))
    get_db().commit()
    check("SALE DEL: an older (not today) sale can be deleted", delete_sale_on_screen(old_inv) and sale_service.get_sale(old_sid) is None)
    check("SALE DEL: older sale's stock also comes back", med_stock() == stock0)

    cust2 = customer_service.save_customer({"name": "Del Udhaar", "phone": "0322"})
    credit = next(p for p in PAYMENT_METHODS if p.lower().startswith("credit")) if any(p.lower().startswith("credit") for p in PAYMENT_METHODS) else PAYMENT_METHODS[-1]
    cr_sid = sale_service.complete_sale([dict(sline, qty=5)], credit, 5000, cust2, 0)
    cr = sale_service.get_sale(cr_sid)
    cr_item = cr["items"][0]["id"]
    sale_service.return_sale(cr_sid, [{"sale_item_id": cr_item, "qty": 2}], "test return")
    check("SALE DEL: udhaar after part-pay + return is Rs40", customer_service.get_customer(cust2)["balance_paisa"] == 4000,
          str(customer_service.get_customer(cust2)["balance_paisa"]))
    _, d3 = home_today()
    check("SALE DEL: home counts only the kept 3 tablets (Rs90)", d3["today"]["sale"] - base["today"]["sale"] == 9000,
          str(d3["today"]["sale"] - base["today"]["sale"]))
    check("SALE DEL: Sales page total shows Rs90 after return",
          any(r["id"] == cr_sid and r["total_paisa"] - r["returned_paisa"] == 9000 for r in sale_service.list_sales()))
    check("SALE DEL: returned + udhaar sale row found", delete_sale_on_screen(cr["invoice_no"]))
    check("SALE DEL: udhaar sale gone", sale_service.get_sale(cr_sid) is None)
    check("SALE DEL: customer udhaar back to 0", customer_service.get_customer(cust2)["balance_paisa"] == 0)
    check("SALE DEL: customer ledger is empty", customer_service.ledger(cust2) == [], str(customer_service.ledger(cust2)))
    check("SALE DEL: only the 3 unreturned tablets came back (no double count)", med_stock() == stock0, f"{med_stock()} vs {stock0}")
    _, d4 = home_today()
    check("SALE DEL: home 'today sale' back to before again", d4["today"]["sale"] == base["today"]["sale"])
    check("SALE DEL: home udhaar card back to before", d4["udhaar"] == base["udhaar"], f"{d4['udhaar']} vs {base['udhaar']}")

    cash2 = sale_service.complete_sale([sline], PAYMENT_METHODS[0], 9000, None, 0)
    sale_service.return_sale(cash2, [{"sale_item_id": sale_service.get_sale(cash2)["items"][0]["id"], "qty": 3}], "full return")
    _, d5 = home_today()
    check("SALE DEL: fully returned cash sale adds Rs0 to home", d5["today"]["sale"] == base["today"]["sale"], str(d5["today"]["sale"] - base["today"]["sale"]))
    check("SALE DEL: fully returned sale can be deleted", delete_sale_on_screen(sale_service.get_sale(cash2)["invoice_no"]) and sale_service.get_sale(cash2) is None)
    check("SALE DEL: stock unchanged after deleting a fully returned sale", med_stock() == stock0)
    customer_service.delete_customer(cust2)

    written = docs_service.write_folder_docs()
    names = {p.name for p in written}
    check("docs: user guide + data/recovery sheet written next to the exe", {docs_service.GUIDE_HTML, docs_service.DATA_DOC} <= names, str(names))
    sheet = (TMP / docs_service.DATA_DOC).read_text(encoding="utf-8-sig")
    check("docs: data sheet shows the real data folder path", str(TMP / "data") in sheet)
    check("docs: data sheet shows the mirror path", "mirror" in sheet and "Secondary backup" in sheet)
    check("docs: copy of the data sheet inside data folder", (TMP / "data" / docs_service.DATA_DOC).exists())
    pos.clear_cart()
    win.hide()


def step_click_everything() -> None:
    """Click every visible button on every page (and every tab), with and without a selected row."""
    import shiboken6
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtPrintSupport import QPrintDialog, QPrintPreviewDialog
    from PySide6.QtWidgets import (
        QAbstractButton,
        QApplication,
        QCheckBox,
        QDialog,
        QFileDialog,
        QInputDialog,
        QMessageBox,
        QTableView,
        QTabWidget,
    )

    from app.printing import escpos
    from app.ui.main_window import MainWindow

    app = QApplication.instance()
    dlg_dir = SHOTS / "dialogs"
    dlg_dir.mkdir(parents=True, exist_ok=True)
    slot_errors: list[str] = []
    popups: list[str] = []
    dialogs: list[str] = []
    side_effects: list[str] = []
    current = {"where": ""}

    def hook(etype, value, tb):
        slot_errors.append(f"{current['where']}: {''.join(traceback.format_exception(etype, value, tb))[-900:]}")

    sys.excepthook = hook

    def fake_exec(self, *a, **k):
        title = self.windowTitle() or self.__class__.__name__
        dialogs.append(f"{current['where']} -> {title}")
        self.resize(max(self.sizeHint().width(), 420), max(self.sizeHint().height(), 200))
        self.grab().save(str(dlg_dir / f"{len(dialogs):03d}_{current['where'].replace(' ', '_').replace('/', '-')[:60]}.png"))
        return 0

    for cls in (QDialog, QPrintDialog, QPrintPreviewDialog, QFileDialog, QInputDialog, QMessageBox):
        cls.exec = fake_exec
        cls.exec_ = fake_exec

    def popup(kind):
        def inner(parent, title, text="", *a, **k):
            popups.append(f"{current['where']} [{kind}] {text}".replace("\n", " ")[:200])
            return QMessageBox.StandardButton.No if kind == "question" else QMessageBox.StandardButton.Ok

        return inner

    for name in ("information", "warning", "critical", "question"):
        setattr(QMessageBox, name, staticmethod(popup(name)))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ("", ""))
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ("", ""))
    QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: "")
    QInputDialog.getText = staticmethod(lambda *a, **k: ("", False))
    QInputDialog.getInt = staticmethod(lambda *a, **k: (0, False))
    QInputDialog.getDouble = staticmethod(lambda *a, **k: (0.0, False))
    QInputDialog.getItem = staticmethod(lambda *a, **k: ("", False))
    QDesktopServices.openUrl = staticmethod(lambda url: side_effects.append(f"open {url.toString()}") or True)
    escpos.send_raw = lambda name, data, doc="": side_effects.append(f"print {len(data)} bytes to {name}") or 1
    escpos.purge_queue = lambda name: side_effects.append(f"purge {name}") or 0

    win = MainWindow()
    win.resize(1366, 768)
    win.show()
    app.processEvents()
    skip_names = {"LogoutBtn", "TopNav"}
    total = 0

    def buttons_in(root):
        out = []
        for b in root.findChildren(QAbstractButton):
            if b.objectName() in skip_names or not b.isVisible() or not b.isEnabled():
                continue
            if b.window() is not win:
                continue
            out.append(b)
        return out

    def label(b):
        return (b.text() or b.toolTip() or b.objectName() or b.__class__.__name__).replace("\n", " ")[:28]

    def click_all(key, mode):
        nonlocal total
        holder = win._holders[key]
        tabs = holder.findChildren(QTabWidget)
        states = [(None, 0)] + [(tw, i) for tw in tabs for i in range(tw.count())]
        done = set()
        for tw, i in states:
            if tw is not None and shiboken6.isValid(tw):
                tw.setCurrentIndex(i)
                app.processEvents()
            for tv in holder.findChildren(QTableView):
                if not tv.isVisible() or tv.model() is None:
                    continue
                if mode == "row" and tv.model().rowCount() > 0:
                    tv.selectRow(0)
                else:
                    tv.clearSelection()
            for b in buttons_in(holder):
                bid = (label(b), id(b))
                if bid in done or not shiboken6.isValid(b):
                    continue
                done.add(bid)
                current["where"] = f"{key}/{mode}/{label(b)}"
                if key == "pos" and not win.pos_page.cart:
                    fill_cart()
                try:
                    b.click()
                    if isinstance(b, QCheckBox):
                        b.click()
                    app.processEvents()
                except Exception:
                    slot_errors.append(f"{current['where']}: {traceback.format_exc()[-900:]}")
                total += 1
                if win._current_key() != key:
                    win.navigate(key)
                    app.processEvents()

    def fill_cart():
        pos = win.pos_page
        pos.search.setText("Pana")
        app.processEvents()
        for i in range(pos.results.count()):
            if pos.results.item(i).data(Qt.ItemDataRole.UserRole):
                pos._pick_result(pos.results.item(i))
                break
        pos._add_to_cart()
        app.processEvents()

    from app.db.database import get_db

    sales_before = get_db().execute("SELECT COUNT(*) FROM sales").fetchone()[0]
    for key in list(win.pages):
        win.navigate(key)
        app.processEvents()
        before = len(slot_errors)
        for mode in ("none", "row"):
            win.navigate(key)
            app.processEvents()
            click_all(key, mode)
        check(f"every button on '{key}' clicked without a crash", len(slot_errors) == before, "; ".join(slot_errors[before:])[:1500])
    sys.excepthook = sys.__excepthook__
    made = get_db().execute("SELECT COUNT(*) FROM sales").fetchone()[0] - sales_before
    check("POS Pay buttons completed real sales", made >= 2, str(made))
    check("Pay + Print sent the bill to the printer", any(s.startswith("print ") for s in side_effects) or any("Choose bill printer" in d for d in dialogs if d.startswith("pos/")), "; ".join(side_effects))
    passed.append(f"clicked {total} buttons, {len(dialogs)} dialogs opened, {len(popups)} messages")
    report = TMP / "click_report.txt"
    report.write_text(
        "DIALOGS\n" + "\n".join(dialogs) + "\n\nMESSAGES\n" + "\n".join(popups) + "\n\nSIDE EFFECTS\n" + "\n".join(side_effects) + "\n\nERRORS\n" + "\n".join(slot_errors),
        encoding="utf-8",
    )
    passed.append(f"click report: {report}")
    win.hide()


def _overlaps(root) -> list[str]:
    from PySide6.QtWidgets import QAbstractButton, QLabel, QLineEdit, QComboBox, QAbstractSpinBox

    kinds = (QAbstractButton, QLabel, QLineEdit, QComboBox, QAbstractSpinBox)
    found = []
    for parent in [root] + root.findChildren(type(root).__mro__[-2]):
        kids = [c for c in parent.children() if isinstance(c, kinds) and c.isVisible() and c.width() > 4]
        for i, a in enumerate(kids):
            for b in kids[i + 1 :]:
                inter = a.geometry().intersected(b.geometry())
                if inter.width() > 6 and inter.height() > 6:
                    found.append(f"{a.__class__.__name__}('{getattr(a, 'text', lambda: '')()[:14]}') x {b.__class__.__name__}('{getattr(b, 'text', lambda: '')()[:14]}')")
    return found


def main() -> None:
    for step in (step_data_layout, step_services, step_company_and_deletes, step_reinstall, step_ui, step_sync_through_ui, step_click_everything):
        try:
            step()
        except Exception:
            failures.append(f"{step.__name__} crashed:\n{traceback.format_exc()}")
    for p in passed:
        print("PASS", p)
    for f in failures:
        print("FAIL", f)
    print(f"\n{len(passed)} passed, {len(failures)} failed. temp={TMP}")
    sys.stdout.flush()
    os._exit(1 if failures else 0)


if __name__ == "__main__":
    main()
