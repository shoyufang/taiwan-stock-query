import pytest
import sys
import os
import json
import tempfile
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def temp_app_config():
    """Create temporary app config directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)

        # Create default config files
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps({
            "api_key": "test_key",
            "secret_key": "test_secret",
            "finmind_token": "test_token",
            "export_format": "csv",
            "simulation_mode": True
        }))

        bookmarks_file = config_dir / "bookmarks.json"
        bookmarks_file.write_text(json.dumps([]))

        history_file = config_dir / "history.json"
        history_file.write_text(json.dumps([]))

        yield config_dir


@pytest.fixture
def mock_shioaji():
    """Create mock Shioaji connection."""
    mock = MagicMock()
    mock.login = MagicMock(return_value=True)
    mock.logout = MagicMock(return_value=True)
    mock.account = MagicMock()
    mock.account.account_id = "TEST_ACCOUNT"
    return mock


@pytest.fixture
def mock_finmind_api():
    """Create mock FinMind API responses."""
    mock = MagicMock()
    mock.get = MagicMock(return_value={"data": []})
    return mock


@pytest.fixture
def sample_snapshot_data():
    """Sample stock snapshot data."""
    return {
        "code": "2330",
        "name": "台積電",
        "price": 650.5,
        "bid_volume": 1000,
        "bid_price": 650.0,
        "ask_price": 651.0,
        "ask_volume": 900,
        "volume": 50000,
        "amount": 32525000,
        "change": 5.5,
        "change_rate": 0.85
    }


@pytest.fixture
def sample_kbar_data():
    """Sample K-line data."""
    return {
        "timestamp": "2026-05-16",
        "open": 645.0,
        "high": 652.0,
        "low": 644.5,
        "close": 650.5,
        "volume": 50000
    }


@pytest.fixture
def sample_institutional_data():
    """Sample institutional investor data."""
    return {
        "date": "2026-05-16",
        "code": "2330",
        "foreign_investors": 100,
        "investment_trust": 50,
        "dealer": 25,
        "foreign_investors_buy": 5000000,
        "foreign_investors_sell": 4500000
    }


@pytest.fixture
def sample_financial_statement():
    """Sample financial statement data."""
    return {
        "quarter": "2026Q1",
        "code": "2330",
        "revenue": 1500000000,
        "gross_profit": 450000000,
        "operating_profit": 350000000,
        "net_income": 300000000,
        "eps": 1.15
    }


@pytest.fixture
def mock_config_manager(temp_app_config):
    """Create mock config manager."""
    from config import ConfigManager
    with patch.dict(os.environ, {"HOME": str(temp_app_config.parent)}):
        yield ConfigManager(str(temp_app_config))


@pytest.fixture
def mock_streamlit():
    """Create mock Streamlit context."""
    mock = MagicMock()
    mock.session_state = {}
    mock.info = MagicMock()
    mock.warning = MagicMock()
    mock.error = MagicMock()
    mock.success = MagicMock()
    return mock


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset all mocks between tests."""
    # Mock lifecycle is handled automatically by patch decorators
    yield
