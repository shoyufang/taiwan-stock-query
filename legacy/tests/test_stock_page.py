"""
測試 stock_page.py 核心函數
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_is_tw_stock_numeric():
    """台股：純數字 → True"""
    from tabs.stock_page import is_tw_stock
    assert is_tw_stock("2330") is True
    assert is_tw_stock("2317") is True
    assert is_tw_stock("2454") is True


def test_is_tw_stock_etf():
    """台股 ETF：5-6 碼數字 → True（Bug 修復）"""
    from tabs.stock_page import is_tw_stock
    assert is_tw_stock("00878") is True
    assert is_tw_stock("00940") is True
    assert is_tw_stock("0050") is True


def test_is_tw_stock_us():
    """美股代號 → False"""
    from tabs.stock_page import is_tw_stock
    assert is_tw_stock("NVDA") is False
    assert is_tw_stock("AAPL") is False
    assert is_tw_stock("TSM") is False


def test_is_tw_stock_numeric_hk():
    """純 5-6 碼數字目前被判斷為台股（ETF 也一樣）。港股如 00700 也是純數字，
    但港股代號通常用 "HK.00700" 格式，所以 00700 仍會 match。
    這是一個已知限制，實際使用時 resolve_code 已會正確處理。"""
    from tabs.stock_page import is_tw_stock
    # 純 5-6 碼數字 → 台股（ETF）
    assert is_tw_stock("00700") is True  # 港股 00700 也會 match，但這是已知限制


def test_is_tw_stock_with_dot():
    """含 . 的代號 → False"""
    from tabs.stock_page import is_tw_stock
    assert is_tw_stock("2330.TW") is False
    assert is_tw_stock("TSM.US") is False
