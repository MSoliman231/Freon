import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path

AUTH_FILE = Path(__file__).resolve().parent / "auth.json"

PASSWORD_LENGTH = 6       # length of generated passwords
MIN_PASSWORD_LENGTH = 4   # shortest password you can choose yourself
ITERATIONS = 200_000


def _hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)


def _read():
    """Stored data, or None if the app has not been set up yet."""
    try:
        with open(AUTH_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        bytes.fromhex(data["salt"])
        bytes.fromhex(data["hash"])
        return data
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _write(data):
    tmp = AUTH_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, AUTH_FILE)


def is_configured():
    """False on a fresh start: the setup screen is shown first."""
    return _read() is not None


def setup(email, password):
    """First start: stores the password (salted hash only) and the email."""
    salt = os.urandom(16)
    _write({
        "salt": salt.hex(),
        "hash": _hash(password, salt).hex(),
        "email": email,
    })


def set_password(password, email=None):
    """Changes the password. The stored email is kept unless a new one is given."""
    data = _read() or {}
    salt = os.urandom(16)
    data["salt"] = salt.hex()
    data["hash"] = _hash(password, salt).hex()
    if email:
        data["email"] = email
    _write(data)


def get_email():
    data = _read()
    return data.get("email", "") if data else ""


def verify_password(password):
    data = _read()
    if data is None:
        return False
    salt = bytes.fromhex(data["salt"])
    expected = bytes.fromhex(data["hash"])
    return hmac.compare_digest(_hash(password, salt), expected)


def generate_password():
    """Random password using only the digits 1 to 9."""
    return "".join(secrets.choice("123456789") for _ in range(PASSWORD_LENGTH))