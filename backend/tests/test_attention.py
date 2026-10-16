import json
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import fakeredis
import pytest

from app.services import attention as att
from app.services import attention_notify as an
from app.store import Store

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def build():
    disp = att.twse_disposition(load("twse_punish.json")) + att.tpex_disposition(load("tpex_disposal.json"))
    notice = att.twse_notice(load("twse_notice_20261016.json")) + att.tpex_notice(load("tpex_warning.json"), date(2026, 10, 16))
    return att.build(date(2026, 10, 16), date(2026, 10, 17), disp, notice, "t")


def test_number_and_measure():
    assert att._number("二") == 2 and att._number("二十") == 20 and att._number("十") == 10 and att._number("５") == 5
    assert att._measure_of("約每二十分鐘撮合一次") == "約每 20 分鐘撮合一次"
    assert att._measure_of("(約每2分鐘撮合一次)") == "約每 2 分鐘撮合一次"


def test_build_filters_and_dedupes():
    b = build()
    codes = [d["code"] for d in b["disposition"]]
    assert len(codes) == len(set(codes)), "同一檔只留最新一筆"
    assert all(len(c) == 4 and not c.startswith("0") for c in codes), "只留普通股"
    assert all(d["end"] >= "2026-10-17" for d in b["disposition"]), "已結束的處置不列"
    hua = next(d for d in b["disposition"] if d["code"] == "4979")
    assert (hua["name"], hua["market"], hua["start"], hua["end"]) == ("華星光", "上櫃", "2026-10-19", "2026-10-23")
    twse = [d for d in b["disposition"] if d["market"] == "上市"]
    assert twse and all(d["match"].startswith("約每") for d in twse)
    # 注意股：上市 10/16 共 17 筆（含權證），只留普通股；上櫃只留 10/16
    n = {x["code"]: x for x in b["notice"]}
    assert "053040" not in n and "2360" in n and n["2360"]["close"] == 2000.0
    assert "<font" not in n["2360"]["reason"]
    assert all(x["market"] in ("上市", "上櫃") for x in b["notice"])


@pytest.mark.asyncio
async def test_notify_first_run_silent_then_only_new(tmp_path):
    rds = fakeredis.FakeAsyncRedis(decode_responses=True)
    store = Store(str(tmp_path / "s.db"))
    store.set_watchlist(["2360"])
    data = build()
    await rds.set("attention:latest", json.dumps(data, ensure_ascii=False))
    app = SimpleNamespace(state=SimpleNamespace(redis=rds, store=store, http=None))
    now = datetime(2026, 10, 17, 15, 0)
    with patch.object(an.notify, "send", AsyncMock()) as send:
        assert await an.run_once(app, now, []) == 0  # 初始化不通知
        assert await an.run_once(app, now, []) == 0  # 沒有新的
        # 新增一檔處置（自選股 2360）
        data["disposition"].append({"code": "2360", "name": "致茂", "market": "上市", "announced": "2026-10-17",
                                    "start": "2026-10-20", "end": "2026-10-26", "reason": "連續三次",
                                    "measure": "第一次處置", "match": "約每 5 分鐘撮合一次"})
        data["asof"] = "2026-10-19"  # 新的一天，2360 仍在注意股
        await rds.set("attention:latest", json.dumps(data, ensure_ascii=False))
        assert await an.run_once(app, now, []) == 2
        assert await an.run_once(app, now, []) == 0
    titles = [c.kwargs["title"] for c in send.await_args_list]
    assert titles == ["新增處置股 1 檔", "致茂 2360 被列注意股"]
    assert "★2360 致茂（上市）10/20～10/26，約每 5 分鐘撮合一次" in send.await_args_list[0].kwargs["message"]
    assert [e["type"] for e in store.list_events()] == ["notice", "disposition"]
