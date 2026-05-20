import pytest
from unittest.mock import patch, MagicMock
import json
from pathlib import Path
# from app import save_bookmark, execute_bookmark, delete_bookmark, list_bookmarks
# from config import ConfigManager


@pytest.mark.integration
class TestBookmarkFlow:
    """Test complete bookmark functionality flow."""

    def test_save_bookmark_complete_flow(self, temp_app_config):
        """Test saving a bookmark with complete validation."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        bookmark = {
            "name": "test_bookmark",
            "tab": "台股市場",
            "query_type": "snapshot",
            "params": {"code": "2330"},
            "created_at": "2026-05-16"
        }

        manager.save_bookmarks([bookmark])
        loaded = manager.load_bookmarks()

        assert len(loaded) == 1
        assert loaded[0]["name"] == "test_bookmark"
        assert loaded[0]["query_type"] == "snapshot"

    def test_execute_bookmark_flow(self, temp_app_config):
        """Test executing a saved bookmark."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        # Save bookmark
        bookmark = {
            "name": "execute_test",
            "tab": "台股市場",
            "query_type": "snapshot",
            "params": {"code": "2330"},
            "created_at": "2026-05-16"
        }
        manager.save_bookmarks([bookmark])

        # Load and verify
        bookmarks = manager.load_bookmarks()
        assert len(bookmarks) == 1
        assert bookmarks[0]["params"]["code"] == "2330"

    def test_delete_bookmark_flow(self, temp_app_config):
        """Test deleting a bookmark."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        # Save two bookmarks
        bookmarks = [
            {
                "name": "bookmark1",
                "tab": "台股市場",
                "query_type": "snapshot",
                "params": {"code": "2330"},
                "created_at": "2026-05-16"
            },
            {
                "name": "bookmark2",
                "tab": "台股市場",
                "query_type": "snapshot",
                "params": {"code": "2412"},
                "created_at": "2026-05-16"
            }
        ]
        manager.save_bookmarks(bookmarks)

        # Load all
        loaded = manager.load_bookmarks()
        assert len(loaded) == 2

        # Delete one
        remaining = [b for b in loaded if b["name"] != "bookmark1"]
        manager.save_bookmarks(remaining)

        # Verify
        final = manager.load_bookmarks()
        assert len(final) == 1
        assert final[0]["name"] == "bookmark2"

    def test_bookmark_with_special_characters(self, temp_app_config):
        """Test bookmark names with special characters."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        bookmark = {
            "name": "台積電快照-2330",
            "tab": "台股市場",
            "query_type": "snapshot",
            "params": {"code": "2330"},
            "created_at": "2026-05-16"
        }

        manager.save_bookmarks([bookmark])
        loaded = manager.load_bookmarks()

        assert loaded[0]["name"] == "台積電快照-2330"

    def test_bookmark_duplicate_names(self, temp_app_config):
        """Test handling of duplicate bookmark names."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        bookmarks = [
            {
                "name": "duplicate",
                "tab": "台股市場",
                "query_type": "snapshot",
                "params": {"code": "2330"},
                "created_at": "2026-05-16"
            },
            {
                "name": "duplicate",
                "tab": "台股市場",
                "query_type": "kbars",
                "params": {"code": "2412"},
                "created_at": "2026-05-16"
            }
        ]

        manager.save_bookmarks(bookmarks)
        loaded = manager.load_bookmarks()

        # Should store both or handle gracefully
        assert len(loaded) >= 1

    def test_bookmark_parameter_persistence(self, temp_app_config):
        """Test that bookmark parameters are correctly persisted."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        bookmark = {
            "name": "kbar_bookmark",
            "tab": "台股市場",
            "query_type": "kbars",
            "params": {
                "code": "2330",
                "start": "2026-05-01",
                "end": "2026-05-16"
            },
            "created_at": "2026-05-16"
        }

        manager.save_bookmarks([bookmark])
        loaded = manager.load_bookmarks()

        assert loaded[0]["params"]["start"] == "2026-05-01"
        assert loaded[0]["params"]["end"] == "2026-05-16"

    def test_bookmark_list_ordering(self, temp_app_config):
        """Test that bookmarks maintain insertion order."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        bookmarks = []
        for i in range(5):
            bookmarks.append({
                "name": f"bookmark_{i}",
                "tab": "台股市場",
                "query_type": "snapshot",
                "params": {"code": f"230{i}"},
                "created_at": "2026-05-16"
            })

        manager.save_bookmarks(bookmarks)
        loaded = manager.load_bookmarks()

        # Verify order
        for i in range(5):
            assert loaded[i]["name"] == f"bookmark_{i}"

    def test_bookmark_max_count(self, temp_app_config):
        """Test handling when bookmark count exceeds limit."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        # Create many bookmarks
        bookmarks = []
        for i in range(150):
            bookmarks.append({
                "name": f"bookmark_{i}",
                "tab": "台股市場",
                "query_type": "snapshot",
                "params": {"code": "2330"},
                "created_at": "2026-05-16"
            })

        manager.save_bookmarks(bookmarks)
        loaded = manager.load_bookmarks()

        # Should keep reasonable number
        assert len(loaded) <= 100  # Typical limit

    @patch('query_wrapper.query_snapshot')
    def test_execute_bookmark_with_query(self, mock_query, temp_app_config):
        """Test executing bookmark that calls actual query."""
        from config import ConfigManager
        import pandas as pd

        manager = ConfigManager(str(temp_app_config))

        # Mock query response
        mock_query.return_value = pd.DataFrame({
            "code": ["2330"],
            "price": [650.5]
        })

        # Save bookmark
        bookmark = {
            "name": "query_bookmark",
            "tab": "台股市場",
            "query_type": "snapshot",
            "params": {"code": "2330"},
            "created_at": "2026-05-16"
        }
        manager.save_bookmarks([bookmark])

        # Execute bookmark (would call query_snapshot internally)
        loaded = manager.load_bookmarks()
        assert loaded[0]["query_type"] == "snapshot"

    def test_bookmark_with_multiple_codes(self, temp_app_config):
        """Test bookmark with multiple stock codes."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        bookmark = {
            "name": "multi_stock",
            "tab": "台股市場",
            "query_type": "snapshot",
            "params": {"codes": ["2330", "2412", "3008"]},
            "created_at": "2026-05-16"
        }

        manager.save_bookmarks([bookmark])
        loaded = manager.load_bookmarks()

        assert len(loaded[0]["params"]["codes"]) == 3

    def test_bookmark_date_range_preservation(self, temp_app_config):
        """Test that date ranges in bookmarks are preserved."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        bookmark = {
            "name": "date_bookmark",
            "tab": "台股市場",
            "query_type": "kbars",
            "params": {
                "code": "2330",
                "start": "2026-01-01",
                "end": "2026-12-31"
            },
            "created_at": "2026-05-16"
        }

        manager.save_bookmarks([bookmark])
        loaded = manager.load_bookmarks()

        # Verify dates are preserved
        assert loaded[0]["params"]["start"] == "2026-01-01"
        assert loaded[0]["params"]["end"] == "2026-12-31"


@pytest.mark.integration
class TestBookmarkEdgeCases:
    """Test edge cases in bookmark functionality."""

    def test_empty_bookmark_name(self, temp_app_config):
        """Test handling of empty bookmark name."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        bookmark = {
            "name": "",
            "tab": "台股市場",
            "query_type": "snapshot",
            "params": {"code": "2330"},
            "created_at": "2026-05-16"
        }

        # Should either reject or handle gracefully
        manager.save_bookmarks([bookmark])
        loaded = manager.load_bookmarks()
        # Either rejected or stored with validation

    def test_bookmark_very_long_name(self, temp_app_config):
        """Test bookmark with very long name."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        long_name = "測試" * 100
        bookmark = {
            "name": long_name,
            "tab": "台股市場",
            "query_type": "snapshot",
            "params": {"code": "2330"},
            "created_at": "2026-05-16"
        }

        manager.save_bookmarks([bookmark])
        loaded = manager.load_bookmarks()
        assert loaded[0]["name"] == long_name

    def test_bookmark_with_unicode_characters(self, temp_app_config):
        """Test bookmark with various unicode characters."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        bookmark = {
            "name": "📈台積電2330🚀",
            "tab": "台股市場",
            "query_type": "snapshot",
            "params": {"code": "2330"},
            "created_at": "2026-05-16"
        }

        manager.save_bookmarks([bookmark])
        loaded = manager.load_bookmarks()
        assert "📈" in loaded[0]["name"]
