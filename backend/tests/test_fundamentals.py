import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from app.services import fundamentals as fu
from app.services import stock as st
from app.services import stock_loader as loader
from app.store import Store

FIX = Path(__file__).parent / "fixtures"


def rows(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))["data"]


def test_income_quarters_single_quarter_and_margins():
    q = fu.income_quarters(rows("finmind_TaiwanStockFinancialStatements_2330"))
    last = q[-1]
    assert last["quarter"] == "2026Q2" and last["revenue"] == 1270380250000.0  # ＝4～6 月營收合計
    assert last["eps"] == 27.25 and last["gross_margin"] == round(860310695000 / 1270380250000 * 100, 2)
    assert last["revenue_yoy"] is not None
    assert fu.eps_ttm(q) is not None


def test_bank_has_no_gross_profit():
    q = fu.income_quarters(rows("finmind_TaiwanStockFinancialStatements_2881"))
    assert q[-1]["gross_margin"] is None and q[-1]["eps"] is not None


def test_balance_and_dividends():
    b = fu.balance_quarters(rows("finmind_TaiwanStockBalanceSheet_2330"))
    assert b[-1]["quarter"] == "2026Q2" and 0 < b[-1]["debt_ratio"] < 100 and b[-1]["book_value_per_share"] > 0
    inc = fu.income_quarters(rows("finmind_TaiwanStockFinancialStatements_2330"), 40)
    d = fu.dividend_years(rows("finmind_TaiwanStockDividend_2330"), inc)
    y2025 = next(x for x in d if x["year"] == 2025)
    assert y2025["times"] == 4 and y2025["eps"] is not None and y2025["payout"] is not None


def test_pe_river_and_peers():
    bars = st.bars_from_finmind(rows("finmind_TaiwanStockPrice"))
    per = rows("finmind_TaiwanStockPER")
    river = fu.pe_river(per, bars)
    assert river is not None
    assert river["percentiles"] == [10, 25, 50, 75, 90]
    assert len(river["multiples"]) == 5 and river["multiples"] == sorted(river["multiples"])
    assert river["series"][-1]["date"] == "2026-10-16"
    assert len(river["series"][-1]["bands"]) == 5

    base = {
        "asof": "2026-10-16",
        "rows": [
            {"code": "2454", "name": "聯發科", "industry": "半導體業", "close": 1400.0, "change_pct": 1.0, "pe": 20.0, "pb": 5.0, "dividend_yield": 3.5, "foreign_streak": 2, "value_e8": 150.0},
            {"code": "2303", "name": "聯電", "industry": "半導體業", "close": 50.0, "change_pct": -0.5, "pe": 12.0, "pb": 1.8, "dividend_yield": 5.5, "foreign_streak": -3, "value_e8": 50.0},
            {"code": "2330", "name": "台積電", "industry": "半導體業", "close": 2420.0, "change_pct": -0.82, "pe": 28.05, "pb": 8.5, "dividend_yield": 1.5, "foreign_streak": -8, "value_e8": 1000.0},
        ],
    }
    p = fu.peers(base, "2303", "半導體業", limit=1)
    assert p is not None and p["count"] == 3 and p["median_pe"] == 20.0
    assert [r["code"] for r in p["rows"]] == ["2330", "2303"]  # limit=1 仍保證本股列入


@pytest.mark.asyncio
async def test_load_fundamentals_shares_per_cache(tmp_path):
    store = Store(str(tmp_path / "s.db"))
    calls = []

    async def fake_fetch(client, dataset, data_id=None, start=None, end=None):
        calls.append(dataset)
        mapping = {
            "TaiwanStockInfo": "finmind_info",
            "TaiwanStockFinancialStatements": "finmind_TaiwanStockFinancialStatements_2330",
            "TaiwanStockBalanceSheet": "finmind_TaiwanStockBalanceSheet_2330",
            "TaiwanStockDividend": "finmind_TaiwanStockDividend_2330",
        }
        return rows(mapping.get(dataset, f"finmind_{dataset}"))

    now = datetime(2026, 10, 17, 9, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    with patch.object(loader.finmind, "fetch", fake_fetch):
        await loader.load_page(store, None, None, "2330", now)
        calls.clear()
        res = await loader.load_fundamentals(store, None, None, "2330", now)
        assert "TaiwanStockPER" not in calls  # 沿用 load_page 的快取
        assert "TaiwanStockPrice" not in calls  # 日 K 已在小時內檢查過
        assert res["code"] == "2330" and len(res["income"]) > 0 and res["river"] is not None
        calls.clear()
        await loader.load_fundamentals(store, None, None, "2330", now)
        assert calls == []

