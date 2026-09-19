from __future__ import annotations

from dataclasses import dataclass


@dataclass
class User:
    id: int
    username: str
    role: str
    must_change_password: bool = False


class Session:
    user: User | None = None
    backup_secret: str | None = None

    @classmethod
    def set(cls, user: User | None, password: str | None = None) -> None:
        cls.user = user
        if user and user.role == "owner" and password:
            cls.backup_secret = password
        if user is None:
            cls.backup_secret = None

    @classmethod
    def current(cls) -> User | None:
        return cls.user

    @classmethod
    def user_id(cls) -> int | None:
        return cls.user.id if cls.user else None

    @classmethod
    def is_owner(cls) -> bool:
        return bool(cls.user and cls.user.role == "owner")

    @classmethod
    def is_cashier(cls) -> bool:
        return bool(cls.user and cls.user.role == "cashier")

    @classmethod
    def clear(cls) -> None:
        cls.user = None
        cls.backup_secret = None
