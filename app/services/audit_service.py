from __future__ import annotations

from app.auth.session import Session
from app.db.database import get_db, rows_to_dicts
from app.utils.dates import now_iso


def log(action: str, entity: str | None = None, entity_id: int | None = None, details: str = "") -> None:
    get_db().execute(
        """
        INSERT INTO audit_log(user_id, action, entity, entity_id, details, ts)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (Session.user_id(), action, entity, entity_id, details, now_iso()),
    )


def list_logs(limit: int = 500, search: str = "") -> list[dict]:
    sql = """
        SELECT a.*, u.username
        FROM audit_log a
        LEFT JOIN users u ON u.id = a.user_id
        WHERE (? = '' OR a.action LIKE ? OR a.entity LIKE ? OR a.details LIKE ? OR u.username LIKE ?)
        ORDER BY a.id DESC
        LIMIT ?
    """
    q = f"%{search}%"
    rows = get_db().execute(sql, (search, q, q, q, q, limit)).fetchall()
    return rows_to_dicts(rows)
