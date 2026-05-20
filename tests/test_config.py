import pytest
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from config import load_config, save_config, load_bookmarks, load_history, ConfigManager


class TestConfig:
    """Test configuration functions."""

    def test_load_config(self, temp_app_config):
        """Test loading configuration from file."""
        manager = ConfigManager(str(temp_app_config))
        config = manager.load_config()
        assert config["api_key"] == "test_key"
        assert config["export_format"] == "csv"
        assert config["simulation_mode"] is True

    def test_save_config(self, temp_app_config):
        """Test saving configuration to file."""
        manager = ConfigManager(str(temp_app_config))
        new_config = {
            "api_key": "new_key",
            "secret_key": "new_secret",
            "finmind_token": "new_token",
            "export_format": "excel",
            "simulation_mode": False
        }
        manager.save_config(new_config)
        loaded = manager.load_config()
        assert loaded["api_key"] == "new_key"
        assert loaded["export_format"] == "excel"

    def test_load_bookmarks(self, temp_app_config):
        """Test loading bookmarks."""
        manager = ConfigManager(str(temp_app_config))
        bookmarks = manager.load_bookmarks()
        assert isinstance(bookmarks, list)
        assert len(bookmarks) == 0

    def test_save_bookmarks(self, temp_app_config):
        """Test saving bookmarks."""
        manager = ConfigManager(str(temp_app_config))
        test_bookmarks = [
            {
                "name": "test_bookmark",
                "tab": "台股市場",
                "params": {"query_type": "漲幅排行"},
                "created_at": "2026-05-16"
            }
        ]
        manager.save_bookmarks(test_bookmarks)
        loaded = manager.load_bookmarks()
        assert len(loaded) == 1
        assert loaded[0]["name"] == "test_bookmark"

    def test_load_history(self, temp_app_config):
        """Test loading query history."""
        manager = ConfigManager(str(temp_app_config))
        history = manager.load_history()
        assert isinstance(history, list)

    def test_save_history(self, temp_app_config):
        """Test saving query history."""
        manager = ConfigManager(str(temp_app_config))
        test_history = [
            {
                "query_type": "snapshot",
                "params": {"code": "2330"},
                "timestamp": "2026-05-16T10:00:00",
                "result_preview": "成功"
            }
        ]
        manager.save_history(test_history)
        loaded = manager.load_history()
        assert len(loaded) == 1
        assert loaded[0]["query_type"] == "snapshot"

    def test_config_missing_file_creation(self, temp_app_config):
        """Test automatic creation of missing config file."""
        config_file = temp_app_config / "config.json"
        config_file.unlink()  # Delete config file

        manager = ConfigManager(str(temp_app_config))
        manager.ensure_default_config()

        assert config_file.exists()
        loaded = manager.load_config()
        assert "api_key" in loaded

    def test_config_with_invalid_json(self, temp_app_config):
        """Test handling of invalid JSON in config file."""
        config_file = temp_app_config / "config.json"
        config_file.write_text("{invalid json}")

        manager = ConfigManager(str(temp_app_config))
        with pytest.raises(json.JSONDecodeError):
            manager.load_config()

    def test_bookmarks_add_duplicate_name(self, temp_app_config):
        """Test handling of duplicate bookmark names."""
        manager = ConfigManager(str(temp_app_config))
        bookmark = {
            "name": "duplicate",
            "tab": "台股市場",
            "params": {},
            "created_at": "2026-05-16"
        }
        bookmarks = [bookmark, bookmark]
        manager.save_bookmarks(bookmarks)
        loaded = manager.load_bookmarks()
        # Should handle duplicates or store as-is
        assert len(loaded) >= 1

    def test_history_max_entries_limit(self, temp_app_config):
        """Test history entries don't exceed maximum."""
        manager = ConfigManager(str(temp_app_config))
        # Create more than 100 history entries
        history = [
            {
                "query_type": "snapshot",
                "params": {"code": f"000{i}"},
                "timestamp": f"2026-05-16T{i:02d}:00:00",
                "result_preview": "成功"
            }
            for i in range(150)
        ]
        manager.save_history(history)
        loaded = manager.load_history()
        # Should keep only the latest 100 (or configured limit)
        assert len(loaded) <= 100

    def test_config_update_partial(self, temp_app_config):
        """Test partial config update."""
        manager = ConfigManager(str(temp_app_config))
        original = manager.load_config()

        # Update only one field
        update = {"api_key": "updated_key"}
        original.update(update)
        manager.save_config(original)

        loaded = manager.load_config()
        assert loaded["api_key"] == "updated_key"
        # Other fields should remain
        assert "secret_key" in loaded


@pytest.mark.integration
class TestConfigPersistence:
    """Test persistence of config across sessions."""

    def test_config_persistence(self, temp_app_config):
        """Test that config changes persist."""
        # First session
        manager1 = ConfigManager(str(temp_app_config))
        config1 = manager1.load_config()
        config1["test_field"] = "test_value"
        manager1.save_config(config1)

        # Second session
        manager2 = ConfigManager(str(temp_app_config))
        config2 = manager2.load_config()
        assert config2.get("test_field") == "test_value"

    def test_bookmarks_persistence(self, temp_app_config):
        """Test that bookmarks persist across sessions."""
        bookmark = {
            "name": "persistent_bookmark",
            "tab": "工具",
            "params": {"type": "comparison"},
            "created_at": "2026-05-16"
        }

        # First session
        manager1 = ConfigManager(str(temp_app_config))
        manager1.save_bookmarks([bookmark])

        # Second session
        manager2 = ConfigManager(str(temp_app_config))
        loaded = manager2.load_bookmarks()
        assert len(loaded) == 1
        assert loaded[0]["name"] == "persistent_bookmark"
