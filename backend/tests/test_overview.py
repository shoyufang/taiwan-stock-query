"""用 2026-10-16 證交所／Yahoo 真實回應（tests/fixtures）驗證解析與組裝。"""

import json
from datetime import date
from pathlib import Path

import pytest

from app.services import overview as ov
from app.sources import yahoo

FIX = Path(__file__).parent / "fixtures"
load = lambda name: json.loads((FIX / name).read_text(encoding="utf-8"))  # noqa: E731


@pytest.fixture(scope="module")
def mi():
    return load("mi_index_20261016.json")


@pytest.fixture(scope="module")
def t86():
    return load("t86_20261016.json")


class TestBasics:
    def test_num(self):
        assert ov.num("993,814,830,090") == 993814830090
        assert ov.num("--") is None and ov.num("") is None

    def test_sign(self):
        assert ov.sign_of("<p style ='color:red'>+</p>") == 1
        assert ov.sign_of("<p style= color:green>-</p>") == -1
        assert ov.sign_of("<p> </p>") == 0

    def test_count_with_limit(self):
        assert ov.count_with_limit("684(19)") == (684, 19)
        assert ov.count_with_limit("1,190") == (1190, 0)

    def test_common_stock(self):
        assert ov.is_common_stock("2330")
        assert not ov.is_common_stock("0050")
        assert not ov.is_common_stock("00400A")

    def test_move_word(self):
        assert [ov.move_word(p) for p in (3, 1, 0.3, 0, -0.3, -1, -3.41)] == ["大漲", "上漲", "小漲", "平盤", "小跌", "下跌", "重挫"]


class TestMiIndex:
    def test_taiex_official(self, mi):
        p = ov.parse_mi_index(mi)
        assert p["taiex"] == {"close": 47111.26, "change": 141.39, "change_pct": 0.30}

    def test_turnover_is_total_row(self, mi):
        assert ov.parse_mi_index(mi)["turnover_twd"] == 993_814_830_090

    def test_breadth_uses_stock_column(self, mi):
        assert ov.parse_mi_index(mi)["breadth"] == {"up": 684, "up_limit": 19, "down": 286, "down_limit": 0, "flat": 106, "untraded": 5}

    def test_quote_signed_change_and_pct(self, mi):
        q = {x["code"]: x for x in ov.parse_mi_index(mi)["quotes"]}
        assert q["9958"]["close"] == 87.40 and q["9958"]["change"] == -1.10
        assert q["9958"]["change_pct"] == round(-1.10 / 88.50 * 100, 2)
        assert q["00400A"]["change"] == 0.07

    def test_has_trading_data(self, mi):
        assert ov.has_trading_data(mi)
        assert not ov.has_trading_data({"stat": "很抱歉，沒有符合條件的資料!", "tables": []})


class TestT86:
    def test_field_mapping_matches_raw(self, t86):
        f = {n: i for i, n in enumerate(t86["fields"])}
        raw = t86["data"][0]
        parsed = ov.parse_t86(t86)[0]
        assert parsed["code"] == raw[f["證券代號"]].strip()
        assert parsed["foreign"] == int(raw[f["外陸資買賣超股數(不含外資自營商)"]].replace(",", ""))
        assert parsed["trust"] == int(raw[f["投信買賣超股數"]].replace(",", ""))
        assert parsed["dealer"] == int(raw[f["自營商買賣超股數"]].replace(",", ""))


class TestSeries:
    def test_fmtqik(self):
        s = ov.parse_fmtqik(load("fmtqik_202610.json"))
        assert s[0] == {"date": "2026-10-01", "close": 48353.49}
        assert s[-1] == {"date": "2026-10-16", "close": 47111.26}

    def test_yahoo_us_close_before_taiwan_date(self):
        bars = yahoo.parse_bars(load("yahoo_gspc.json"))
        last, prev = yahoo.last_before(bars, date(2026, 10, 16))
        assert last["date"] == date(2026, 10, 15) and round(last["close"], 2) == 7744.06
        assert prev["date"] == date(2026, 10, 14)


class TestBuild:
    @pytest.fixture(scope="class")
    def data(self, mi, t86):
        series = ov.parse_fmtqik(load("fmtqik_202610.json"))
        return ov.build_overview(date(2026, 10, 16), mi, t86, series, [], "2026-10-17T00:00:00+08:00")

    def test_headline_and_lead(self, data):
        assert data["headline"] == "加權指數小漲 0.30%，收 47,111 點"
        assert data["lead"].startswith("上市股票 684 家上漲、286 家下跌，成交金額 9,938 億元。")

    def test_rankings(self, data):
        values = [r["value_twd"] for r in data["top_value"]]
        assert values == sorted(values, reverse=True)
        assert all(ov.is_common_stock(r["code"]) for r in data["gainers"] + data["losers"])
        assert data["gainers"][0]["change_pct"] >= data["gainers"][-1]["change_pct"]
        assert data["losers"][0]["change_pct"] <= data["losers"][-1]["change_pct"]

    def test_foreign_lists_signs(self, data):
        assert all(r["lots"] > 0 for r in data["foreign_buy"])
        assert all(r["lots"] < 0 for r in data["foreign_sell"])

    def test_single_asof(self, data):
        assert data["asof"] == "2026-10-16"
        assert data["index_series"][-1]["date"] == "2026-10-16"
