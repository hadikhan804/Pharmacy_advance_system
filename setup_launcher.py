"""Copy the app folder to the Desktop, then start it. Do not run from a zip."""
from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path


def _message(text: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, text, "Yasir Medical Store", 0x40)
    except Exception:
        print(text)


def _bundle() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def main() -> int:
    dest = Path.home() / "Desktop" / "YasirMedicalStore"
    zpath = _bundle() / "YasirMedicalStore.zip"
    if not zpath.exists():
        zpath = Path(sys.executable).resolve().parent / "YasirMedicalStore.zip"
    if not zpath.exists():
        _message("YasirMedicalStore.zip is missing. Send YasirMedicalStore-Setup.exe, not a zip.")
        return 1
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zpath) as zf:
        zf.extractall(dest.parent)
    exe = dest / "YasirMedicalStore.exe"
    runtime = dest / "_internal" / "python312.dll"
    if not exe.exists() or not runtime.exists():
        _message(
            "Install failed. Right-click YasirMedicalStore.zip → Extract All → Desktop, "
            "then open the folder and run YasirMedicalStore.exe."
        )
        return 1
    os.startfile(str(exe))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
