"""警示：規則判斷、去重、通知、API（不連外部服務）。"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import fakeredis
import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import alert_runner as runner
from app.services import alerts as al
from app.services import notify
from app.store import Store

TZ = ZoneInfo("Asia/Taipei")


def bars_from(closes):
    return [{"date": f"2026-09-{i + 1:02d}", "open": c, "high": c, "low": c, "close": c, "volume": 1, "value": 1}
            for i, c in enumerate(closes)]


class TestRules:
    def test_price_rules(self):
        assert al.eval_price({"type": "price_above", "value": 2450}, 2455, 1.0, "現價") == "價格突破 2,450 元（現價 2,455）"
        assert al.eval_price({"type": "price_above", "value": 2450}, 2449, 1.0, "現價") is None
        assert al.eval_price({"type": "price_below", "value": 2400}, 2400, -1.0, "現價").startswith("價格跌破 2,400")

    def test_pct_move_uses_percent_not_amount(self):
        # 舊站的 bug：拿漲跌金額比百分比。台積電跌 20 元＝−0.82%，門檻 3% 不應觸發
        assert al.eval_price({"type": "pct_move", "value": 3}, 2420, -0.82, "現價") is None
        assert al.eval_price({"type": "pct_move", "value": 3}, 2420, -3.41, "現價") == "單日下跌 3.41%（門檻 3%）"

    def test_ma20_break_only_on_cross(self):
        up = [100.0] * 20 + [101.0]
        assert al.eval_close({"type": "ma20_break", "value": 0}, bars_from(up + [95.0]), []).startswith("收盤 95 跌破月線")
        # 已經在月線下方又往下，不算「跌破」
        assert al.eval_close({"type": "ma20_break", "value": 0}, bars_from([100.0] * 20 + [95.0, 94.0]), []) is None
        assert al.eval_close({"type": "ma20_reclaim", "value": 0}, bars_from([100.0] * 20 + [99.0, 105.0]), []).startswith("收盤 105 站上月線")

    def test_foreign_streak(self):
        r = {"type": "foreign_sell_streak", "value": 3}
        assert al.eval_close(r, bars_from([1, 2]), [500, -1, -2, -22046]) == "外資連續 3 天賣超（今日 -22,046 張）"
        assert al.eval_close(r, bars_from([1, 2]), [-1, 5, -2]) is None

    def test_validate(self):
        assert al.validate("price_above", 2450) is None
        assert al.validate("pct_move", 50) is not None
        assert al.validate("nope", 1) is not None


class TestStoreDedupe:
    def test_once_per_day(self, tmp_path):
        s = Store(str(tmp_path / "a.db"))
        rid = s.add_rule("2330", "price_above", 2450, "2026-10-19T09:00:00")
        assert s.mark_triggered(rid, "2026-10-19", "2330", "price_above", "m", "t")
        assert not s.mark_triggered(rid, "2026-10-19", "2330", "price_above", "m", "t")
        assert s.mark_triggered(rid, "2026-10-20", "2330", "price_above", "m", "t")
        assert len(s.list_events()) == 2

    def test_watchlist_default_until_set(self, tmp_path):
        s = Store(str(tmp_path / "b.db"))
        assert s.get_watchlist() is None
        s.set_watchlist([])
        assert s.get_watchlist() == []  # 使用者清空 ≠ 從未設定
        s.set_watchlist(["2330", "6488"])
        assert s.get_watchlist() == ["2330", "6488"]


class TestNotify:
    @pytest.mark.asyncio
    async def test_send_all_channels(self):
        rds = fakeredis.FakeAsyncRedis(decode_responses=True)
        sent = []

        def handler(req: httpx.Request):
            sent.append((str(req.url), json.loads(req.content)))
            return httpx.Response(200, json={"ok": True})

        cfg = {"ntfy_url": "http://ntfy", "ntfy_topic": "twstock", "telegram_token": "T", "telegram_chat": "42",
               "public_url": "http://100.100.245.93:8600"}
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            res = await notify.send(rds, http, title="台積電 2330", message="價格突破 2,450 元", code="2330", at="t", cfg=cfg)
        assert res == {"web": True, "ntfy": True, "telegram": True}
        ntfy = [b for u, b in sent if u.startswith("http://ntfy")][0]
        assert ntfy["click"] == "http://100.100.245.93:8600/stock/2330" and ntfy["topic"] == "twstock"
        tg = [b for u, b in sent if "telegram" in u][0]
        assert tg["chat_id"] == "42" and "價格突破" in tg["text"]

    def test_channels_without_config(self):
        cfg = {"ntfy_url": "", "ntfy_topic": "t", "telegram_token": "", "telegram_chat": "", "public_url": ""}
        assert notify.channels(cfg) == {"web": True, "ntfy": False, "telegram": False}


class TestRunner:
    @pytest.mark.asyncio
    async def test_fire_notifies_once(self, tmp_path):
        s = Store(str(tmp_path / "c.db"))
        rid = s.add_rule("2330", "price_above", 2450, "x")
        app = type("A", (), {})()
        app.state = type("S", (), {"store": s, "redis": fakeredis.FakeAsyncRedis(decode_responses=True), "http": None})()
        rule = s.list_rules()[0]
        now = datetime(2026, 10, 19, 9, 30, tzinfo=TZ)
        with patch.object(runner.notify, "send", AsyncMock()) as send:
            assert await runner.fire(app, rule, "價格突破", "2026-10-19", now, {"2330": "台積電"})
            assert not await runner.fire(app, rule, "價格突破", "2026-10-19", now, {"2330": "台積電"})
        assert send.await_count == 1
        assert s.list_events()[0]["message"] == "台積電 2330：價格突破" and rid == rule["id"]


class TestWatchlistRow:
    @pytest.mark.asyncio
    async def test_row_uses_latest_bar(self, tmp_path):
        from types import SimpleNamespace

        from app import api_watchlist
        s = Store(str(tmp_path / "w.db"))
        s.upsert_bars("2330", [
            {"date": "2026-10-15", "open": 2420, "high": 2450, "low": 2420, "close": 2440, "volume": 58487, "value": 1},
            {"date": "2026-10-16", "open": 2430, "high": 2445, "low": 2420, "close": 2420, "volume": 43047, "value": 1},
        ])
        req = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(store=s, finmind=None)))
        info = [{"stock_id": "2330", "stock_name": "台積電", "industry_category": "半導體業", "type": "twse"}]
        with patch.object(api_watchlist.loader, "ensure_bars", AsyncMock()):
            row = await api_watchlist._row(req, "2330", info, None)
        assert (row["date"], row["close"], row["change"], row["change_pct"]) == ("2026-10-16", 2420, -20, round(-20 / 2440 * 100, 2))


class TestApi:
    def test_rules_crud_and_validation(self):
        server = fakeredis.FakeServer()
        rds = fakeredis.FakeAsyncRedis(server=server, decode_responses=True)
        info = [{"stock_id": "2330", "stock_name": "台積電", "industry_category": "半導體業", "type": "twse"}]
        with patch.object(main.cache, "make_client", return_value=rds), \
             patch("app.services.stock_loader.stock_info", AsyncMock(return_value=info)), \
             TestClient(main.app) as c:
            assert c.post("/api/alerts", json={"code": "2330", "type": "pct_move", "value": 50}).status_code == 400
            assert c.post("/api/alerts", json={"code": "9999", "type": "price_above", "value": 1}).status_code == 400
            rid = c.post("/api/alerts", json={"code": "2330", "type": "price_above", "value": 2450}).json()["id"]
            body = c.get("/api/alerts").json()
            assert [r["id"] for r in body["rules"]] == [rid] and body["channels"]["web"]
            sync = fakeredis.FakeRedis(server=server, decode_responses=True)
            assert "2330" in sync.smembers("quote:pinned")
            assert c.patch(f"/api/alerts/{rid}", json={"enabled": False}).status_code == 200
            assert c.delete(f"/api/alerts/{rid}").status_code == 200
            assert c.delete(f"/api/alerts/{rid}").status_code == 404
