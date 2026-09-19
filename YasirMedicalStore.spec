# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH)
ICON = ROOT / "assets" / "icon.ico"
VERSION = ROOT / "version_info.txt"

datas = [
    (str(ROOT / "app" / "i18n" / "en.json"), "app/i18n"),
    (str(ROOT / "app" / "i18n" / "ur.json"), "app/i18n"),
    (str(ROOT / "app" / "ui" / "style.qss"), "app/ui"),
]

hiddenimports = collect_submodules("app") + [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtPrintSupport",
    "cryptography.fernet",
    "openpyxl",
]

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="YasirMedicalStore",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON) if ICON.exists() else None,
    version=str(VERSION) if VERSION.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="YasirMedicalStore",
)
