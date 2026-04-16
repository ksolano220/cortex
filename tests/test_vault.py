import pytest
import json
import os
import stat
from pathlib import Path
from unittest.mock import patch

from cortex.vault import Vault


def test_vault_init_default_path():
    vault = Vault()
    assert vault._path == Path.home() / ".cortex" / "vault.json"


def test_vault_init_custom_path(tmp_path):
    custom_path = tmp_path / "custom_vault.json"
    vault = Vault(str(custom_path))
    assert vault._path == custom_path


def test_vault_ensure_dir(tmp_path):
    vault_path = tmp_path / "test_vault" / "vault.json"
    vault = Vault(str(vault_path))
    
    # Directory should be created
    assert vault_path.parent.exists()
    
    # Directory should have restricted permissions (owner only)
    dir_stat = os.stat(vault_path.parent)
    assert dir_stat.st_mode & 0o777 == 0o700


def test_vault_set_and_get(tmp_path):
    vault_path = tmp_path / "vault.json"
    vault = Vault(str(vault_path))
    
    vault.set("TEST_KEY", "test_value")
    
    # Should be able to get the value
    assert vault.get("TEST_KEY") == "test_value"
    
    # Should return None for non-existent keys
    assert vault.get("NON_EXISTENT") is None


def test_vault_file_permissions(tmp_path):
    vault_path = tmp_path / "vault.json"
    vault = Vault(str(vault_path))
    
    vault.set("TEST_KEY", "test_value")
    
    # File should have restricted permissions (owner read/write only)
    file_stat = os.stat(vault_path)
    assert file_stat.st_mode & 0o777 == 0o600


def test_vault_delete(tmp_path):
    vault_path = tmp_path / "vault.json"
    vault = Vault(str(vault_path))
    
    vault.set("KEY1", "value1")
    vault.set("KEY2", "value2")
    
    # Verify both keys exist
    assert vault.get("KEY1") == "value1"
    assert vault.get("KEY2") == "value2"
    
    # Delete one key
    vault.delete("KEY1")
    
    # Verify KEY1 is gone but KEY2 remains
    assert vault.get("KEY1") is None
    assert vault.get("KEY2") == "value2"
    
    # Delete non-existent key should not crash
    vault.delete("NON_EXISTENT")


def test_vault_list_keys(tmp_path):
    vault_path = tmp_path / "vault.json"
    vault = Vault(str(vault_path))
    
    # Empty vault should return empty list
    assert vault.list_keys() == []
    
    # Add some keys
    vault.set("KEY1", "value1")
    vault.set("KEY2", "value2")
    vault.set("KEY3", "value3")
    
    # Should return all keys
    keys = vault.list_keys()
    assert set(keys) == {"KEY1", "KEY2", "KEY3"}


def test_vault_load_into_env(tmp_path):
    vault_path = tmp_path / "vault.json"
    vault = Vault(str(vault_path))
    
    # Set some keys in vault
    vault.set("CORTEX_TEST_KEY1", "value1")
    vault.set("CORTEX_TEST_KEY2", "value2")
    
    # Load into environment
    vault.load_into_env()
    
    # Verify environment variables are set
    assert os.environ.get("CORTEX_TEST_KEY1") == "value1"
    assert os.environ.get("CORTEX_TEST_KEY2") == "value2"
    
    # Clean up
    os.environ.pop("CORTEX_TEST_KEY1", None)
    os.environ.pop("CORTEX_TEST_KEY2", None)


def test_vault_corrupted_file(tmp_path):
    vault_path = tmp_path / "vault.json"
    vault = Vault(str(vault_path))
    
    # Create a corrupted JSON file
    with open(vault_path, "w", encoding="utf-8") as f:
        f.write("invalid json content")
    
    # Should handle corrupted file gracefully
    assert vault.get("ANY_KEY") is None
    assert vault.list_keys() == []
    
    # Should be able to set new values after corruption
    vault.set("NEW_KEY", "new_value")
    assert vault.get("NEW_KEY") == "new_value"


def test_vault_empty_file(tmp_path):
    vault_path = tmp_path / "vault.json"
    vault = Vault(str(vault_path))
    
    # Create empty file
    vault_path.touch()
    
    # Should handle empty file gracefully
    assert vault.get("ANY_KEY") is None
    assert vault.list_keys() == []


def test_vault_nonexistent_file(tmp_path):
    vault_path = tmp_path / "nonexistent" / "vault.json"
    vault = Vault(str(vault_path))
    
    # Should handle nonexistent file gracefully
    assert vault.get("ANY_KEY") is None
    assert vault.list_keys() == []
    
    # Should create file and directory when setting value
    vault.set("NEW_KEY", "new_value")
    assert vault.get("NEW_KEY") == "new_value"
    assert vault_path.exists()


def test_vault_multiple_operations(tmp_path):
    vault_path = tmp_path / "vault.json"
    vault = Vault(str(vault_path))
    
    # Test multiple operations in sequence
    vault.set("API_KEY", "secret123")
    vault.set("DB_PASSWORD", "pass456")
    vault.set("JWT_SECRET", "jwt789")
    
    # Verify all values
    assert vault.get("API_KEY") == "secret123"
    assert vault.get("DB_PASSWORD") == "pass456"
    assert vault.get("JWT_SECRET") == "jwt789"
    
    # Update a value
    vault.set("API_KEY", "newsecret123")
    assert vault.get("API_KEY") == "newsecret123"
    
    # Delete a value
    vault.delete("DB_PASSWORD")
    assert vault.get("DB_PASSWORD") is None
    assert vault.get("API_KEY") == "newsecret123"
    assert vault.get("JWT_SECRET") == "jwt789"
    
    # List remaining keys
    keys = vault.list_keys()
    assert set(keys) == {"API_KEY", "JWT_SECRET"}


def test_vault_persistence(tmp_path):
    vault_path = tmp_path / "vault.json"
    
    # Create vault and set value
    vault1 = Vault(str(vault_path))
    vault1.set("PERSISTENT_KEY", "persistent_value")
    
    # Create new vault instance with same path
    vault2 = Vault(str(vault_path))
    
    # Should be able to read value set by first instance
    assert vault2.get("PERSISTENT_KEY") == "persistent_value"