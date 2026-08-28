"""Encrypted local secret storage helpers."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from . import storage


class SecretStoreError(RuntimeError):
    error_code = "AUTOMATION_SECRET_STORE_ERROR"


def _key_file() -> Path:
    return storage.root_dir() / "secret.key"


def _normalize_env_key(raw: str) -> bytes:
    encoded = raw.strip().encode("utf-8")
    try:
        Fernet(encoded)
        return encoded
    except (ValueError, TypeError):
        return base64.urlsafe_b64encode(hashlib.sha256(encoded).digest())


def get_or_create_key() -> bytes:
    env_key = os.environ.get("VOICEBOX_AUTOMATION_SECRET_KEY")
    if env_key:
        return _normalize_env_key(env_key)

    path = _key_file()
    if path.exists():
        key = path.read_bytes().strip()
        try:
            Fernet(key)
        except (ValueError, TypeError) as exc:
            raise SecretStoreError("Khóa mã hóa Automation Hub không hợp lệ.") from exc
        return key

    path.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    try:
        with path.open("xb") as handle:
            handle.write(key)
        try:
            path.chmod(0o600)
        except OSError:
            pass
    except FileExistsError:
        return get_or_create_key()
    return key


def encrypt_secret(value: dict[str, Any]) -> tuple[str, str]:
    if not value:
        raise SecretStoreError("Secret không được để trống.")
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ciphertext = Fernet(get_or_create_key()).encrypt(payload).decode("ascii")
    fingerprint = hashlib.sha256(payload).hexdigest()[:12]
    return ciphertext, fingerprint


def decrypt_secret(ciphertext: str | None) -> dict[str, Any]:
    if not ciphertext:
        raise SecretStoreError("Connection chưa có secret.")
    try:
        payload = Fernet(get_or_create_key()).decrypt(ciphertext.encode("ascii"))
        value = json.loads(payload.decode("utf-8"))
    except (InvalidToken, ValueError, json.JSONDecodeError, TypeError) as exc:
        raise SecretStoreError("Không thể giải mã secret; hãy cấu hình lại connection.") from exc
    if not isinstance(value, dict):
        raise SecretStoreError("Secret connection không đúng định dạng.")
    return value


def secret_store_status() -> dict[str, Any]:
    try:
        key = get_or_create_key()
        return {
            "ready": True,
            "source": "environment" if os.environ.get("VOICEBOX_AUTOMATION_SECRET_KEY") else "local_file",
            "key_fingerprint": hashlib.sha256(key).hexdigest()[:10],
        }
    except SecretStoreError as exc:
        return {"ready": False, "source": "unavailable", "error": str(exc)}
