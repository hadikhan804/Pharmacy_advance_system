from __future__ import annotations

import json
import re
import sqlite3
import shutil
import tempfile
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

from openpyxl import Workbook

from app.auth.session import Session
from app.config import backup_default_dir, db_path
from app.db.database import close_db, get_db
from app.services import audit_service, settings_service
from app.utils.crypto import decrypt_bytes, encrypt_bytes, new_salt
from app.utils.dates import now_iso, today
from app.utils.money import from_paisa

_running = False


def _salt() -> bytes:
    raw = settings_service.get("backup_salt", "")
    if raw:
        return bytes.fromhex(raw)
    salt = new_salt()
    settings_service.set_value("backup_salt", salt.hex())
    return salt


def _password() -> str | None:
    return Session.backup_secret


def local_backup_dir() -> Path:
    path = Path(settings_service.get("backup_folder") or backup_default_dir())
    path.mkdir(parents=True, exist_ok=True)
    return path


def secondary_dir() -> Path | None:
    raw = (settings_service.get("secondary_backup_folder") or "").strip()
    if not raw:
        return None
    return Path(raw)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def _snapshot_db(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    conn = get_db()
    out = sqlite3.connect(str(dest))
    try:
        conn.backup(out)
        out.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        out.close()


def _integrity_ok(db_file: Path) -> bool:
    try:
        conn = sqlite3.connect(str(db_file))
        row = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()
        return bool(row and row[0] == "ok")
    except sqlite3.Error:
        return False


def _write_encrypted(src: Path, dest: Path) -> None:
    password = _password()
    data = src.read_bytes()
    if password:
        dest.write_bytes(encrypt_bytes(data, password, _salt()))
    else:
        dest.write_bytes(data)


def _read_maybe_encrypted(path: Path) -> bytes:
    data = path.read_bytes()
    password = _password()
    if path.suffix in {".enc", ".yms"} or path.name.endswith(".db.enc") or path.name.endswith(".xlsx.enc"):
        if not password:
            raise ValueError("Owner password required to decrypt this backup")
        return decrypt_bytes(data, password, _salt())
    if password:
        try:
            return decrypt_bytes(data, password, _salt())
        except ValueError:
            return data
    return data


def _log(location: str, kind: str, triggered_by: str, ok: int | None, size: int, details: str = "") -> None:
    get_db().execute(
        """
        INSERT INTO backup_log(ts, location, kind, triggered_by, integrity_ok, size_bytes, details)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (now_iso(), location, kind, triggered_by, ok, size, details),
    )
    get_db().commit()


def _write_xlsx(path: Path) -> None:
    from app.services import customer_service, medicine_service, stock_service, supplier_service
    from app.services.dashboard_service import period_totals
    from app.utils.dates import month_start

    wb = Workbook()
    med = wb.active
    med.title = "Medicines"
    med.append(["Brand", "Generic", "Company", "Formulation", "Barcode", "GST%", "Reorder", "Stock"])
    for r in medicine_service.list_medicines():
        med.append(
            [
                r["brand_name"],
                r["generic_name"],
                r.get("company_name"),
                r.get("formulation_name"),
                r.get("barcode"),
                r.get("gst_pct"),
                r.get("reorder_level"),
                r.get("stock_qty"),
            ]
        )
    st = wb.create_sheet("Stock")
    st.append(["Brand", "Qty", "Reorder", "Value cost", "Value sale"])
    for r in stock_service.current_stock():
        st.append([r["brand_name"], r["qty"], r["reorder_level"], from_paisa(r["value_cost"]), from_paisa(r["value_sale"])])
    sales = wb.create_sheet("SalesSummary")
    tday = today()
    d = period_totals(tday, tday)
    m = period_totals(month_start(), tday)
    sales.append(["Period", "Sale PKR", "Profit PKR"])
    sales.append(["Today", from_paisa(d["sale"]), from_paisa(d["profit"])])
    sales.append(["This month", from_paisa(m["sale"]), from_paisa(m["profit"])])
    ud = wb.create_sheet("Udhaar")
    ud.append(["Name", "Phone", "Balance PKR", "Oldest due"])
    for r in customer_service.udhaar_list():
        ud.append([r["name"], r["phone"], from_paisa(r["balance_paisa"]), r["oldest_due"]])
    pay = wb.create_sheet("Payables")
    pay.append(["Name", "Phone", "Payable PKR"])
    for r in supplier_service.payables():
        pay.append([r["name"], r["phone"], from_paisa(r["payable_paisa"])])
    wb.save(str(path))


def _copy_to_secondary(files: list[Path]) -> bool:
    dest = secondary_dir()
    if not dest:
        return True
    try:
        dest.mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.copy2(f, dest / f.name)
        settings_service.set_value("pending_secondary", "")
        return True
    except OSError:
        pending = json.dumps([str(f) for f in files])
        settings_service.set_value("pending_secondary", pending)
        return False


def retry_pending_secondary() -> bool:
    raw = settings_service.get("pending_secondary", "")
    if not raw:
        return True
    try:
        paths = [Path(p) for p in json.loads(raw)]
        paths = [p for p in paths if p.exists()]
        if not paths:
            settings_service.set_value("pending_secondary", "")
            return True
        return _copy_to_secondary(paths)
    except (json.JSONDecodeError, OSError):
        return False


def _prune(folder: Path) -> None:
    files = sorted(folder.glob("pharmacy_*.db*")) + sorted(folder.glob("pharmacy_*.xlsx*"))
    by_day: dict[str, list[Path]] = {}
    by_month: dict[str, list[Path]] = {}
    pat = re.compile(r"pharmacy_(\d{4}-\d{2}-\d{2})_")
    for f in files:
        m = pat.search(f.name)
        if not m:
            continue
        day = m.group(1)
        by_day.setdefault(day, []).append(f)
        by_month.setdefault(day[:7], []).append(f)
    keep: set[Path] = set()
    days = sorted(by_day.keys(), reverse=True)[:30]
    for d in days:
        keep.update(by_day[d])
    months = sorted(by_month.keys(), reverse=True)[:12]
    for mo in months:
        keep.update(by_month[mo])
    for f in files:
        if f not in keep:
            try:
                f.unlink()
            except OSError:
                pass


def status() -> dict:
    last = settings_service.get("last_verified_backup_at", "")
    pending = bool(settings_service.get("pending_secondary", ""))
    stale = True
    if last:
        try:
            dt = datetime.strptime(last[:19], "%Y-%m-%d %H:%M:%S")
            stale = datetime.now() - dt > timedelta(hours=48)
        except ValueError:
            stale = True
    warning = pending or stale or not last
    return {
        "last_verified": last,
        "pending_secondary": pending,
        "stale": stale,
        "warning": warning,
    }


def list_backups(limit: int = 40) -> list[dict]:
    from app.db.database import rows_to_dicts

    return rows_to_dicts(
        get_db().execute("SELECT * FROM backup_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    )


def run_backup(triggered_by: str = "manual") -> Path:
    global _running
    if _running:
        return local_backup_dir()
    _running = True
    try:
        folder = local_backup_dir()
        stamp = _stamp()
        tmp = Path(tempfile.mkdtemp(prefix="yms_bak_"))
        raw_db = tmp / "pharmacy.db"
        raw_xlsx = tmp / "export.xlsx"
        _snapshot_db(raw_db)
        ok = _integrity_ok(raw_db)
        _write_xlsx(raw_xlsx)
        enc = bool(_password())
        db_name = f"pharmacy_{stamp}.db" + (".enc" if enc else "")
        xlsx_name = f"pharmacy_{stamp}.xlsx" + (".enc" if enc else "")
        db_out = folder / db_name
        xlsx_out = folder / xlsx_name
        _write_encrypted(raw_db, db_out)
        _write_encrypted(raw_xlsx, xlsx_out)
        shutil.rmtree(tmp, ignore_errors=True)
        if ok:
            settings_service.set_value("last_verified_backup_at", now_iso())
            settings_service.set_value("last_auto_backup_date", today())
        _log(str(db_out), "db", triggered_by, 1 if ok else 0, db_out.stat().st_size, "integrity " + ("ok" if ok else "FAIL"))
        _log(str(xlsx_out), "xlsx", triggered_by, 1, xlsx_out.stat().st_size, "")
        audit_service.log("backup.create", "backup", None, f"{triggered_by} {db_out}")
        copied = _copy_to_secondary([db_out, xlsx_out])
        if not copied:
            _log(str(secondary_dir() or ""), "secondary", triggered_by, 0, 0, "queued")
        _prune(folder)
        sec = secondary_dir()
        if sec and sec.exists():
            _prune(sec)
        return db_out
    finally:
        _running = False


def backup_to(folder: str | Path | None = None) -> Path:
    if folder:
        settings_service.set_value("backup_folder", str(folder))
    return run_backup("manual")


def event_backup(reason: str) -> None:
    if not _password():
        return
    try:
        run_backup(reason)
    except Exception:
        pass


def auto_daily_if_needed() -> Path | None:
    last = settings_service.get("last_auto_backup_date", "")
    retry_pending_secondary()
    if not _password():
        return None
    if last == today() and not settings_service.get("pending_secondary"):
        return None
    return run_backup("daily")


def restore_from(file_path: str | Path) -> None:
    src = Path(file_path)
    if not src.exists():
        raise ValueError("Backup file not found")
    run_backup("pre-restore")
    conn = get_db()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    close_db()
    target = db_path()
    for suffix in ("-wal", "-shm"):
        extra = Path(str(target) + suffix)
        if extra.exists():
            extra.unlink()
    if src.suffix.lower() in {".zip", ".yms"} or src.name.endswith(".zip.enc"):
        data = _read_maybe_encrypted(src) if src.name.endswith(".enc") or src.suffix == ".yms" else src.read_bytes()
        tmp = Path(tempfile.mkdtemp(prefix="yms_rst_"))
        zpath = tmp / "pack.zip"
        zpath.write_bytes(data)
        with zipfile.ZipFile(zpath, "r") as zf:
            zf.extractall(tmp)
        db_files = list(tmp.rglob("*.db"))
        if not db_files:
            raise ValueError("No database found in export")
        shutil.copy2(db_files[0], target)
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        raw = _read_maybe_encrypted(src)
        if raw[:16].startswith(b"SQLite format 3"):
            target.write_bytes(raw)
        else:
            raise ValueError("File is not a pharmacy database")
    from app.db.database import init_db

    init_db()
    audit_service.log("backup.restore", "backup", None, str(src))
    get_db().commit()


def export_everything(dest_path: str | Path) -> Path:
    dest = Path(dest_path)
    tmp = Path(tempfile.mkdtemp(prefix="yms_exp_"))
    db_file = tmp / "pharmacy.db"
    xlsx_file = tmp / "business_export.xlsx"
    readme = tmp / "readme.txt"
    _snapshot_db(db_file)
    _write_xlsx(xlsx_file)
    readme.write_text(
        "Yasir Medical Store — full export\n\n"
        "To restore on another PC:\n"
        "1. Install Yasir Medical Store.\n"
        "2. Open the app and sign in as owner.\n"
        "3. Settings → Restore, and pick pharmacy.db from this folder "
        "(or this .yms file if it is still encrypted).\n"
        "4. If the file is encrypted, use the same owner password used when exporting.\n",
        encoding="utf-8",
    )
    zip_path = tmp / "pack.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(db_file, "pharmacy.db")
        zf.write(xlsx_file, "business_export.xlsx")
        zf.write(readme, "readme.txt")
    payload = zip_path.read_bytes()
    password = _password()
    if password:
        dest = dest.with_suffix(".yms")
        dest.write_bytes(encrypt_bytes(payload, password, _salt()))
    else:
        dest = dest.with_suffix(".zip")
        dest.write_bytes(payload)
    shutil.rmtree(tmp, ignore_errors=True)
    _log(str(dest), "zip", "export-everything", 1, dest.stat().st_size, "")
    audit_service.log("backup.export_all", "backup", None, str(dest))
    return dest


def scan_recover_candidates() -> list[Path]:
    homes = Path.home()
    roots = [
        homes / "Documents" / "YasirMedicalStoreBackups",
        homes / "Desktop",
        homes / "Downloads",
        homes / "OneDrive" / "YasirMedicalStoreBackups",
        homes / "Google Drive" / "YasirMedicalStoreBackups",
        homes / "Dropbox" / "YasirMedicalStoreBackups",
        Path(os_environ_appdata()) / "YasirMedicalStore" / "backups",
        Path(os_environ_appdata()) / "PharmacyPOS" / "backups",
        local_backup_dir(),
    ]
    for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
        drive = Path(f"{letter}:/")
        if drive.exists():
            roots.append(drive)
            roots.append(drive / "YasirMedicalStoreBackups")
    found: list[Path] = []
    seen: set[str] = set()
    patterns = ("pharmacy.db", "pharmacy_*.db", "pharmacy_*.db.enc", "*.yms", "Yasir*.zip", "Yasir*.yms")

    def _add(f: Path) -> None:
        try:
            if f.is_file() and f.stat().st_size > 100 and str(f) not in seen:
                seen.add(str(f))
                found.append(f)
        except OSError:
            pass

    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        try:
            is_drive_root = root.parent == root
            for pat in patterns:
                for f in root.glob(pat):
                    _add(f)
                if is_drive_root:
                    continue
                for f in root.glob("*/" + pat):
                    _add(f)
        except OSError:
            continue
    found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return found[:30]


def os_environ_appdata() -> str:
    import os

    return os.environ.get("APPDATA") or str(Path.home())


def suggested_secondary_folders() -> list[Path]:
    homes = Path.home()
    out = [
        homes / "Documents" / "YasirMedicalStoreBackups",
        homes / "OneDrive" / "YasirMedicalStoreBackups",
        homes / "Google Drive" / "YasirMedicalStoreBackups",
        homes / "Dropbox" / "YasirMedicalStoreBackups",
    ]
    for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
        drive = Path(f"{letter}:/")
        if drive.exists():
            out.append(drive / "YasirMedicalStoreBackups")
    return [p for p in out if p.parent.exists() or p.exists()]
