# Pharmacy Advance System

Offline Windows pharmacy POS for a local medical store. Built with Python, PySide6, and SQLite.

The working database stays **next to the app** on the machine that runs it. It is not included in this repository.

## Features

- Owner and cashier login
- Medicines, companies, formulations, suppliers, customers
- Purchases with boxes and tablets-per-box pricing
- POS with pack or loose-tablet sale, hold, and checkout
- Stock, expiry, udhaar, payables, reports
- English / Urdu
- Encrypted backups (owner password)
- Saved sale bills you can view and print

## Requirements

- Windows 10 or later
- Python 3.12

## Run from source

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe run.py
```

Or double-click `Start Hadi Pharmacy.bat` after the venv is created.

First login:

- Username: `admin`
- Password: `admin123`

Change that password after the first login. Do not use the default password on a live shop PC.

## Where data is stored

- `pharmacy.db` is created in the project folder when you run from source, or next to the EXE when frozen.
- Override the folder with the `HADI_DATA_DIR` environment variable if needed.
- Backups go in a `backups` folder. Bills are saved under `bills`.
- None of those files belong in Git.

## Build a Windows package

```bat
.venv\Scripts\python.exe -m pip install pyinstaller
.venv\Scripts\python.exe build_exe.py
```

That writes:

- `dist/HadiPharmacy/` — app folder (`HadiPharmacy.exe` plus `_internal`)
- `dist/HadiPharmacy-Setup.exe` — copies the app to the Desktop and starts it

Send the Setup EXE, or the whole app folder. Do not open the inner EXE from inside a zip (Windows Temp cannot load `python312.dll`).

## Security notes

- Passwords are stored as PBKDF2-SHA256 hashes.
- Backup files can be encrypted from the owner password.
- The live SQLite file is not encrypted. Keep the shop PC locked and back up off the machine.
- This public repo contains **source only**. Shop sales, CNICs, and phone numbers stay on the local `pharmacy.db`.

## License

Use and modify for your own shop. No warranty.
