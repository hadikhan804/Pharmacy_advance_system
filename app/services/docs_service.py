"""Keep two guides next to HadiPharmacy.exe: the full user guide and a data / recovery sheet with real paths."""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

from app.config import APP_TITLE, STORE_PHONE, app_dir, data_dir, data_dir_override, db_path, is_frozen, mirror_db_path, resource_dir

GUIDE_HTML = "User Guide.html"
DATA_DOC = "DATA AND RECOVERY - READ ME.txt"


def guide_markdown() -> str:
    for p in (resource_dir() / "app" / "docs" / "user_guide.md", Path(__file__).resolve().parents[1] / "docs" / "user_guide.md"):
        if p.exists():
            return p.read_text(encoding="utf-8")
    return f"# {APP_TITLE}\n\nThe guide file is missing. Call {STORE_PHONE}."


def guide_html() -> str:
    from PySide6.QtGui import QTextDocument

    doc = QTextDocument()
    doc.setDefaultStyleSheet(
        "body{font-family:'Segoe UI',Arial;font-size:11pt} h1{color:#4b3fd1} h2{color:#4b3fd1;margin-top:18px}"
        " table{border-collapse:collapse} td,th{border:1px solid #bbb;padding:4px 8px} pre{background:#f3f3f3}"
    )
    doc.setMarkdown(guide_markdown())
    return doc.toHtml().replace("<head>", f"<head><title>{APP_TITLE} - User Guide</title>", 1)


def _size(p: Path) -> str:
    try:
        n = p.stat().st_size
    except OSError:
        return "missing"
    return f"{n / 1024 / 1024:.2f} MB" if n > 1024 * 1024 else f"{n / 1024:.0f} KB"


def _when(p: Path) -> str:
    try:
        return datetime.fromtimestamp(p.stat().st_mtime).strftime("%d-%m-%Y %I:%M %p")
    except OSError:
        return "never"


def data_doc_text() -> str:
    from app.db.database import get_db
    from app.services import backup_service

    db = get_db()

    def count(sql: str) -> int:
        try:
            return int(db.execute(sql).fetchone()[0])
        except Exception:
            return 0

    exe = Path(sys.executable).resolve() if is_frozen() else app_dir() / "HadiPharmacy.exe"
    data = data_dir()
    backups = Path(backup_service.local_backup_dir())
    files = sorted(backups.glob("pharmacy_*.db*"), key=lambda p: p.stat().st_mtime, reverse=True)
    latest = files[0] if files else None
    sec = backup_service.secondary_dir()
    mirror = mirror_db_path()
    st = backup_service.status()
    locked = any(str(f).endswith(".enc") for f in files[:5])
    now = datetime.now().strftime("%d-%m-%Y %I:%M %p")
    lines = [
        f"{APP_TITLE} - WHERE YOUR DATA IS AND HOW TO NEVER LOSE IT",
        "=" * 64,
        f"This file is rewritten automatically every time the program starts and closes. Last update: {now}",
        f"Support: {STORE_PHONE}",
        "",
        "1. YOUR DATA ON THIS COMPUTER (exact paths)",
        "-" * 64,
        f"Program (exe) ........ {exe}",
        f"DATA FOLDER .......... {data}",
        f"  Main database ...... {db_path()}   ({_size(db_path())}, saved {_when(db_path())})",
        f"  Backups ............ {backups}",
        f"  Saved bills ........ {data / 'bills'}",
        f"Safety copy (mirror) . {mirror}   ({_size(mirror)}, saved {_when(mirror)})",
        f"Secondary backup ..... {sec if sec else 'NOT SET  <-- set it in Settings > Secondary backup (USB / Google Drive)'}",
        "",
        "What is inside right now:",
        f"  Medicines: {count('SELECT COUNT(*) FROM medicines WHERE active = 1')}"
        f"   Sales/bills: {count('SELECT COUNT(*) FROM sales')}"
        f"   Customers: {count('SELECT COUNT(*) FROM customers WHERE active = 1')}"
        f"   Companies: {count('SELECT COUNT(*) FROM companies WHERE active = 1')}"
        f"   Purchases: {count('SELECT COUNT(*) FROM purchases')}",
        f"  Backup files: {len(files)}   Latest: {latest.name if latest else 'none yet'} ({_when(latest) if latest else '-'})",
        f"  Backup status: {'WARNING - take a backup (Settings > Backup now)' if st.get('warning') else 'OK'}",
        "  Backups are LOCKED with the owner password (.enc files). Remember it!" if locked else
        "  Backups are plain files (no password needed to restore).",
        "",
        "2. NEVER DO THESE",
        "-" * 64,
        "  - Never delete the 'data' folder. It IS your shop.",
        "  - Never copy only HadiPharmacy.exe to another place. Always copy the WHOLE folder",
        "    (HadiPharmacy.exe + _internal + data).",
        "  - Never copy the data folder while the program is open. Click Logout first.",
        "  - Never open the program from inside a zip file.",
        "",
        "3. THE EXE (PROGRAM) WAS DELETED, BUT THE DATA FOLDER IS STILL HERE",
        "-" * 64,
        "  1. Do NOT touch the data folder.",
        f"  2. Put HadiPharmacy-Setup.exe in {app_dir()} and run it.",
        "     It puts the program back in that folder and never touches the existing data folder.",
        "  3. If your data folder is somewhere else, close the program, copy that whole 'data' folder",
        "     next to the new HadiPharmacy.exe (replace the empty one), then open the program.",
        "",
        "4. THE WHOLE FOLDER WAS DELETED (program AND data)",
        "-" * 64,
        "  1. Run HadiPharmacy-Setup.exe on the same computer.",
        f"  2. The program finds the safety copy in {mirror.parent}",
        "     and brings everything back automatically (you will see 'previous shop data was found').",
        "  3. If that did not happen: login admin / admin123 > Settings > Restore > pick the newest",
        "     file from your USB / Google Drive (Secondary backup) or from a copied backups folder.",
        "",
        "5. MOVE TO ANOTHER FOLDER ON THIS COMPUTER",
        "-" * 64,
        "  1. Click Logout (program must be closed).",
        f"  2. Move / copy the whole folder {app_dir()}",
        "     (HadiPharmacy.exe + _internal + data) to the new place.",
        "  3. Open HadiPharmacy.exe from the new place. Everything is there.",
        "",
        "6. MOVE TO ANOTHER COMPUTER (no row of data is lost)",
        "-" * 64,
        "  Way A - copy the folder (simplest, keeps everything exactly):",
        "    1. Old PC: click Logout.",
        f"    2. Copy the whole folder {app_dir()} to a USB drive.",
        "    3. New PC: paste the folder anywhere (Desktop, D:, ...) and open HadiPharmacy.exe inside it.",
        "       Login with your usual username and password.",
        "  Way B - one file:",
        "    1. Old PC: Settings > Export everything > save the file to USB.",
        "    2. New PC: run HadiPharmacy-Setup.exe, login admin / admin123,",
        "       Settings > Restore > pick that file > type the OLD owner password if asked.",
        "    3. Login again with your usual username and password.",
        "  After moving: set Printer and Secondary backup again in Settings (they depend on the PC).",
        "",
        "7. GO BACK TO AN EARLIER POINT (something was deleted by mistake)",
        "-" * 64,
        "  Settings > Restore > pick a file from the backups folder above. File names contain",
        "  date and time: pharmacy_YYYY-MM-DD_HHMMSS.db  (.db.enc = locked with owner password).",
        "  The program shows how many medicines and sales the file has before replacing anything,",
        "  and takes a backup of the current data first, so a restore can also be undone.",
        "  The .xlsx file next to each backup is the same data in Excel (open it in Excel if needed).",
        "",
        "8. WHEN BACKUPS ARE TAKEN AUTOMATICALLY",
        "-" * 64,
        "  - Once a day when the program starts        - When you Logout / close",
        "  - After every purchase                       - Before every delete and every restore",
        "  - When a month is closed",
        "  - Safety copy (mirror): at start, every 10 minutes and at close",
        "  - Kept: every backup of the last 30 days + one per month for 12 months",
        "",
        "9. FILES IN THIS FOLDER",
        "-" * 64,
        "  HadiPharmacy.exe ............ the program",
        "  _internal\\ ....................... program files (keep with the exe)",
        "  data\\ ............................ YOUR DATA (database, backups, bills)",
        f"  {GUIDE_HTML} ................. full guide to every screen and button",
        f"  {DATA_DOC} ... this file",
        "",
    ]
    return "\n".join(lines)


def write_folder_docs() -> list[Path]:
    """Write the guides next to the exe. Only for the installed program (or a test data folder)."""
    if not (is_frozen() or data_dir_override()):
        return []
    written = []
    folder = app_dir()
    for name, make in ((DATA_DOC, data_doc_text), (GUIDE_HTML, guide_html)):
        try:
            (folder / name).write_text(make(), encoding="utf-8-sig" if name.endswith(".txt") else "utf-8")
            written.append(folder / name)
        except Exception:
            continue
    try:
        (data_dir() / DATA_DOC).write_text(data_doc_text(), encoding="utf-8-sig")
    except Exception:
        pass
    return written
