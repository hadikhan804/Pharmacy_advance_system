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
        "Hadi Pharmacy\n"
        "=============\n\n"
        "Do not open the program from inside a zip.\n"
        "Windows Temp cannot load python312.dll.\n\n"
        "Best: send HadiPharmacy-Setup.exe\n"
        "It installs the app in the SAME folder where the Setup file is, and starts it.\n\n"
        "If you only have the zip:\n"
        "1. Right-click the zip → Extract All → any normal folder\n"
        "2. Open the HadiPharmacy folder\n"
        "3. Double-click HadiPharmacy.exe\n"
        "4. Login: admin / admin123\n\n"
        "Keep HadiPharmacy.exe and the _internal folder together.\n\n"
        "Shop data lives in the 'data' folder next to the exe:\n"
        "  data\\pharmacy.db   (all medicines, stock, sales)\n"
        "  data\\backups       (automatic daily + event backups)\n"
        "  data\\bills         (saved bills)\n\n"
        "Running Setup again never touches the data folder.\n"
        "A safety copy is also kept in %LOCALAPPDATA%\\HadiPharmacy\\mirror.\n"
        "If the app folder is deleted and installed again, the app brings that data back automatically.\n\n"
        "NEVER delete the data folder. Close the app with Logout before running Setup.\n\n"
        "Full instructions: open 'User Guide.html' in this folder,\n"
        "or press F1 / click Help inside the program.\n",
        encoding="utf-8",
    )
    write_guide_html(folder)


def write_guide_html(folder: Path) -> None:
    from PySide6.QtGui import QTextDocument
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    doc = QTextDocument()
    doc.setDefaultStyleSheet(
        "body{font-family:'Segoe UI',Arial;font-size:11pt} h1{color:#4b3fd1} h2{color:#4b3fd1;margin-top:18px}"
        " table{border-collapse:collapse} td,th{border:1px solid #bbb;padding:4px 8px} pre{background:#f3f3f3}"
    )
    doc.setMarkdown((ROOT / "app" / "docs" / "user_guide.md").read_text(encoding="utf-8"))
    html = doc.toHtml().replace("<head>", "<head><title>Hadi Pharmacy - User Guide</title>", 1)
    (folder / "User Guide.html").write_text(html, encoding="utf-8")


def zip_folder(folder: Path, dest: Path) -> None:
    if dest.exists():
        dest.unlink()
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in folder.rglob("*"):
            rel = path.relative_to(folder)
            if rel.parts and rel.parts[0].lower() in {"data", "backups", "bills"}:
                continue
            if path.name.lower().startswith("pharmacy.db") or path.name == "app.lock":
                continue
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
        "HadiPharmacy-Setup",
        "--add-data",
        f"{zipped};.",
        str(ROOT / "setup_launcher.py"),
    ]
    if icon.exists():
        cmd.extend(["--icon", str(icon)])
    if version.exists():
        cmd.extend(["--version-file", str(version)])
    subprocess.check_call(cmd, cwd=str(ROOT))
    built = ROOT / "dist" / "HadiPharmacy-Setup.exe"
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
            str(ROOT / "HadiPharmacy.spec"),
        ],
        cwd=str(ROOT),
    )
    folder = ROOT / "dist" / "HadiPharmacy"
    exe = folder / "HadiPharmacy.exe"
    if not exe.exists():
        raise SystemExit("Build finished but dist/HadiPharmacy/HadiPharmacy.exe was not created")
    write_readme(folder)
    old_onefile = ROOT / "dist" / "HadiPharmacy.exe"
    if old_onefile.exists() and old_onefile.is_file():
        old_onefile.unlink()
    zipped = ROOT / "dist" / "HadiPharmacy.zip"
    zip_folder(folder, zipped)
    setup = ROOT / "dist" / "HadiPharmacy-Setup.exe"
    make_setup_exe(zipped, setup)
    print(f"App folder: {folder}")
    print(f"Zip: {zipped}")
    print(f"Send this EXE: {setup}")


if __name__ == "__main__":
    main()
