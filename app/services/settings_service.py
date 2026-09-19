from __future__ import annotations

from app.db.database import get_db
from app.services import audit_service


def get(key: str, default: str = "") -> str:
    row = get_db().execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row is None or row["value"] is None:
        return default
    return str(row["value"])


def set_value(key: str, value: str) -> None:
    get_db().execute(
        "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    get_db().commit()
    audit_service.log("settings.update", "settings", None, f"{key}={value}")


def get_all() -> dict[str, str]:
    rows = get_db().execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] or "" for r in rows}


def pharmacy_info() -> dict[str, str]:
    data = get_all()
    return {
        "name": data.get("pharmacy_name", "Yasir Medical Store"),
        "address": data.get("pharmacy_address", ""),
        "phone": data.get("pharmacy_phone", ""),
        "ntn": data.get("ntn", ""),
        "logo_path": data.get("logo_path", ""),
        "footer_en": data.get("receipt_footer_en", ""),
        "footer_ur": data.get("receipt_footer_ur", ""),
        "printer_name": data.get("printer_name", ""),
        "default_gst": data.get("default_gst", "0"),
        "language": data.get("language", "en"),
        "backup_folder": data.get("backup_folder", ""),
        "secondary_backup_folder": data.get("secondary_backup_folder", ""),
        "expiry_alert_days": data.get("expiry_alert_days", "30,60,90"),
        "udhaar_overdue_days": data.get("udhaar_overdue_days", "30"),
        "last_verified_backup_at": data.get("last_verified_backup_at", ""),
    }


def expiry_windows() -> list[int]:
    raw = get("expiry_alert_days", "30,60,90")
    days = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            days.append(int(part))
    return days or [30, 60, 90]


def default_gst() -> float:
    try:
        return float(get("default_gst", "0") or 0)
    except ValueError:
        return 0.0


def overdue_days() -> int:
    try:
        return int(get("udhaar_overdue_days", "30") or 30)
    except ValueError:
        return 30
