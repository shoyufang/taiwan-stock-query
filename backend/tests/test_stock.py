"""個股頁：以 2330 的 FinMind 真實資料（2026-10-16 為止）驗證。"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from app.services import stock as st
from app.services import stock_loader as loader
from app.store import Store

FIX = Path(__file__).parent / "fixtures"
load = lambda n: json.loads((FIX / f"finmind_{n}.json").read_text(encoding="utf-8"))["data"]  # noqa: E731


@pytest.fixture(scope="module")
def data():
    bars = st.bars_from_finmind(load("TaiwanStockPrice"))
    inst = st.institutional_daily(load("TaiwanStockInstitutionalInvestorsBuySell"))
    margin = st.margin_daily(load("TaiwanStockMarginPurchaseShortSale"))
    revenue = st.revenue_monthly(load("TaiwanStockMonthRevenue"))
    pe = st.pe_position(load("TaiwanStockPER"))
    profile = st.pick_profile(load("info"), "2330")
    return dict(bars=bars, inst=inst, margin=margin, revenue=revenue, pe=pe, profile=profile)


class TestPieces:
    def test_profile_prefers_specific_industry(self, data):
        assert data["profile"] == {"code": "2330", "name": "台積電", "industry": "半導體業", "market": "上市"}

    def test_last_bar_matches_official(self, data):
        b = data["bars"][-1]
        # 證交所 10/16：收 2,420，成交 43,046,982 股
        assert (b["date"], b["close"], b["volume"]) == ("2026-10-16", 2420.0, 43047)

    def test_institutional_matches_twse_t86(self, data):
        by = {d["date"]: d for d in data["inst"]}
        # 與證交所 T86 外資買賣超（不含外資自營商）比對：10/16 −22,046 張、10/15 −34,111 張
        assert by["2026-10-16"]["foreign"] == -22046
        assert by["2026-10-15"]["foreign"] == -34111

    def test_streak(self):
        assert st.streak([5, -1, -2, -3]) == (-1, 3)
        assert st.streak([1, 2, 0]) == (0, 0)

    def test_margin(self, data):
        m = data["margin"][-1]
        assert m == {"date": "2026-10-16", "margin_balance": 34110, "margin_change": -113, "short_balance": 9}

    def test_revenue_uses_revenue_month(self, data):
        r = data["revenue"][-1]
        assert (r["year"], r["month"]) == (2026, 9)
        assert r["yoy"] == round((511857399000 / 330980920000 - 1) * 100, 1)
        assert r["mom"] == round((511857399000 / 514805337000 - 1) * 100, 1)

    def test_pe_position(self, data):
        pe = data["pe"]
        assert pe["current"] == 28.05 and pe["end"] == "2026-10-16"
        assert pe["min"] <= pe["median"] <= pe["max"]
        assert 0 <= pe["pct_rank"] <= 100

    def test_adjust_bars(self):
        bars = [{"date": d, "open": p, "high": p, "low": p, "close": p, "volume": 1, "value": 1}
                for d, p in [("2025-09-15", 1255.0), ("2025-09-16", 1250.0)]]
        divs = [{"date": "2025-09-16", "before_price": 1255.0, "after_price": 1249.99}]
        adj = st.adjust_bars(bars, divs)
        assert adj[0]["close"] == 1249.99  # 除息前一天被調整為參考價
        assert adj[1]["close"] == 1250.0   # 除息當天之後不動

    def test_search(self):
        info = load("info") + [
            {"industry_category": "所有證券", "stock_id": "711145", "stock_name": "環球晶國票9B購02", "type": "tpex", "date": "2026-10-17"},
        ]
        assert st.search(info, "2330")[0]["code"] == "2330"
        assert st.search(info, "台積")[0]["name"] == "台積電"
        assert [r["code"] for r in st.search(info, "環球晶")] == ["6488"]  # 權證不列入

    def test_otc_not_compared_with_taiex(self, data):
        otc = {**data["profile"], "market": "上櫃"}
        r = st.build_report(otc, data["bars"][-1], data["bars"][-2]["close"], data["inst"], data["margin"],
                            data["revenue"], data["pe"], 0.30)
        assert "加權指數" not in r["lead"]


class TestReport:
    def test_page(self, data):
        page = st.build_stock_page(data["profile"], data["bars"], data["inst"], data["margin"], data["revenue"],
                                   data["pe"], 0.30, "2026-10-17T00:00:00+08:00")
        assert page["asof"] == "2026-10-16"
        assert page["quote"]["change"] == -20.0 and page["quote"]["change_pct"] == round(-20 / 2440 * 100, 2)
        r = page["report"]
        assert r["headline"] == "台積電收 2,420 元，外資單日賣超 2.2 萬張"
        assert r["lead"].startswith("台積電下跌 0.82%，同日加權指數上漲 0.30%，弱於大盤。")
        # 10/05 外資買超，10/06 起至 10/16 連續 8 個交易日賣超
        assert "外資已連續 8 個交易日賣超" in r["lead"]
        assert "9 月營收 5,118.6 億元，年增 54.6%" in r["lead"]
        assert len(page["institutional"]) == 15 and len(page["margin"]) == 10 and len(page["revenue"]) == 13


class TestLoader:
    @pytest.mark.asyncio
    async def test_cache_and_incremental_bars(self, tmp_path):
        store = Store(str(tmp_path / "s.db"))
        calls = []

        async def fake_fetch(client, dataset, data_id=None, start=None, end=None):
            calls.append((dataset, start))
            name = "info" if dataset == "TaiwanStockInfo" else dataset
            return load(name)

        now = datetime(2026, 10, 17, 9, 0, tzinfo=ZoneInfo("Asia/Taipei"))
        with patch.object(loader.finmind, "fetch", fake_fetch):
            p1 = await loader.load_page(store, None, None, "2330", now)
            n1 = len(calls)
            p2 = await loader.load_page(store, None, None, "2330", now)
        assert p1["asof"] == p2["asof"] == "2026-10-16"
        assert ("TaiwanStockPrice", "1994-01-01") in calls  # 第一次抓全部歷史
        assert len(calls) == n1  # 第二次全部命中快取

    @pytest.mark.asyncio
    async def test_unknown_code(self, tmp_path):
        store = Store(str(tmp_path / "s.db"))

        async def fake_fetch(client, dataset, *a, **k):
            return load("info")

        with patch.object(loader.finmind, "fetch", fake_fetch), pytest.raises(loader.StockNotFound):
            await loader.load_page(store, None, None, "9999")
