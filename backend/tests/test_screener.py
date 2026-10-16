import copy
import json
from pathlib import Path

from app.services import screener as sc

FIX = Path(__file__).parent / "fixtures"
load = lambda n: json.loads((FIX / n).read_text(encoding="utf-8"))  # noqa: E731


def t86_with(base: dict, foreign_by_code: dict[str, int]) -> dict:
    """以真實 T86 結構造出前幾天的資料（只改外資欄）。"""
    d = copy.deepcopy(base)
    f = {n: i for i, n in enumerate(d["fields"])}
    col = f["外陸資買賣超股數(不含外資自營商)"]
    for row in d["data"]:
        if row[0].strip() in foreign_by_code:
            row[col] = f"{foreign_by_code[row[0].strip()]:,}"
    return d


def test_parse_bwibbu_matches_official():
    v = sc.parse_bwibbu(load("bwibbu_20261016.json"))
    assert v["2330"] == {"pe": 28.05, "dividend_yield": 0.91, "pb": 9.76}  # 與 FinMind 同日數字一致
    assert v["1101"]["pe"] is None  # 虧損股本益比為「-」


def test_signed_streak():
    assert sc.signed_streak([1, -2, -3]) == -2
    assert sc.signed_streak([5, 6]) == 2
    assert sc.signed_streak([5, 0]) == 0


def test_build_base():
    t86_today = load("t86_20261016.json")
    days = [
        t86_with(t86_today, {"2454": -1_000_000, "2002": 5_000_000}),
        t86_with(t86_today, {"2454": 2_000_000, "2002": 6_000_000}),  # 2454 前一天買超 → 打斷賣超
        t86_today,                                                     # 10/16：2454 外資 −1,622,341 股
    ]
    bw = load("bwibbu_20261016.json")
    base = sc.build_base("2026-10-16", load("mi_index_20261016.json"), days, bw, {"2454": "半導體業"}, "t")
    rows = {r["code"]: r for r in base["rows"]}
    r = rows["2454"]
    assert r["foreign"] == -1622 and r["foreign_streak"] == -1
    assert rows["2002"]["foreign_streak"] == 3  # 中鋼連 3 日買超
    v = sc.parse_bwibbu(bw)["2454"]
    assert (r["pe"], r["dividend_yield"], r["pb"], r["industry"]) == (v["pe"], v["dividend_yield"], v["pb"], "半導體業")
    assert r["close"] == 4250 and r["change_pct"] == 2.04  # 與市場總覽 10/16 數字一致
    assert "0050" not in rows and "00400A" not in rows  # 只收普通股
    assert base["days"] == 3
