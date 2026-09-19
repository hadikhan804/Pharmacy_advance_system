from __future__ import annotations

import sqlite3

from app.auth.passwords import hash_password
from app.config import backup_default_dir
from app.utils.dates import now_iso


DEFAULT_SETTINGS = {
    "pharmacy_name": "Yasir Medical Store",
    "pharmacy_address": "",
    "pharmacy_phone": "",
    "ntn": "",
    "logo_path": "",
    "receipt_footer_en": "Thank you. Medicines cannot be returned without invoice.",
    "receipt_footer_ur": "شکریہ۔ بل کے بغیر دوائی واپس نہیں ہوگی۔",
    "printer_name": "",
    "default_gst": "0",
    "language": "en",
    "backup_folder": str(backup_default_dir()),
    "expiry_alert_days": "30,60,90",
    "udhaar_overdue_days": "30",
    "last_auto_backup_date": "",
    "secondary_backup_folder": "",
    "last_verified_backup_at": "",
    "setup_complete": "1",
    "backup_salt": "",
    "pending_secondary": "",
}


def seed_if_needed(conn: sqlite3.Connection) -> None:
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
            (key, value),
        )
    row = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
    if row["c"] == 0:
        conn.execute(
            """
            INSERT INTO users(username, password_hash, role, active, must_change_password, created_at)
            VALUES (?, ?, 'owner', 1, 0, ?)
            """,
            ("admin", hash_password("admin123"), now_iso()),
        )
    conn.execute(
        """
        UPDATE settings SET value = ?
        WHERE key = 'pharmacy_name' AND value IN ('My Pharmacy', 'Pharmacy POS', '')
        """,
        ("Yasir Medical Store",),
    )
    conn.commit()
