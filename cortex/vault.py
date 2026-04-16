"""
Cortex Vault — secure local key storage.

Keys are stored at ~/.cortex/vault.json with restricted permissions.
Cortex reads them at runtime. They never enter git, logs, or conversation.

Usage:
    from cortex.vault import Vault

    vault = Vault()
    vault.set("ANTHROPIC_API_KEY", "sk-ant-...")
    vault.set("OPENAI_API_KEY", "sk-...")

    key = vault.get("ANTHROPIC_API_KEY")
"""

import json
import os
import stat
from pathlib import Path
from typing import Optional


VAULT_DIR = Path.home() / ".cortex"
VAULT_PATH = VAULT_DIR / "vault.json"


class Vault:
    def __init__(self, path: Optional[str] = None):
        self._path = Path(path) if path else VAULT_PATH
        self._ensure_dir()

    def _ensure_dir(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # lock down the directory — owner only
        os.chmod(self._path.parent, stat.S_IRWXU)

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self, data: dict):
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        # restrict file to owner read/write only
        os.chmod(self._path, stat.S_IRUSR | stat.S_IWUSR)

    def set(self, key: str, value: str):
        data = self._load()
        data[key] = value
        self._save(data)

    def get(self, key: str) -> Optional[str]:
        data = self._load()
        return data.get(key)

    def delete(self, key: str):
        data = self._load()
        data.pop(key, None)
        self._save(data)

    def list_keys(self) -> list:
        return list(self._load().keys())

    def load_into_env(self):
        """Load all vault keys into environment variables."""
        for key, value in self._load().items():
            os.environ[key] = value
