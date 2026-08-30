"""Fernet encryption for persisted MFA secrets."""

from __future__ import annotations

import base64
import hashlib
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


def _session_secret() -> str:
    secret = (os.getenv("SECRET_KEY") or "").strip()
    if not secret:
        try:
            from app.config.settings import Config

            secret = str(Config.SECRET_KEY or "").strip()
        except Exception:
            secret = ""
    return secret


def _mfa_key() -> str:
    return (os.getenv("MFA_ENCRYPTION_KEY") or "").strip()


def _fernet(secret: str) -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def _encryption_secret() -> str:
    secret = _mfa_key() or _session_secret()
    if not secret:
        raise ValueError("MFA_ENCRYPTION_KEY or SECRET_KEY must be set to encrypt MFA secrets")
    return secret


def encrypt_secret_blob(plaintext: str) -> str:
    value = "" if plaintext is None else str(plaintext)
    return _fernet(_encryption_secret()).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret_blob(stored: Any) -> str:
    if stored is None:
        return ""
    value = stored.decode("utf-8") if isinstance(stored, (bytes, bytearray)) else str(stored)
    value = value.strip()
    if not value:
        return ""
    secrets = []
    for candidate in (_mfa_key(), _session_secret()):
        if candidate and candidate not in secrets:
            secrets.append(candidate)
    if not secrets:
        raise ValueError("MFA_ENCRYPTION_KEY or SECRET_KEY must be set to decrypt MFA secrets")
    for secret in secrets:
        try:
            return _fernet(secret).decrypt(value.encode("ascii")).decode("utf-8")
        except InvalidToken:
            continue
    raise ValueError("Cannot decrypt MFA secret with the configured encryption keys")
