"""處置股與注意股（純函式）。

來源：證交所 rwd announcement/punish（處置，可帶日期區間）、announcement/notice（注意，指定日期）；
櫃買中心 OpenAPI tpex_disposal_information、tpex_trading_warning_information。
只保留普通股（4 碼、非 0 開頭）；權證、可轉債等衍生的處置不列。
"""

from __future__ import annotations

import re
from datetime import date

from app.services import overview as ov

_TAG = re.compile(r"<[^>]+>")
_ROC_SLASH = re.compile(r"(\d{2,3})/(\d{1,2})/(\d{1,2})")
_ROC_COMPACT = re.compile(r"(\d{3})(\d{2})(\d{2})")


def _clean(s: str) -> str:
    return " ".join(_TAG.sub("", s or "").split())


def _slash_dates(s: str) -> list[date]:
    return [date(int(y) + 1911, int(m), int(d)) for y, m, d in _ROC_SLASH.findall(s or "")]


def _compact(s: str) -> date | None:
    m = _ROC_COMPACT.fullmatch((s or "").strip())
    return date(int(m[1]) + 1911, int(m[2]), int(m[3])) if m else None


def _compact_all(s: str) -> list[date]:
    return [d for part in re.split(r"[~～]", s or "") if (d := _compact(part))]


def _measure_of(detail: str) -> str:
    """處置內容裡的撮合頻率（約每 5 分鐘／20 分鐘撮合一次），讓使用者一眼看出嚴重程度。"""
    m = re.search(r"每\s*([０-９\d一二三四五六七八九十]+)\s*分鐘撮合一次", detail or "")
    if not m:
        return ""
    return f"約每 {_number(m[1])} 分鐘撮合一次"


_CJK_DIGIT = {c: i for i, c in enumerate("零一二三四五六七八九")}


def _number(s: str) -> int:
    """'5'、'５'、'二'、'二十'、'六十' → 整數（證交所用國字，櫃買用阿拉伯數字）。"""
    s = s.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    if s.isdigit():
        return int(s)
    if "十" in s:
        tens, _, ones = s.partition("十")
        return (_CJK_DIGIT.get(tens, 1) if tens else 1) * 10 + (_CJK_DIGIT.get(ones, 0) if ones else 0)
    return _CJK_DIGIT.get(s, 0)


def twse_disposition(raw: dict) -> list[dict]:
    f = {n: i for i, n in enumerate(raw.get("fields") or [])}
    out = []
    for r in raw.get("data", []):
        code = str(r[f["證券代號"]]).strip()
        days = _slash_dates(r[f["處置起迄時間"]])
        if not ov.is_common_stock(code) or len(days) < 2:
            continue
        out.append({"code": code, "name": r[f["證券名稱"]].strip(), "market": "上市",
                    "announced": _slash_dates(r[f["公布日期"]])[0].isoformat(),
                    "start": days[0].isoformat(), "end": days[-1].isoformat(),
                    "reason": _clean(r[f["處置條件"]]), "measure": _clean(r[f["處置措施"]]),
                    "match": _measure_of(r[f["處置內容"]])})
    return out


def tpex_disposition(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        code = str(r.get("SecuritiesCompanyCode", "")).strip()
        days = _compact_all(r.get("DispositionPeriod", ""))
        announced = _compact(r.get("Date", ""))
        if not ov.is_common_stock(code) or len(days) < 2 or not announced:
            continue
        out.append({"code": code, "name": r.get("CompanyName", "").strip(), "market": "上櫃",
                    "announced": announced.isoformat(), "start": days[0].isoformat(), "end": days[-1].isoformat(),
                    "reason": _clean(r.get("DispositionReasons", "")), "measure": "",
                    "match": _measure_of(r.get("DisposalCondition", ""))})
    return out


def twse_notice(raw: dict) -> list[dict]:
    f = {n: i for i, n in enumerate(raw.get("fields") or [])}
    out = []
    for r in raw.get("data", []):
        code = str(r[f["證券代號"]]).strip()
        if not ov.is_common_stock(code):
            continue
        out.append({"code": code, "name": r[f["證券名稱"]].strip(), "market": "上市",
                    "reason": _clean(r[f["注意交易資訊"]]), "close": ov.num(r[f["收盤價"]]),
                    "count": int(ov.num(r[f["累計次數"]]) or 1)})
    return out


def tpex_notice(rows: list[dict], asof: date) -> list[dict]:
    out = []
    for r in rows:
        code = str(r.get("SecuritiesCompanyCode", "")).strip()
        if not ov.is_common_stock(code) or _compact(r.get("Date", "")) != asof:
            continue
        out.append({"code": code, "name": r.get("CompanyName", "").strip(), "market": "上櫃",
                    "reason": _clean(r.get("TradingInformation", "")), "close": ov.num(r.get("ClosePrice")), "count": None})
    return out


def build(asof: date, today: date, disposition: list[dict], notice: list[dict], generated_at: str) -> dict:
    """處置：只留「今天仍在處置期間或尚未開始」的；同一檔多筆時取最新公告。注意：asof 當日。"""
    latest: dict[str, dict] = {}
    for d in disposition:
        if d["end"] < today.isoformat():
            continue
        cur = latest.get(d["code"])
        if not cur or (d["announced"], d["start"]) > (cur["announced"], cur["start"]):
            latest[d["code"]] = d
    disp = sorted(latest.values(), key=lambda d: (d["start"], d["code"]), reverse=True)
    return {"generated_at": generated_at, "asof": asof.isoformat(), "today": today.isoformat(),
            "disposition": disp, "notice": sorted(notice, key=lambda n: (n["market"], n["code"])),
            "sources": ["臺灣證券交易所（公布處置／注意有價證券）", "證券櫃檯買賣中心 OpenAPI"],
            "note": "只列普通股；權證、可轉債等不列。處置期間以交易所公告為準。"}


def new_dispositions(data: dict, seen: set[str]) -> list[dict]:
    return [d for d in data["disposition"] if f"{d['code']}|{d['start']}" not in seen]


def disposition_key(d: dict) -> str:
    return f"{d['code']}|{d['start']}"
