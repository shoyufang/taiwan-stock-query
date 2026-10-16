"""投資行事曆（純函式）：除權息（證交所 TWT48U）、法說會（MOPS）、法定公布期限。"""

from __future__ import annotations

import re
from datetime import date, timedelta

from app.services import overview as ov

_ROC_CJK = re.compile(r"(\d{2,3})年(\d{1,2})月(\d{1,2})日")
_ROC_SLASH = re.compile(r"(\d{2,3})/(\d{1,2})/(\d{1,2})")


def roc_cjk(s: str) -> date | None:
    m = _ROC_CJK.search(s or "")
    return date(int(m[1]) + 1911, int(m[2]), int(m[3])) if m else None


def roc_slash_all(s: str) -> list[date]:
    return [date(int(y) + 1911, int(m), int(d)) for y, m, d in _ROC_SLASH.findall(s or "")]


def parse_twt48u(raw: dict) -> list[dict]:
    f = {name: i for i, name in enumerate(raw.get("fields") or [])}
    out = []
    for r in raw.get("data", []):
        d = roc_cjk(r[f["除權除息日期"]])
        if not d:
            continue
        kind = r[f["除權息"]].strip()
        cash = ov.num(r[f["現金股利"]]) if "<" not in r[f["現金股利"]] else None
        stock = ov.num(r[f["無償配股率"]])
        detail = []
        if "息" in kind:
            detail.append(f"現金股利 {cash:g} 元" if cash else "現金股利待公告")
        if "權" in kind and stock:
            detail.append(f"無償配股率 {stock:g}")
        out.append({"date": d.isoformat(), "kind": "dividend", "code": r[f["股票代號"]].strip(),
                    "name": r[f["名稱"]].strip(), "title": f"除{kind}", "detail": "，".join(detail)})
    return out


def conference_events(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        days = roc_slash_all(r["date_text"])
        if not days:
            continue
        span = f"（{days[0].strftime('%m/%d')}～{days[-1].strftime('%m/%d')}）" if len(days) > 1 and days[-1] != days[0] else ""
        summary = r["summary"]
        out.append({"date": days[0].isoformat(), "kind": "conference", "code": r["code"], "name": r["name"],
                    "title": f"法說會 {r['time']}{span}".strip(),
                    "detail": (summary[:120] + "…") if len(summary) > 120 else summary, "place": r["place"]})
    return out


def deadline_events(start: date, end: date) -> list[dict]:
    """法定期限：月營收每月 10 日前；Q1 5/15、Q2 8/14、Q3 11/14、年報 3/31。"""
    out = []
    y, m = start.year, start.month
    while date(y, m, 1) <= end:
        d = date(y, m, 10)
        prev_m = 12 if m == 1 else m - 1
        if start <= d <= end:
            out.append({"date": d.isoformat(), "kind": "deadline", "title": f"{prev_m} 月營收公布期限", "detail": "上市櫃公司須於每月 10 日前公布上月營收"})
        for mm, dd, label in ((3, 31, f"{y - 1} 年年報"), (5, 15, "第一季財報"), (8, 14, "第二季財報"), (11, 14, "第三季財報")):
            if m == mm:
                d2 = date(y, mm, dd)
                if start <= d2 <= end:
                    out.append({"date": d2.isoformat(), "kind": "deadline", "title": f"{label}公布期限", "detail": "一般上市櫃公司法定截止日"})
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def build(today: date, dividends: list[dict], conferences: list[dict], generated_at: str,
          back_days: int = 7, ahead_days: int = 60) -> dict:
    start, end = today - timedelta(days=back_days), today + timedelta(days=ahead_days)
    events = [e for e in dividends + conferences if start.isoformat() <= e["date"] <= end.isoformat()]
    events += deadline_events(start, end)
    order = {"deadline": 0, "dividend": 1, "conference": 2}
    events.sort(key=lambda e: (e["date"], order[e["kind"]], e.get("code", "")))
    return {"generated_at": generated_at, "today": today.isoformat(), "start": start.isoformat(), "end": end.isoformat(),
            "events": events, "sources": ["臺灣證券交易所（除權息預告 TWT48U）", "公開資訊觀測站（法人說明會）"],
            "note": "除權息預告為上市股票；法說會含上市與上櫃。"}
