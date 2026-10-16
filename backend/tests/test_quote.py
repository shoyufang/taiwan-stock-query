"""行情服務：轉換、訂閱規劃、主迴圈（以假 SDK 與 fakeredis 測試，不連永豐金）。"""

import json
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import fakeredis

from app.quote import normalize as nz
from app.quote.service import INDEX_CODE, QuoteService
from app.quote.subscriptions import plan

TZ = ZoneInfo("Asia/Taipei")


def stk(**kw):
    base = dict(code="2890", datetime=(2026, 5, 21, 9, 20, 39, 959231), open=Decimal("29.8"), close=Decimal("29.9"),
                high=Decimal("30"), low=Decimal("29.75"), price_chg=Decimal("0.1"), pct_chg=33, volume=1,
                total_volume=3693, total_amount=Decimal("110307300"),
                bid_price=[Decimal("29.85"), Decimal("29.8")], bid_volume=[252, 1369],
                ask_price=[Decimal("29.9"), Decimal("29.95")], ask_volume=[50, 101], simtrade=False, suspend=False)
    base.update(kw)
    return SimpleNamespace(**base)


class TestNormalize:
    def test_stock_quote_uses_price_chg_not_pct_chg(self):
        d = nz.from_quote_stk(stk())
        assert d["change"] == 0.1
        assert d["change_pct"] == round(0.1 / 29.8 * 100, 2)  # 0.34，不是推播裡的 33
        assert d["time"] == "2026-05-21T09:20:39"
        assert d["bid"] == [[29.85, 252], [29.8, 1369]]

    def test_index_quote(self):
        q = SimpleNamespace(code="IX0001", datetime=datetime(2026, 7, 16, 11, 52, 45), close=Decimal("45625.32"),
                            reference=Decimal("45500"), open=Decimal("45400"), high=Decimal("45713.2"),
                            low=Decimal("44970.64"), amount_sum=Decimal("512300000000"), raise_count=500,
                            limit_up_count=10, flat_count=80, fall_count=400, limit_down_count=2, no_trade=3)
        d = nz.from_quote_idx(q)
        assert d["change"] == 125.32 and d["change_pct"] == round(125.32 / 45500 * 100, 2)
        assert d["raise_count"] == 500 and d["amount_sum"] == 512300000000.0

    def test_session_window(self):
        assert nz.in_session(datetime(2026, 10, 19, 9, 0, tzinfo=TZ))
        assert not nz.in_session(datetime(2026, 10, 19, 13, 50, tzinfo=TZ))
        assert not nz.in_session(datetime(2026, 10, 17, 10, 0, tzinfo=TZ))  # 週六


class TestPlan:
    def test_pinned_first_then_recent_interest(self):
        add, remove = plan({"9999"}, ["IX0001", "2330"], {"2454": 990, "2317": 995, "1101": 100}, now=1000)
        assert add == ["IX0001", "2330", "2317", "2454"]  # 1101 已超過 300 秒未關注
        assert remove == ["9999"]

    def test_cap(self):
        interest = {str(1000 + i): 1000 - i for i in range(300)}
        add, _ = plan(set(), ["IX0001"], interest, now=1000, cap=190)
        assert len(add) == 190 and add[0] == "IX0001" and add[1] == "1000"


class FakeApi:
    def __init__(self):
        self.subscribed, self.unsubscribed, self.logged_out = [], [], False
        self.contracts = SimpleNamespace(get=lambda code: SimpleNamespace(code=code))
        self.cb_stk = self.cb_idx = None

    def set_on_quote_stk_v1_callback(self, f): self.cb_stk = f
    def set_on_quote_idx_v1_callback(self, f): self.cb_idx = f
    def subscribe(self, contract, quote_type): self.subscribed.append(contract.code)
    def unsubscribe(self, contract, quote_type): self.unsubscribed.append(contract.code)
    def logout(self): self.logged_out = True

    def scanners(self, scanner_type, ascending, count):
        return [SimpleNamespace(code="2330", name="台積電", close=2420.0, change_price=-20.0, total_volume=100, total_amount=1e9)]


FAKE_SJ = SimpleNamespace(QuoteType=SimpleNamespace(Quote="quote"),
                          ScannerType=SimpleNamespace(AmountRank="a", ChangePercentRank="p"))


def make_service(now):
    rds = fakeredis.FakeRedis(decode_responses=True)
    api = FakeApi()
    clock = {"now": now}
    svc = QuoteService(rds, lambda: api, pinned=[INDEX_CODE, "2330"], clock=lambda: clock["now"], sj_module=FAKE_SJ)
    return svc, api, rds, clock


class TestService:
    def test_streaming_then_logout_after_close(self):
        svc, api, rds, clock = make_service(datetime(2026, 10, 19, 9, 0, tzinfo=TZ))
        assert svc.step() == "streaming"
        assert api.subscribed == [INDEX_CODE, "2330"]
        assert json.loads(rds.get("q:scanner"))["amount"][0]["code"] == "2330"

        api.cb_stk("TSE", stk(code="2330", close=Decimal("2420"), price_chg=Decimal("-20")))
        assert json.loads(rds.get("q:last:2330"))["change_pct"] == round(-20 / 2440 * 100, 2)

        clock["now"] = datetime(2026, 10, 19, 13, 55, tzinfo=TZ)
        assert svc.step() == "closed" and api.logged_out and svc.api is None

    def test_interest_adds_dynamic_subscription(self):
        svc, api, rds, clock = make_service(datetime(2026, 10, 19, 9, 0, tzinfo=TZ))
        rds.zadd("quote:interest", {"2603": clock["now"].timestamp()})
        svc.step()
        assert "2603" in api.subscribed

    def test_login_failure_backs_off(self):
        svc, api, rds, clock = make_service(datetime(2026, 10, 19, 9, 0, tzinfo=TZ))
        svc.api_factory = lambda: (_ for _ in ()).throw(RuntimeError("bad key"))
        assert svc.step() == "login_failed"
        assert svc.step() == "waiting_retry"
        svc.write_status("login_failed")
        assert "bad key" in json.loads(rds.get("quote:status"))["error"]
