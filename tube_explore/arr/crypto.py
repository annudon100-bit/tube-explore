import base64
import os
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_KEY_FILE = "arr_api_key.key"
_SALT_FILE = "arr_api_key.salt"


def _get_key_path(config_dir: str) -> str:
    return os.path.join(config_dir, _KEY_FILE)


def _get_salt_path(config_dir: str) -> str:
    return os.path.join(config_dir, _SALT_FILE)


def _derive_key(config_dir: str, raw_key: bytes) -> bytes:
    salt_path = _get_salt_path(config_dir)
    if os.path.exists(salt_path):
        with open(salt_path, "rb") as f:
            salt = f.read()
    else:
        salt = os.urandom(16)
        os.makedirs(os.path.dirname(salt_path), exist_ok=True)
        with open(salt_path, "wb") as f:
            f.write(salt)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600000)
    return base64.urlsafe_b64encode(kdf.derive(raw_key))


def _get_fernet(config_dir: str) -> Fernet:
    key_path = _get_key_path(config_dir)
    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            key = f.read()
    else:
        raw_key = os.urandom(32)
        key = _derive_key(config_dir, raw_key)
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        with open(key_path, "wb") as f:
            f.write(key)
    return Fernet(key)


def encrypt_api_key(api_key: str, config_dir: str) -> str:
    f = _get_fernet(config_dir)
    return f.encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted: str, config_dir: str) -> str:
    f = _get_fernet(config_dir)
    return f.decrypt(encrypted.encode()).decode()
