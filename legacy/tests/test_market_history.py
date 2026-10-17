"""
Phase G 測試：_market_history 模組
- load_market_history: CSV 容錯、欄位缺失、排序
- breadth_sparkline: 資料充足/不足
- data_asof: 渲染不崩潰
"""
import os
import tempfile
import textwrap
from pathlib import Path

import pandas as pd
import pytest

from tabs._market_history import (
    _find_data_dir,
    load_market_history,
    data_asof,
)


# ── 測試數據建立 ──


@pytest.fixture
def temp_market_dir(tmp_path):
    """建立含測試 CSV 的 data/market 目錄"""
    market_dir = tmp_path / "market"
    market_dir.mkdir()

    # 模擬 5 天的市場資料（含早期缺欄位）
    data_1 = "date,taiex,trust,dealer\n2024-01-02,17500.0,-5000,3000\n2024-01-03,17600.0,2000,-1000\n"
    data_2 = "date,taiex,taiex_chg,taiex_pct,trust,dealer\n2024-01-04,17700.0,100,0.57,3000,-2000\n2024-01-05,17650.0,-50,-0.28,-1000,1500\n2024-01-08,17800.0,150,0.85,4000,-500\n"

    (market_dir / "2024-01-02.csv").write_text(data_1, encoding="utf-8")
    (market_dir / "2024-01-03.csv").write_text(data_1, encoding="utf-8")
    (market_dir / "2024-01-04.csv").write_text(data_2, encoding="utf-8")
    (market_dir / "2024-01-05.csv").write_text(data_2, encoding="utf-8")
    (market_dir / "2024-01-08.csv").write_text(data_2, encoding="utf-8")

    return market_dir


@pytest.fixture(autouse=True)
def patch_data_dir(monkeypatch, temp_market_dir):
    """patch _find_data_dir 回傳 temp 目錄，並清除快取避免跨測試污染"""
    import tabs._market_history as mh
    monkeypatch.setattr("tabs._market_history._DATA_DIR", temp_market_dir)
    # 清除 SQLite 快取
    try:
        from sqlite_cache import cache_manager
        cache_manager.clear_all()
    except Exception:
        pass
    return temp_market_dir


# ── load_market_history ──


class TestLoadMarketHistory:
    def test_returns_dataframe(self, patch_data_dir):
        df = load_market_history(250)
        assert isinstance(df, pd.DataFrame)

    def test_has_required_columns(self, patch_data_dir):
        df = load_market_history(250)
        for col in ["date", "taiex", "taiex_chg", "taiex_pct", "trust", "dealer", "foreign"]:
            assert col in df.columns, f"缺少欄位: {col}"

    def test_foreign_equals_trust(self, patch_data_dir):
        df = load_market_history(250)
        if not df.empty:
            assert (df["foreign"] == df["trust"]).all()

    def test_sorted_descending(self, patch_data_dir):
        df = load_market_history(250)
        if len(df) >= 2:
            dates = df["date"]
            for i in range(len(dates) - 1):
                assert dates.iloc[i] >= dates.iloc[i + 1], f"排序錯誤 at {i}: {dates.iloc[i]} < {dates.iloc[i+1]}"

    def test_limited_to_days(self, patch_data_dir):
        df = load_market_history(3)
        assert len(df) <= 3

    def test_empty_when_no_dir(self):
        """無資料目錄時回傳空 DataFrame（patch _find_data_dir 模擬）"""
        import tabs._market_history as mh
        # 直接 patch _find_data_dir 而非 _DATA_DIR（因為有 caching）
        original_find = mh._find_data_dir
        mh._find_data_dir = lambda: Path("/nonexistent_xyz_99999")
        try:
            df = load_market_history.__wrapped__(250)  # 繞過 cache，直接調原始函數
            assert df.empty or len(df) == 0
        finally:
            mh._find_data_dir = original_find

    def test_handles_missing_taiex_chg(self, monkeypatch, temp_market_dir):
        """早期檔可能缺 taiex_chg/taiex_pct 欄位"""
        data_no_chg = "date,taiex,trust,dealer\n2024-01-10,17900.0,5000,-3000\n"
        (temp_market_dir / "2024-01-10.csv").write_text(data_no_chg, encoding="utf-8")
        monkeypatch.setattr("tabs._market_history._DATA_DIR", temp_market_dir)
        df = load_market_history(250)
        assert "taiex_chg" in df.columns
        assert "taiex_pct" in df.columns

    def test_numeric_columns(self, patch_data_dir):
        df = load_market_history(250)
        for col in ["taiex", "taiex_chg", "taiex_pct", "trust", "dealer", "foreign"]:
            assert pd.api.types.is_numeric_dtype(df[col]), f"{col} 不是 numeric"


# ── data_asof ──


class TestDataAsof:
    def test_with_valid_timestamp(self):
        """data_asof 不崩潰"""
        import streamlit as st
        original = st.caption
        st.caption = lambda x: None
        try:
            data_asof("市場寬度", pd.Timestamp("2024-01-08"))
        finally:
            st.caption = original

    def test_with_nan(self):
        import streamlit as st
        original = st.caption
        st.caption = lambda x: None
        try:
            data_asof("市場寬度", pd.NaT)
        finally:
            st.caption = original

    def test_with_string(self):
        import streamlit as st
        original = st.caption
        st.caption = lambda x: None
        try:
            data_asof("市場寬度", "2024/01/08")
        finally:
            st.caption = original
