from __future__ import annotations

from app.auth.passwords import hash_password, verify_password
from app.auth.session import User
from app.constants import ROLE_CASHIER, ROLE_OWNER, ROLES
from app.db.database import get_db, row_to_dict, rows_to_dicts, transaction
from app.services import audit_service
from app.utils.dates import now_iso


def authenticate(username: str, password: str) -> User | None:
    username = (username or "").strip()
    password = password or ""
    row = get_db().execute(
        "SELECT * FROM users WHERE lower(username) = lower(?) AND active = 1",
        (username,),
    ).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        return None
    audit_service.log("user.login", "users", row["id"], username)
    get_db().commit()
    return User(
        id=row["id"],
        username=row["username"],
        role=row["role"],
        must_change_password=bool(row["must_change_password"]),
    )


def list_users() -> list[dict]:
    return rows_to_dicts(
        get_db().execute(
            "SELECT id, username, role, active, must_change_password, created_at FROM users ORDER BY username"
        ).fetchall()
    )


def get_user(user_id: int) -> dict | None:
    return row_to_dict(get_db().execute("SELECT id, username, role, active FROM users WHERE id = ?", (user_id,)).fetchone())


def create_user(username: str, password: str, role: str) -> int:
    if role not in ROLES:
        raise ValueError("Invalid role")
    if not username.strip():
        raise ValueError("Username is required")
    if len(password or "") < 6:
        raise ValueError("Password must be at least 6 characters")
    if get_db().execute("SELECT 1 FROM users WHERE lower(username) = lower(?)", (username.strip(),)).fetchone():
        raise ValueError("That username is already taken")
    with transaction() as conn:
        cur = conn.execute(
            """
            INSERT INTO users(username, password_hash, role, active, must_change_password, created_at)
            VALUES (?, ?, ?, 1, 1, ?)
            """,
            (username.strip(), hash_password(password), role, now_iso()),
        )
        uid = cur.lastrowid
        audit_service.log("user.create", "users", uid, username)
        return uid


def _keeps_an_owner(user_id: int, role: str, active: bool) -> None:
    others = get_db().execute(
        "SELECT COUNT(*) FROM users WHERE role = ? AND active = 1 AND id != ?", (ROLE_OWNER, user_id)
    ).fetchone()[0]
    if not others and (role != ROLE_OWNER or not active):
        raise ValueError("At least one active owner account must remain, otherwise nobody can open Settings.")


def set_active(user_id: int, active: bool) -> None:
    cur = get_user(user_id)
    if not cur:
        raise ValueError("User not found")
    _keeps_an_owner(user_id, cur["role"], active)
    with transaction():
        get_db().execute("UPDATE users SET active = ? WHERE id = ?", (1 if active else 0, user_id))
        audit_service.log("user.active", "users", user_id, str(active))


def change_password(user_id: int, new_password: str, clear_must_change: bool = True) -> None:
    with transaction():
        get_db().execute(
            "UPDATE users SET password_hash = ?, must_change_password = ? WHERE id = ?",
            (hash_password(new_password), 0 if clear_must_change else 1, user_id),
        )
        audit_service.log("user.password", "users", user_id, "")


def update_user(user_id: int, username: str, role: str) -> None:
    if role not in (ROLE_OWNER, ROLE_CASHIER):
        raise ValueError("Invalid role")
    if not username.strip():
        raise ValueError("Username is required")
    cur = get_user(user_id)
    if not cur:
        raise ValueError("User not found")
    _keeps_an_owner(user_id, role, bool(cur["active"]))
    clash = get_db().execute(
        "SELECT id FROM users WHERE lower(username) = lower(?) AND id != ?", (username.strip(), user_id)
    ).fetchone()
    if clash:
        raise ValueError("That username is already taken")
    with transaction():
        get_db().execute(
            "UPDATE users SET username = ?, role = ? WHERE id = ?",
            (username.strip(), role, user_id),
        )
        audit_service.log("user.update", "users", user_id, f"{username}/{role}")
