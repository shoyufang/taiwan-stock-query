import json
from datetime import date
from pathlib import Path

from app.services import calendar as cal
from app.sources import mops

FIX = Path(__file__).parent / "fixtures"


def load_dividends():
    return cal.parse_twt48u(json.loads((FIX / "twt48u.json").read_text(encoding="utf-8")))


def load_conferences():
    return mops.parse_conferences((FIX / "mops_conference_11510.html").read_text(encoding="utf-8"))


def test_roc_dates():
    assert cal.roc_cjk("115年10月22日") == date(2026, 10, 22)
    assert cal.roc_slash_all("115/09/11 至 115/10/13") == [date(2026, 9, 11), date(2026, 10, 13)]
    assert cal.roc_cjk("") is None


def test_twt48u_parsing():
    d = load_dividends()
    assert len(d) == 55
    first = d[0]
    assert first == {"date": "2026-10-15", "kind": "dividend", "code": "00401A", "name": "主動摩根台灣鑫收",
                     "title": "除息", "detail": "現金股利 0.131 元"}
    # 現金股利欄位為 HTML 說明（待公告）時不得當成 0 元
    assert any(e["detail"] == "現金股利待公告" for e in d)


def test_conference_parsing():
    rows = load_conferences()
    assert len(rows) == 81
    assert rows[0]["code"] == "1203" and rows[0]["name"] == "味王"
    ev = cal.conference_events(rows)
    assert ev[0]["date"] == "2026-10-14" and ev[0]["title"].startswith("法說會")
    # 日期為區間時取起日，並在標題保留區間
    ranged = [e for e in ev if "～" in e["title"]]
    for e in ranged:
        assert e["date"] <= "2026-10-31"


def test_deadlines():
    ev = cal.deadline_events(date(2026, 10, 10), date(2026, 12, 16))
    assert [(e["date"], e["title"]) for e in ev] == [
        ("2026-10-10", "9 月營收公布期限"), ("2026-11-10", "10 月營收公布期限"),
        ("2026-11-14", "第三季財報公布期限"), ("2026-12-10", "11 月營收公布期限")]
    jan = cal.deadline_events(date(2027, 1, 1), date(2027, 3, 31))
    assert ("2027-01-10", "12 月營收公布期限") in [(e["date"], e["title"]) for e in jan]
    assert ("2027-03-31", "2026 年年報公布期限") in [(e["date"], e["title"]) for e in jan]


def test_build_window_and_order():
    data = cal.build(date(2026, 10, 17), load_dividends(), cal.conference_events(load_conferences()), "t")
    assert data["start"] == "2026-10-10" and data["end"] == "2026-12-16"
    dates = [e["date"] for e in data["events"]]
    assert dates == sorted(dates) and dates[0] >= "2026-10-10"
    assert {e["kind"] for e in data["events"]} == {"dividend", "conference", "deadline"}
