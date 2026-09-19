from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken


def fernet_from_password(password: str, salt: bytes) -> Fernet:
    raw = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000, dklen=32)
    return Fernet(base64.urlsafe_b64encode(raw))


def new_salt() -> bytes:
    return os.urandom(16)


def encrypt_bytes(data: bytes, password: str, salt: bytes) -> bytes:
    return fernet_from_password(password, salt).encrypt(data)


def decrypt_bytes(data: bytes, password: str, salt: bytes) -> bytes:
    try:
        return fernet_from_password(password, salt).decrypt(data)
    except InvalidToken as exc:
        raise ValueError("Wrong password or damaged backup") from exc
