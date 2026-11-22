from __future__ import annotations

import sqlite3

from app.auth.passwords import hash_password
from app.config import BILL_RETURN_POLICY_EN, BILL_RETURN_POLICY_UR, EXPIRY_ALERT_DAYS, STORE_PHONE, backup_default_dir
from app.utils.dates import now_iso


DEFAULT_SETTINGS = {
    "pharmacy_name": "Hadi Pharmacy",
    "pharmacy_address": "",
    "pharmacy_phone": STORE_PHONE,
    "ntn": "",
    "logo_path": "",
    "receipt_footer_en": BILL_RETURN_POLICY_EN,
    "receipt_footer_ur": BILL_RETURN_POLICY_UR,
    "printer_name": "",
    "default_gst": "0",
    "language": "en",
    "backup_folder": str(backup_default_dir()),
    "expiry_alert_days": f"30,90,{EXPIRY_ALERT_DAYS}",
    "udhaar_overdue_days": "30",
    "last_auto_backup_date": "",
    "secondary_backup_folder": "",
    "last_verified_backup_at": "",
    "setup_complete": "1",
    "backup_salt": "",
    "pending_secondary": "",
    "last_closed_month": "",
    "receipt_mode": "direct",
    "thermal_width": "48",
    "thermal_feed": "4",
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
        WHERE key = 'pharmacy_name' AND value IN ('My Pharmacy', 'Pharmacy POS', 'Yasir Medical Store', '')
        """,
        ("Hadi Pharmacy",),
    )
    conn.execute(
        """
        UPDATE settings SET value = ?
        WHERE key = 'pharmacy_phone' AND IFNULL(value, '') = ''
        """,
        (STORE_PHONE,),
    )
    conn.execute(
        """
        UPDATE settings SET value = ?
        WHERE key = 'expiry_alert_days' AND value IN ('30,60,90', '30, 60, 90', '')
        """,
        (f"30,90,{EXPIRY_ALERT_DAYS}",),
    )
    conn.execute(
        """
        UPDATE settings SET value = ?
        WHERE key = 'receipt_footer_en' AND value IN (
            'Thank you. Medicines cannot be returned without invoice.',
            'Thank you. Get well soon.',
            ''
        )
        """,
        (BILL_RETURN_POLICY_EN,),
    )
    conn.execute(
        """
        UPDATE settings SET value = ?
        WHERE key = 'receipt_footer_ur' AND value IN (
            'شکریہ۔ بل کے بغیر دوائی واپس نہیں ہوگی۔',
            ''
        )
        """,
        (BILL_RETURN_POLICY_UR,),
    )
    conn.commit()
