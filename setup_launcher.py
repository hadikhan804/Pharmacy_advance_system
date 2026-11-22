"""Install the app into the same folder as this Setup file, then start it. Do not run from a zip."""
from __future__ import annotations

import os
import shutil
import sys
import zipfile
from pathlib import Path

TITLE = "Hadi Pharmacy"
MB_YESNO_QUESTION = 0x4 | 0x20
IDYES = 6


def _message(text: str, flags: int = 0x40) -> int:
    if os.environ.get("YMS_SETUP_SILENT"):
        print(text)
        return 7 if flags & 0x4 else 1
    try:
        import ctypes

        return ctypes.windll.user32.MessageBoxW(None, text, TITLE, flags)
    except Exception:
        print(text)
        return IDYES


def _bundle() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def _setup_folder() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _writable(folder: Path) -> bool:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / ".yms_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _is_removable(folder: Path) -> bool:
    try:
        import ctypes

        return ctypes.windll.kernel32.GetDriveTypeW(str(folder.anchor)) == 2
    except Exception:
        return False


def _has_db(folder: Path) -> bool:
    return (folder / "data" / "pharmacy.db").exists() or (folder / "pharmacy.db").exists()


def _relative(name: str) -> str:
    parts = name.replace("\\", "/").split("/")
    return "/".join(parts[1:]) if len(parts) > 1 and parts[0] in {"HadiPharmacy", "YasirMedicalStore"} else "/".join(parts)


def _is_user_data(rel: str) -> bool:
    parts = rel.lower().split("/")
    if parts[0] in {"data", "backups", "bills", "mirror"}:
        return True
    return parts[-1].startswith("pharmacy.db") or parts[-1] == "app.lock"


def _offer_old_data(dest: Path) -> None:
    """A copy on the Desktop from an earlier Setup holds the shop data: bring it into this folder."""
    old = None
    for name in ("HadiPharmacy", "YasirMedicalStore"):
        candidate = Path.home() / "Desktop" / name
        if candidate.resolve() != dest.resolve() and (candidate / "data" / "pharmacy.db").exists():
            old = candidate
            break
    if old is None:
        return
    answer = _message(
        "Shop data from an earlier install was found in:\n"
        f"{old / 'data'}\n\n"
        f"Copy it into this folder so you keep every record?\n{dest / 'data'}\n\n"
        "Yes = copy my data here (recommended)\nNo = start with an empty shop here",
        MB_YESNO_QUESTION,
    )
    if answer != IDYES:
        return
    if (old / "data" / "app.lock").exists():
        _message("The old copy of the program is still open.\nClose it (Logout), then press OK to continue copying.")
    shutil.copytree(old / "data", dest / "data", dirs_exist_ok=True, ignore=shutil.ignore_patterns("app.lock"))


def main() -> int:
    zpath = _bundle() / "HadiPharmacy.zip"
    if not zpath.exists():
        zpath = _setup_folder() / "HadiPharmacy.zip"
    if not zpath.exists():
        _message("HadiPharmacy.zip is missing. Send HadiPharmacy-Setup.exe, not a zip.")
        return 1

    dest = _setup_folder()
    if not _writable(dest):
        fallback = Path.home() / "Desktop" / "HadiPharmacy"
        _message(f"This folder cannot be written to:\n{dest}\n\nThe program will be installed in:\n{fallback}")
        dest = fallback
        dest.mkdir(parents=True, exist_ok=True)

    had_data = _has_db(dest)
    if not had_data:
        try:
            _offer_old_data(dest)
        except OSError as exc:
            _message(f"Could not copy the old data:\n{exc}\n\nNothing was deleted. You can copy the data folder by hand later.")
    try:
        with zipfile.ZipFile(zpath) as zf:
            for member in zf.infolist():
                rel = _relative(member.filename)
                if not rel or _is_user_data(rel):
                    continue
                target = dest / rel
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
    except PermissionError:
        _message(
            "Hadi Pharmacy is still open.\n\n"
            "Close the app (and any open bill window), then run Setup again.\n"
            "Your shop data is safe."
        )
        return 1
    exe = dest / "HadiPharmacy.exe"
    runtime = dest / "_internal" / "python312.dll"
    if not exe.exists() or not runtime.exists():
        _message("Install failed. Copy HadiPharmacy-Setup.exe to a normal folder (for example Desktop) and run it again.")
        return 1
    usb = (
        "\n\nNOTE: this is a USB drive. Your shop data will be saved on this USB.\n"
        "Keep it plugged in while using the program, and do not unplug it while the program is open."
        if _is_removable(dest)
        else ""
    )
    _message(
        ("Update installed. Your existing shop data was kept.\n\n" if _has_db(dest) and had_data else "Installed.\n\n")
        + f"Program:  {exe}\n"
        f"Your data:  {dest / 'data'}\n\n"
        "In this same folder you will find:\n"
        "  User Guide.html  - how to use every screen\n"
        "  DATA AND RECOVERY - READ ME.txt  - exact data paths and how to never lose data\n\n"
        "Next time, open HadiPharmacy.exe from this folder." + usb
    )
    os.startfile(str(exe))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
