"""
Cortex Auth — simple user accounts with per-user data isolation.

Each user gets their own directory under ~/.cortex/users/{username}/
with their own plan, rules, uploads, and output.
"""

import json
import hashlib
import os
import secrets
from pathlib import Path
from typing import Optional

USERS_DIR = Path.home() / ".cortex" / "users"
AUTH_FILE = Path.home() / ".cortex" / "auth.json"


def _hash_password(password: str, salt: str = None) -> tuple:
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return hashed, salt


def _load_auth() -> dict:
    if AUTH_FILE.exists():
        try:
            with open(AUTH_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_auth(data: dict):
    AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.chmod(AUTH_FILE, 0o600)


def signup(username: str, password: str) -> bool:
    auth = _load_auth()
    if username in auth:
        return False
    hashed, salt = _hash_password(password)
    auth[username] = {"password_hash": hashed, "salt": salt}
    _save_auth(auth)

    # Create user directory structure
    user_dir = USERS_DIR / username
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "uploads").mkdir(exist_ok=True)
    (user_dir / "output").mkdir(exist_ok=True)

    # Default plan
    with open(user_dir / "plan_status.json", "w") as f:
        json.dump({"total_tasks": 0, "completed": 0, "failed": 0, "current_task": None, "tasks": []}, f, indent=2)

    # Default rules
    with open(user_dir / "cortex.yaml", "w") as f:
        f.write("rules: []\nrisk_threshold: 100\nmax_blocked_attempts: 3\nmax_rounds: 3\n")

    # Empty runtime log
    with open(user_dir / "runtime_log.json", "w") as f:
        json.dump([], f)

    # User vault
    vault_file = user_dir / "vault.json"
    with open(vault_file, "w") as f:
        json.dump({}, f)
    os.chmod(vault_file, 0o600)

    return True


def get_user_vault_path(username: str) -> Path:
    return USERS_DIR / username / "vault.json"


def login(username: str, password: str) -> bool:
    auth = _load_auth()
    if username not in auth:
        return False
    user = auth[username]
    salt = user.get("salt", "")
    if salt:
        hashed, _ = _hash_password(password, salt)
        return user["password_hash"] == hashed
    # Backwards compat with old unsalted hashes
    return user["password_hash"] == hashlib.sha256(password.encode()).hexdigest()


def get_user_dir(username: str) -> Path:
    user_dir = USERS_DIR / username
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def list_users() -> list:
    auth = _load_auth()
    return list(auth.keys())
