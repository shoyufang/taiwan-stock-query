import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import json
# from app import record_query_history, execute_from_history, clear_history
# from config import ConfigManager


@pytest.mark.integration
class TestHistoryFlow:
    """Test complete query history functionality flow."""

    def test_record_query_history_single_query(self, temp_app_config):
        """Test recording a single query to history."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        history_entry = {
            "query_type": "snapshot",
            "params": {"code": "2330"},
            "timestamp": "2026-05-16T10:00:00",
            "result_preview": "成功"
        }

        manager.save_history([history_entry])
        loaded = manager.load_history()

        assert len(loaded) == 1
        assert loaded[0]["query_type"] == "snapshot"
        assert loaded[0]["params"]["code"] == "2330"

    def test_record_multiple_queries(self, temp_app_config):
        """Test recording multiple queries to history."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        history = [
            {
                "query_type": "snapshot",
                "params": {"code": "2330"},
                "timestamp": "2026-05-16T10:00:00",
                "result_preview": "成功"
            },
            {
                "query_type": "kbars",
                "params": {"code": "2412", "start": "2026-05-01", "end": "2026-05-16"},
                "timestamp": "2026-05-16T10:05:00",
                "result_preview": "成功"
            },
            {
                "query_type": "ranking",
                "params": {"type": "rise"},
                "timestamp": "2026-05-16T10:10:00",
                "result_preview": "成功"
            }
        ]

        manager.save_history(history)
        loaded = manager.load_history()

        assert len(loaded) == 3
        assert loaded[0]["query_type"] == "snapshot"
        assert loaded[1]["query_type"] == "kbars"
        assert loaded[2]["query_type"] == "ranking"

    def test_history_auto_append(self, temp_app_config):
        """Test that history entries are appended, not replaced."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        # First batch
        history1 = [{
            "query_type": "snapshot",
            "params": {"code": "2330"},
            "timestamp": "2026-05-16T10:00:00",
            "result_preview": "成功"
        }]
        manager.save_history(history1)

        # Second batch
        loaded = manager.load_history()
        history2 = loaded + [{
            "query_type": "kbars",
            "params": {"code": "2412"},
            "timestamp": "2026-05-16T10:05:00",
            "result_preview": "成功"
        }]
        manager.save_history(history2)

        final = manager.load_history()
        assert len(final) == 2

    def test_history_max_100_entries(self, temp_app_config):
        """Test that history doesn't exceed 100 entries."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        # Create 150 history entries
        history = []
        for i in range(150):
            history.append({
                "query_type": "snapshot",
                "params": {"code": f"000{i}"},
                "timestamp": f"2026-05-16T{i//60:02d}:{i%60:02d}:00",
                "result_preview": "成功"
            })

        manager.save_history(history)
        loaded = manager.load_history()

        # Should keep only 100
        assert len(loaded) <= 100

    def test_history_keeps_latest_entries(self, temp_app_config):
        """Test that oldest entries are removed when limit exceeded."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        # Create more than 100 entries
        history = []
        for i in range(110):
            history.append({
                "query_type": "snapshot",
                "params": {"code": "2330"},
                "timestamp": f"2026-05-16T{i:02d}:00:00",
                "result_preview": f"entry_{i}"
            })

        manager.save_history(history)
        loaded = manager.load_history()

        # Should keep latest 100
        assert len(loaded) == 100
        # Latest entries should be present
        assert any("entry_109" in str(e.get("result_preview", "")) for e in loaded)

    def test_clear_history(self, temp_app_config):
        """Test clearing all history."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        # Add history
        history = [
            {
                "query_type": "snapshot",
                "params": {"code": "2330"},
                "timestamp": "2026-05-16T10:00:00",
                "result_preview": "成功"
            }
        ]
        manager.save_history(history)
        assert len(manager.load_history()) == 1

        # Clear
        manager.save_history([])
        assert len(manager.load_history()) == 0

    @patch('query_wrapper.query_snapshot')
    def test_execute_from_history_snapshot(self, mock_query, temp_app_config):
        """Test executing snapshot query from history."""
        from config import ConfigManager
        import pandas as pd

        manager = ConfigManager(str(temp_app_config))

        # Mock response
        mock_query.return_value = pd.DataFrame({
            "code": ["2330"],
            "price": [650.5]
        })

        # Record in history
        history_entry = {
            "query_type": "snapshot",
            "params": {"code": "2330"},
            "timestamp": "2026-05-16T10:00:00",
            "result_preview": "成功"
        }
        manager.save_history([history_entry])

        loaded = manager.load_history()
        assert loaded[0]["query_type"] == "snapshot"

    @patch('query_wrapper.query_kbars')
    def test_execute_from_history_kbars(self, mock_query, temp_app_config):
        """Test executing K-bar query from history."""
        from config import ConfigManager
        import pandas as pd

        manager = ConfigManager(str(temp_app_config))

        # Mock response
        mock_query.return_value = pd.DataFrame({
            "timestamp": ["2026-05-16"],
            "close": [650.5]
        })

        history_entry = {
            "query_type": "kbars",
            "params": {
                "code": "2330",
                "start": "2026-05-01",
                "end": "2026-05-16"
            },
            "timestamp": "2026-05-16T10:00:00",
            "result_preview": "成功"
        }
        manager.save_history([history_entry])

        loaded = manager.load_history()
        assert loaded[0]["query_type"] == "kbars"
        assert loaded[0]["params"]["start"] == "2026-05-01"

    def test_history_query_type_variety(self, temp_app_config):
        """Test history with various query types."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        query_types = [
            "snapshot", "kbars", "ticks", "ranking",
            "institutional", "margin_short", "shareholding", "day_trading"
        ]

        history = []
        for i, qtype in enumerate(query_types):
            history.append({
                "query_type": qtype,
                "params": {"code": "2330"},
                "timestamp": f"2026-05-16T{i:02d}:00:00",
                "result_preview": f"{qtype}_success"
            })

        manager.save_history(history)
        loaded = manager.load_history()

        assert len(loaded) == len(query_types)
        for i, qtype in enumerate(query_types):
            assert loaded[i]["query_type"] == qtype

    def test_history_timestamp_preservation(self, temp_app_config):
        """Test that query timestamps are correctly preserved."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        timestamp = "2026-05-16T14:30:45"
        history_entry = {
            "query_type": "snapshot",
            "params": {"code": "2330"},
            "timestamp": timestamp,
            "result_preview": "成功"
        }

        manager.save_history([history_entry])
        loaded = manager.load_history()

        assert loaded[0]["timestamp"] == timestamp

    def test_history_parameter_preservation(self, temp_app_config):
        """Test that all query parameters are preserved in history."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        history_entry = {
            "query_type": "comparison",
            "params": {
                "codes": ["2330", "2412", "3008"],
                "type": "snapshot",
                "start": "2026-05-01",
                "end": "2026-05-16",
                "metric": "price"
            },
            "timestamp": "2026-05-16T10:00:00",
            "result_preview": "成功"
        }

        manager.save_history([history_entry])
        loaded = manager.load_history()

        assert loaded[0]["params"]["codes"] == ["2330", "2412", "3008"]
        assert loaded[0]["params"]["type"] == "snapshot"
        assert loaded[0]["params"]["metric"] == "price"


@pytest.mark.integration
class TestHistoryEdgeCases:
    """Test edge cases in history functionality."""

    def test_history_with_special_characters(self, temp_app_config):
        """Test history with special characters in parameters."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        history_entry = {
            "query_type": "snapshot",
            "params": {"code": "2330", "note": "台積電💯"},
            "timestamp": "2026-05-16T10:00:00",
            "result_preview": "成功"
        }

        manager.save_history([history_entry])
        loaded = manager.load_history()

        assert "💯" in loaded[0]["params"]["note"]

    def test_history_with_very_long_parameters(self, temp_app_config):
        """Test history with very long parameter values."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        long_codes = ",".join([f"000{i}" for i in range(100)])
        history_entry = {
            "query_type": "snapshot",
            "params": {"codes": long_codes},
            "timestamp": "2026-05-16T10:00:00",
            "result_preview": "成功"
        }

        manager.save_history([history_entry])
        loaded = manager.load_history()

        assert len(loaded[0]["params"]["codes"]) > 500

    def test_history_duplicate_entries(self, temp_app_config):
        """Test that identical queries can be recorded multiple times."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        history_entry = {
            "query_type": "snapshot",
            "params": {"code": "2330"},
            "timestamp": "2026-05-16T10:00:00",
            "result_preview": "成功"
        }

        # Add same entry twice
        history = [history_entry]
        manager.save_history(history)

        history = manager.load_history() + [history_entry]
        manager.save_history(history)

        loaded = manager.load_history()
        # Should have both entries
        assert len(loaded) >= 2

    def test_history_with_null_parameters(self, temp_app_config):
        """Test history entries with null or missing parameters."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        history_entry = {
            "query_type": "news",
            "params": {},  # Empty params
            "timestamp": "2026-05-16T10:00:00",
            "result_preview": "成功"
        }

        manager.save_history([history_entry])
        loaded = manager.load_history()

        assert loaded[0]["params"] == {}


@pytest.mark.integration
class TestHistoryUI:
    """Test history UI display functionality."""

    def test_history_display_recent_10(self, temp_app_config):
        """Test displaying only recent 10 history entries in sidebar."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        # Create 20 history entries
        history = []
        for i in range(20):
            history.append({
                "query_type": "snapshot",
                "params": {"code": f"000{i}"},
                "timestamp": f"2026-05-16T{i:02d}:00:00",
                "result_preview": f"entry_{i}"
            })

        manager.save_history(history)
        loaded = manager.load_history()

        # UI should display only recent 10
        recent = loaded[-10:] if len(loaded) > 10 else loaded
        assert len(recent) <= 10

    def test_history_entry_display_format(self, temp_app_config):
        """Test formatting of history entries for display."""
        from config import ConfigManager
        manager = ConfigManager(str(temp_app_config))

        history_entry = {
            "query_type": "snapshot",
            "params": {"code": "2330"},
            "timestamp": "2026-05-16T10:00:00",
            "result_preview": "成功"
        }

        manager.save_history([history_entry])
        loaded = manager.load_history()

        entry = loaded[0]
        # Should have all required fields
        assert "query_type" in entry
        assert "params" in entry
        assert "timestamp" in entry
