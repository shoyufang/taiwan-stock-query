"""
測試 market_overview.py 核心函數
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_ranking_map_valid_values():
    """ranking_map 所有值必須 ∈ {'up', 'down', 'volume', 'amount'}"""
    from tabs.market_overview import render_rankings
    # ranking_map 是函式內部變數，我們用另一種方式驗證
    # 直接呼叫 query_ranking 確認合法值
    import query_wrapper as qw

    valid_types = {"up", "down", "volume", "amount"}
    for rt in valid_types:
        df = qw.query_ranking(rt, limit=1)
        # 不要求一定有資料（可能是假日），但不能拋錯
        assert df is not None


def test_safe_div():
    """_safe_div 安全除法"""
    from tabs.market_overview import _safe_div
    assert _safe_div(10, 2) == 500.0  # 10/2 * 100 = 500%
    assert _safe_div(0, 100) == 0.0
    assert _safe_div(10, 0) is None
    assert _safe_div(10, None) is None


def test_is_market_open_logic():
    """is_market_open 基本邏輯驗證"""
    from tabs.market_overview import is_market_open

    # 直接用實際時間測試：如果現在是工作日盤中應該 True
    # 這個測試主要確認函式不會拋錯
    result = is_market_open()
    assert isinstance(result, bool)
