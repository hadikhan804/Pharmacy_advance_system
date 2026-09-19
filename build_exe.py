"""Build a transfer-safe app folder, zip, and one Setup EXE."""
from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def make_icon() -> None:
    from PySide6.QtWidgets import QApplication

    from app.ui.icon import app_icon

    QApplication.instance() or QApplication([])
    out = ROOT / "assets" / "icon.ico"
    out.parent.mkdir(parents=True, exist_ok=True)
    app_icon().pixmap(256, 256).save(str(out), "ICO")
    if not out.exists():
        raise SystemExit("Could not write assets/icon.ico")


def write_readme(folder: Path) -> None:
    (folder / "HOW_TO_RUN.txt").write_text(
        "Yasir Medical Store\n"
        "===================\n\n"
        "Do not open the program from inside a zip.\n"
        "Windows Temp cannot load python312.dll.\n\n"
        "Best: send YasirMedicalStore-Setup.exe\n"
        "It copies the app to the Desktop and starts it.\n\n"
        "If you only have the zip:\n"
        "1. Right-click the zip → Extract All → Desktop\n"
        "2. Open the YasirMedicalStore folder\n"
        "3. Double-click YasirMedicalStore.exe\n"
        "4. Login: admin / admin123\n\n"
        "Keep YasirMedicalStore.exe and the _internal folder together.\n"
        "The shop database (pharmacy.db) is created in that folder.\n",
        encoding="utf-8",
    )


def zip_folder(folder: Path, dest: Path) -> None:
    if dest.exists():
        dest.unlink()
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in folder.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(folder.parent))


def make_setup_exe(zipped: Path, dest: Path) -> None:
    icon = ROOT / "assets" / "icon.ico"
    version = ROOT / "version_info.txt"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name",
        "YasirMedicalStore-Setup",
        "--add-data",
        f"{zipped};.",
        str(ROOT / "setup_launcher.py"),
    ]
    if icon.exists():
        cmd.extend(["--icon", str(icon)])
    if version.exists():
        cmd.extend(["--version-file", str(version)])
    subprocess.check_call(cmd, cwd=str(ROOT))
    built = ROOT / "dist" / "YasirMedicalStore-Setup.exe"
    if not built.exists():
        raise SystemExit("Setup EXE was not created")
    if built.resolve() != dest.resolve():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(built, dest)


def main() -> None:
    make_icon()
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            str(ROOT / "YasirMedicalStore.spec"),
        ],
        cwd=str(ROOT),
    )
    folder = ROOT / "dist" / "YasirMedicalStore"
    exe = folder / "YasirMedicalStore.exe"
    if not exe.exists():
        raise SystemExit("Build finished but dist/YasirMedicalStore/YasirMedicalStore.exe was not created")
    write_readme(folder)
    old_onefile = ROOT / "dist" / "YasirMedicalStore.exe"
    if old_onefile.exists() and old_onefile.is_file():
        old_onefile.unlink()
    zipped = ROOT / "dist" / "YasirMedicalStore.zip"
    zip_folder(folder, zipped)
    setup = ROOT / "dist" / "YasirMedicalStore-Setup.exe"
    make_setup_exe(zipped, setup)
    print(f"App folder: {folder}")
    print(f"Zip: {zipped}")
    print(f"Send this EXE: {setup}")


if __name__ == "__main__":
    main()
