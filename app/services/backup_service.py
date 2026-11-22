from __future__ import annotations

import json
import os
import re
import sqlite3
import shutil
import tempfile
import time
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

from openpyxl import Workbook

from app.auth.session import Session
from app.config import app_dir, backup_default_dir, db_path, mirror_db_path
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
    raw = (settings_service.get("backup_folder") or "").strip()
    if not raw:
        return backup_default_dir()
    path = Path(raw)
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path
    except OSError:
        return backup_default_dir()


def normalize_settings() -> None:
    """Point an old '<app>/backups' setting at the new data/backups folder."""
    raw = (settings_service.get("backup_folder") or "").strip()
    legacy = {
        str(app_dir() / "backups"),
        str(Path(os_environ_appdata()) / "HadiPharmacy" / "backups"),
        str(Path(os_environ_appdata()) / "YasirMedicalStore" / "backups"),
    }
    if not raw or raw in legacy:
        settings_service.set_value("backup_folder", str(backup_default_dir()))


_last_mirror = 0.0
MIRROR_EVERY_SECONDS = 600


def _sales_count(db_file: Path) -> int:
    try:
        conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
        try:
            return int(conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0])
        finally:
            conn.close()
    except sqlite3.Error:
        return -1


def mirror_now(force: bool = False) -> Path | None:
    """Keep a plain copy of the DB outside the app folder so a reinstall can bring it back."""
    global _last_mirror
    if not force and time.monotonic() - _last_mirror < MIRROR_EVERY_SECONDS:
        return None
    dest = mirror_db_path()
    meta = dest.with_suffix(".json")
    tmp = dest.with_suffix(".tmp")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        source = str(db_path())
        if dest.exists() and meta.exists():
            prev = json.loads(meta.read_text(encoding="utf-8")).get("source")
            if prev and prev != source:
                mine = int(get_db().execute("SELECT COUNT(*) FROM sales").fetchone()[0])
                if mine < _sales_count(dest):
                    return None
        _snapshot_db(tmp)
        if not _integrity_ok(tmp):
            tmp.unlink(missing_ok=True)
            return None
        os.replace(tmp, dest)
        meta.write_text(json.dumps({"source": source, "ts": now_iso()}), encoding="utf-8")
        _last_mirror = time.monotonic()
        return dest
    except (OSError, sqlite3.Error, ValueError):
        tmp.unlink(missing_ok=True)
        return None


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
    conn.commit()
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


ENC_MAGIC = b"YMSENC1\n"


class PasswordNeeded(ValueError):
    """The backup is encrypted and the current owner password does not open it."""


def _encrypt(data: bytes, password: str) -> bytes:
    salt = _salt()
    return ENC_MAGIC + salt + encrypt_bytes(data, password, salt)


def _legacy_salts() -> list[bytes]:
    """Old backups did not carry their salt; it lived only in the database (and its mirror copy)."""
    found = [_salt()]
    for db_file in (mirror_db_path(),):
        try:
            conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
            try:
                row = conn.execute("SELECT value FROM settings WHERE key='backup_salt'").fetchone()
            finally:
                conn.close()
            if row and row[0] and bytes.fromhex(row[0]) not in found:
                found.append(bytes.fromhex(row[0]))
        except (sqlite3.Error, ValueError, OSError):
            continue
    return found


def _decrypt(data: bytes, password: str) -> bytes:
    if data.startswith(ENC_MAGIC):
        salt = data[len(ENC_MAGIC) : len(ENC_MAGIC) + 16]
        return decrypt_bytes(data[len(ENC_MAGIC) + 16 :], password, salt)
    last: Exception | None = None
    for salt in _legacy_salts():
        try:
            return decrypt_bytes(data, password, salt)
        except ValueError as exc:
            last = exc
    raise last or ValueError("Wrong password or damaged backup")


def _write_encrypted(src: Path, dest: Path) -> None:
    password = _password()
    data = src.read_bytes()
    if password:
        dest.write_bytes(_encrypt(data, password))
    else:
        dest.write_bytes(data)


def _is_plain(data: bytes) -> bool:
    return data[:16].startswith(b"SQLite format 3") or data[:2] == b"PK"


def _read_maybe_encrypted(path: Path, password: str | None = None) -> bytes:
    data = path.read_bytes()
    if _is_plain(data):
        return data
    candidates = [p for p in (password, _password()) if p]
    if not candidates:
        raise PasswordNeeded("This backup is locked with the owner password that was used when it was made.")
    for pw in candidates:
        try:
            return _decrypt(data, pw)
        except ValueError:
            continue
    raise PasswordNeeded("Wrong password for this backup. Enter the owner password that was used when it was made.")


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
        base = stamp
        n = 1
        while any(folder.glob(f"pharmacy_{stamp}.*")):
            n += 1
            stamp = f"{base}-{n}"
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
        get_db().commit()
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
    try:
        run_backup(reason)
    except Exception:
        pass
    mirror_now(force=True)


def auto_daily_if_needed() -> Path | None:
    last = settings_service.get("last_auto_backup_date", "")
    retry_pending_secondary()
    if last == today() and not settings_service.get("pending_secondary"):
        return None
    try:
        return run_backup("daily")
    except Exception:
        return None


def _backup_db_bytes(src: Path, password: str | None) -> bytes:
    """SQLite bytes from a .db / .db.enc backup or a .zip / .yms export. Current data is not touched."""
    data = _read_maybe_encrypted(src, password)
    if data[:2] == b"PK":
        tmp = Path(tempfile.mkdtemp(prefix="yms_rst_"))
        try:
            zpath = tmp / "pack.zip"
            zpath.write_bytes(data)
            with zipfile.ZipFile(zpath, "r") as zf:
                names = [n for n in zf.namelist() if n.lower().endswith(".db")]
                if not names:
                    raise ValueError("No database found in this export")
                data = zf.read(names[0])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    if not data[:16].startswith(b"SQLite format 3"):
        raise ValueError("File is not a pharmacy database")
    return data


def check_backup(file_path: str | Path, password: str | None = None) -> dict:
    """Open a backup without restoring it. Raises PasswordNeeded / ValueError if it cannot be used."""
    src = Path(file_path)
    if not src.exists():
        raise ValueError("Backup file not found")
    data = _backup_db_bytes(src, password)
    tmp = Path(tempfile.mkdtemp(prefix="yms_chk_")) / "check.db"
    tmp.write_bytes(data)
    try:
        conn = sqlite3.connect(tmp)
        try:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("This backup file is damaged")
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"medicines", "sales", "settings"} <= tables:
                raise ValueError("This file is not a Hadi Pharmacy backup")
            info = {
                "medicines": conn.execute("SELECT COUNT(*) FROM medicines").fetchone()[0],
                "sales": conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0],
                "last_sale": conn.execute("SELECT MAX(date) FROM sales").fetchone()[0] or "",
            }
        finally:
            conn.close()
    finally:
        shutil.rmtree(tmp.parent, ignore_errors=True)
    return info


def restore_from(file_path: str | Path, password: str | None = None) -> None:
    src = Path(file_path)
    check_backup(src, password)
    data = _backup_db_bytes(src, password)
    run_backup("pre-restore")
    conn = get_db()
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    close_db()
    target = db_path()
    for suffix in ("-wal", "-shm"):
        extra = Path(str(target) + suffix)
        if extra.exists():
            extra.unlink()
    target.write_bytes(data)
    from app.db.database import init_db

    init_db()
    audit_service.log("backup.restore", "backup", None, str(src))
    get_db().commit()
    mirror_now(force=True)


def export_everything(dest_path: str | Path) -> Path:
    dest = Path(dest_path)
    tmp = Path(tempfile.mkdtemp(prefix="yms_exp_"))
    db_file = tmp / "pharmacy.db"
    xlsx_file = tmp / "business_export.xlsx"
    readme = tmp / "readme.txt"
    _snapshot_db(db_file)
    _write_xlsx(xlsx_file)
    readme.write_text(
        "Hadi Pharmacy — full export\n\n"
        "To restore on another PC:\n"
        "1. Install Hadi Pharmacy.\n"
        "2. Open the app and sign in as owner.\n"
        "3. Settings → Restore, and pick pharmacy.db from this folder "
        "(or this .yms file if it is still encrypted).\n"
        "4. If the file is locked (.yms), the app asks for the owner password that was used when exporting.\n",
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
        dest.write_bytes(_encrypt(payload, password))
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
        homes / "Documents" / "HadiPharmacyBackups",
        homes / "Documents" / "YasirMedicalStoreBackups",
        homes / "Desktop",
        homes / "Downloads",
        homes / "OneDrive" / "HadiPharmacyBackups",
        homes / "OneDrive" / "YasirMedicalStoreBackups",
        homes / "Google Drive" / "HadiPharmacyBackups",
        homes / "Google Drive" / "YasirMedicalStoreBackups",
        homes / "Dropbox" / "HadiPharmacyBackups",
        homes / "Dropbox" / "YasirMedicalStoreBackups",
        Path(os_environ_appdata()) / "HadiPharmacy" / "backups",
        Path(os_environ_appdata()) / "YasirMedicalStore" / "backups",
        Path(os_environ_appdata()) / "PharmacyPOS" / "backups",
        local_backup_dir(),
    ]
    for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
        drive = Path(f"{letter}:/")
        if drive.exists():
            roots.append(drive)
            roots.append(drive / "HadiPharmacyBackups")
            roots.append(drive / "YasirMedicalStoreBackups")
    found: list[Path] = []
    seen: set[str] = set()
    patterns = ("pharmacy.db", "pharmacy_*.db", "pharmacy_*.db.enc", "*.yms", "Hadi*.zip", "Hadi*.yms", "Yasir*.zip", "Yasir*.yms")

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
        homes / "Documents" / "HadiPharmacyBackups",
        homes / "OneDrive" / "HadiPharmacyBackups",
        homes / "Google Drive" / "HadiPharmacyBackups",
        homes / "Dropbox" / "HadiPharmacyBackups",
    ]
    for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
        drive = Path(f"{letter}:/")
        if drive.exists():
            out.append(drive / "HadiPharmacyBackups")
    return [p for p in out if p.parent.exists() or p.exists()]
