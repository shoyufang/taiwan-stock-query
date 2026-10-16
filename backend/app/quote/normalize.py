"""把 Shioaji 推播物件轉成前端用的 dict（純函式，不 import shioaji，方便測試）。

注意：推播的 pct_chg 單位是萬分之一（0.33% 寫成 33），這裡不用它，改由 price_chg 自算。
"""

from __future__ import annotations

from datetime import date, datetime, time


def _f(x) -> float | None:
    return None if x is None else float(x)


def _iso(dt) -> str | None:
    """Shioaji 的 datetime 可能是 datetime 或 tuple（文件兩種範例都有）。"""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat(timespec="seconds")
    if isinstance(dt, (tuple, list)):
        return datetime(*dt).isoformat(timespec="seconds")
    return str(dt)


def _pct(change: float, close: float | None) -> float:
    if close is None:
        return 0.0
    prev = close - change
    return round(change / prev * 100, 2) if prev else 0.0


def from_quote_stk(q) -> dict:
    """QuoteSTKv1（成交＋五檔同一筆）→ dict。量的單位：張。"""
    close = _f(q.close)
    change = _f(q.price_chg) or 0.0
    return {
        "kind": "stock",
        "code": q.code,
        "time": _iso(getattr(q, "datetime", None)),
        "close": close,
        "open": _f(q.open),
        "high": _f(q.high),
        "low": _f(q.low),
        "change": change,
        "change_pct": _pct(change, close),
        "volume": int(q.volume or 0),
        "total_volume": int(q.total_volume or 0),
        "total_amount": _f(q.total_amount),
        "bid": [[float(p), int(v)] for p, v in zip(q.bid_price or [], q.bid_volume or [])],
        "ask": [[float(p), int(v)] for p, v in zip(q.ask_price or [], q.ask_volume or [])],
        "simtrade": bool(getattr(q, "simtrade", False)),
        "suspend": bool(getattr(q, "suspend", False)),
    }


def from_quote_idx(q) -> dict:
    """QuoteIdxV1 → dict。指數推播附帶全市場漲跌家數與累計成交金額（僅大盤）。"""
    close = _f(q.close)
    ref = _f(getattr(q, "reference", None))
    change = (close - ref) if (close is not None and ref) else 0.0
    return {
        "kind": "index",
        "code": q.code,
        "time": _iso(getattr(q, "datetime", None)),
        "close": close,
        "reference": ref,
        "open": _f(q.open),
        "high": _f(q.high),
        "low": _f(q.low),
        "change": round(change, 2),
        "change_pct": round(change / ref * 100, 2) if ref else 0.0,
        "amount_sum": _f(getattr(q, "amount_sum", None)),
        # 漲跌家數：原樣保留，是否含漲停／跌停待開盤後與證交所收盤統計比對確認
        "raise_count": getattr(q, "raise_count", None),
        "limit_up_count": getattr(q, "limit_up_count", None),
        "flat_count": getattr(q, "flat_count", None),
        "fall_count": getattr(q, "fall_count", None),
        "limit_down_count": getattr(q, "limit_down_count", None),
        "no_trade": getattr(q, "no_trade", None),
    }


def from_scanner(items) -> list[dict]:
    """ScannerItem 清單 → dict 清單。"""
    out = []
    for s in items:
        close = _f(s.close)
        change = _f(s.change_price) or 0.0
        out.append({
            "code": s.code,
            "name": s.name,
            "close": close,
            "change": change,
            "change_pct": _pct(change, close),
            "total_volume": int(s.total_volume or 0),
            "total_amount": _f(s.total_amount),
        })
    return out


# 盤中時段（台北時間）：與前端 marketMode 的規則一致；國定假日未處理
SESSION_START = time(8, 25)
SESSION_END = time(13, 50)


def in_session(now: datetime) -> bool:
    return now.weekday() < 5 and SESSION_START <= now.time() < SESSION_END


def trading_date(now: datetime) -> date:
    return now.date()
