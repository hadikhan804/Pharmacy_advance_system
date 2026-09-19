import os
import sys
from pathlib import Path

APP_NAME = "YasirMedicalStore"
APP_TITLE = "Yasir Medical Store"
APP_SUBTITLE = "Pharmacy POS System"
DB_FILENAME = "pharmacy.db"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))


def resource_dir() -> Path:
    """Bundled files (QSS, translations) live here. Inside the EXE when frozen."""
    if is_frozen():
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def app_dir() -> Path:
    """Folder that contains the .exe (or the project folder when running from source)."""
    override = os.environ.get("YASIR_DATA_DIR")
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


def data_dir() -> Path:
    path = app_dir()
    if not _writable_dir(path):
        path = Path(os.environ.get("APPDATA") or str(Path.home())) / APP_NAME
        path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / DB_FILENAME


def backup_default_dir() -> Path:
    path = data_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path
