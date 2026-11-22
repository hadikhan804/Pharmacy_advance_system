import os
import sys
from pathlib import Path

APP_NAME = "HadiPharmacy"
APP_TITLE = "Hadi Pharmacy"
LEGACY_APP_NAME = "YasirMedicalStore"
DATA_DIR_ENV = "HADI_DATA_DIR"
LEGACY_DATA_DIR_ENV = "YASIR_DATA_DIR"
APP_SUBTITLE = "Pharmacy POS System"
STORE_PHONE = "03716931861"
EXPIRY_ALERT_MONTHS = 6
EXPIRY_ALERT_DAYS = EXPIRY_ALERT_MONTHS * 30
BILL_RETURN_POLICY_EN = (
    "After 15 days no return. Syrups, strips and fridge items are non refundable."
)
BILL_RETURN_POLICY_UR = (
    "15 دن بعد واپسی نہیں۔ شربت، سٹرپس اور فریج آئٹم واپس نہیں ہوں گے۔"
)
DB_FILENAME = "pharmacy.db"


def data_dir_override() -> str | None:
    return os.environ.get(DATA_DIR_ENV) or os.environ.get(LEGACY_DATA_DIR_ENV)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))


def resource_dir() -> Path:
    """Bundled files (QSS, translations) live here. Inside the EXE when frozen."""
    if is_frozen():
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def app_dir() -> Path:
    """Folder that contains the .exe (or the project folder when running from source)."""
    override = data_dir_override()
    if override:
        return Path(override)
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = resource_dir()
ASSETS_DIR = resource_dir() / "assets"
I18N_DIR = resource_dir() / "app" / "i18n"


def _writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".yms_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


DATA_SUBDIR = "data"
_data_dir_cache: Path | None = None


def _appdata_root() -> Path:
    return Path(os.environ.get("APPDATA") or str(Path.home())) / APP_NAME


def data_dir() -> Path:
    """<app folder>/data holds pharmacy.db, backups and bills. Reinstalling keeps it."""
    global _data_dir_cache
    if _data_dir_cache is not None and _data_dir_cache.exists():
        return _data_dir_cache
    path = app_dir() / DATA_SUBDIR
    if not _writable_dir(path):
        path = _appdata_root() / DATA_SUBDIR
        path.mkdir(parents=True, exist_ok=True)
    _data_dir_cache = path
    return path


def db_path() -> Path:
    return data_dir() / DB_FILENAME


def backup_default_dir() -> Path:
    path = data_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def bills_dir() -> Path:
    path = data_dir() / "bills"
    path.mkdir(parents=True, exist_ok=True)
    return path


def mirror_dir() -> Path:
    """Safety copy outside the app folder, used if the app folder is deleted and reinstalled."""
    override = data_dir_override()
    if override:
        return Path(override) / "mirror"
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / APP_NAME / "mirror"


def mirror_db_path() -> Path:
    return mirror_dir() / DB_FILENAME


def _is_sqlite(path: Path) -> bool:
    try:
        with open(path, "rb") as fh:
            return fh.read(16).startswith(b"SQLite format 3")
    except OSError:
        return False


def prepare_data_dir() -> dict:
    """Move an older layout into data/ or bring back the safety copy. Runs before the DB opens."""
    import shutil

    data = data_dir()
    target = data / DB_FILENAME
    result: dict = {"data_dir": str(data), "action": ""}
    if target.exists():
        return result
    if data_dir_override():
        legacy_roots = [app_dir()]
    else:
        appdata = Path(os.environ.get("APPDATA") or str(Path.home()))
        legacy_roots = [app_dir(), _appdata_root(), appdata / LEGACY_APP_NAME]
    for root in legacy_roots:
        legacy = root / DB_FILENAME
        if root == data or not legacy.exists() or not _is_sqlite(legacy):
            continue
        for suffix in ("", "-wal", "-shm"):
            src = Path(str(legacy) + suffix)
            if src.exists():
                if root == app_dir():
                    shutil.move(str(src), str(data / (DB_FILENAME + suffix)))
                else:
                    shutil.copy2(str(src), str(data / (DB_FILENAME + suffix)))
        for sub in ("backups", "bills"):
            src_dir = root / sub
            if src_dir.is_dir() and root == app_dir():
                dest_dir = data / sub
                dest_dir.mkdir(parents=True, exist_ok=True)
                for f in src_dir.iterdir():
                    if not (dest_dir / f.name).exists():
                        shutil.move(str(f), str(dest_dir / f.name))
                try:
                    src_dir.rmdir()
                except OSError:
                    pass
        result.update(action="migrated", source=str(legacy))
        return result
    for candidate in (mirror_db_path(), Path(os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())) / LEGACY_APP_NAME / "mirror" / DB_FILENAME):
        if candidate.exists() and _is_sqlite(candidate):
            shutil.copy2(str(candidate), str(target))
            result.update(action="restored_mirror", source=str(candidate))
            break
    return result
