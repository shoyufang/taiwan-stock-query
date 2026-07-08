"""
資料路由層（R4）— 同一資料主題、多個來源，呼叫端不必知道來源差異。

目前實作 get_institutional()（三大法人買賣超）、get_valuation()（本益比/
股淨比/殖利率）；K線/融資融券路由留待後續 session 擴充
（見 docs/plans/REDESIGN_PLAN_2026-07.md R4）。

get_institutional 統一欄位（原始股數，不做張/億轉換，轉換交給呼叫端依用途決定）：
    日期, 代號, 名稱, 外資買賣超, 投信買賣超, 自營商買賣超

get_valuation 統一欄位：
    日期, 代號, 名稱, 本益比, 股淨比, 殖利率%
"""

from datetime import date, timedelta
import pandas as pd

from datasources.twse_client import query_twse_institutional_numeric, query_twse_bwibbu, query_twse_margin
from datasources.finmind_client import query_institutional, query_per_pbr, query_margin_short
from logging_config import main_logger

_UNIFIED_COLS = ["日期", "代號", "名稱", "外資買賣超", "投信買賣超", "自營商買賣超"]
_VALUATION_COLS = ["日期", "代號", "名稱", "本益比", "股淨比", "殖利率%"]
_MARGIN_COLS = ["日期", "代號", "名稱", "融資今餘", "融資買進", "融資賣出",
                "融券今餘", "融券買進", "融券賣出", "資券互抵"]


def _today_str() -> str:
    return date.today().isoformat()


def _from_twse(code: str = None) -> pd.DataFrame:
    """今日全市場（或單一代號）三大法人 — 來源 TWSE rwd T86。"""
    df = query_twse_institutional_numeric()
    if df.empty:
        return pd.DataFrame(columns=_UNIFIED_COLS)
    if code:
        df = df[df["Code"] == str(code)]
    out = df.rename(columns={
        "Code": "代號",
        "Name": "名稱",
        "ForeignInvestmentNetBuySell": "外資買賣超",
        "InvestmentTrustNetBuySell": "投信買賣超",
        "DealerNetBuySell": "自營商買賣超",
    }).copy()
    out["日期"] = _today_str()
    return out[_UNIFIED_COLS]


def _from_finmind(code: str, start: str, end: str) -> pd.DataFrame:
    """歷史區間三大法人（逐股）— 來源 FinMind，長格式轉寬格式對齊統一欄位。"""
    df = query_institutional(code, start, end)
    if df.empty:
        return pd.DataFrame(columns=_UNIFIED_COLS)
    pivot = df.pivot_table(index="日期", columns="法人", values="買超", aggfunc="sum")
    out = pd.DataFrame(index=pivot.index)
    out["外資買賣超"] = pivot.get("外資", 0)
    out["投信買賣超"] = pivot.get("投信", 0)
    out["自營商買賣超"] = pivot.get("自營(自行)", 0) + pivot.get("自營(避險)", 0)
    out = out.reset_index()
    out["代號"] = str(code)
    out["名稱"] = ""
    return out[_UNIFIED_COLS]


def get_institutional(code: str = None, start: str = None, end: str = None) -> pd.DataFrame:
    """
    三大法人買賣超路由：
    - start/end 皆未指定，或指定區間就是今天 → TWSE 當日資料（code 可留空查全市場）
    - 指定歷史區間（start 早於今天，或 end 早於今天）→ FinMind（此時必須帶 code）

    回傳欄位：日期, 代號, 名稱, 外資買賣超, 投信買賣超, 自營商買賣超（原始股數）
    """
    today = _today_str()
    is_today_only = (start is None or start == today) and (end is None or end == today)

    if is_today_only:
        return _from_twse(code)

    if not code:
        raise ValueError("get_institutional()：查歷史區間必須指定 code（FinMind 僅支援逐股查詢）")
    return _from_finmind(code, start or (date.today() - timedelta(days=30)).isoformat(), end or today)


def _valuation_from_twse(code: str = None) -> pd.DataFrame:
    """今日全市場（或單一代號）估值 — 來源 TWSE BWIBBU_ALL。"""
    df = query_twse_bwibbu(code)
    if df.empty:
        return pd.DataFrame(columns=_VALUATION_COLS)
    out = df.copy()
    out["日期"] = _today_str()
    return out[_VALUATION_COLS]


def _valuation_from_finmind(code: str, start: str, end: str) -> pd.DataFrame:
    """歷史區間估值（逐股）— 來源 FinMind taiwan_stock_per_pbr。"""
    df = query_per_pbr(code, start, end)
    if df.empty:
        return pd.DataFrame(columns=_VALUATION_COLS)
    out = df.rename(columns={"本益比(PER)": "本益比", "股淨比(PBR)": "股淨比"}).copy()
    out["代號"] = str(code)
    out["名稱"] = ""
    return out[_VALUATION_COLS]


def get_valuation(code: str = None, start: str = None, end: str = None) -> pd.DataFrame:
    """
    本益比/股淨比/殖利率路由：
    - start/end 皆未指定，或指定區間就是今天 → TWSE BWIBBU_ALL（code 可留空查全市場）
    - 指定歷史區間 → FinMind（此時必須帶 code）

    回傳欄位：日期, 代號, 名稱, 本益比, 股淨比, 殖利率%
    """
    today = _today_str()
    is_today_only = (start is None or start == today) and (end is None or end == today)

    if is_today_only:
        return _valuation_from_twse(code)

    if not code:
        raise ValueError("get_valuation()：查歷史區間必須指定 code（FinMind 僅支援逐股查詢）")
    return _valuation_from_finmind(code, start or (date.today() - timedelta(days=60)).isoformat(), end or today)


_MARGIN_TWSE_RENAME = {
    "股票代號": "代號", "股票名稱": "名稱",
    "融資今日餘額": "融資今餘", "融資買進": "融資買進", "融資賣出": "融資賣出",
    "融券今日餘額": "融券今餘", "融券買進": "融券買進", "融券賣出": "融券賣出",
    "資券互抵": "資券互抵",
}
_MARGIN_NUMERIC_COLS = ["融資今餘", "融資買進", "融資賣出", "融券今餘", "融券買進", "融券賣出", "資券互抵"]


def _margin_from_twse(code: str = None) -> pd.DataFrame:
    """今日全市場（或單一代號）融資融券 — 來源 TWSE MI_MARGN。"""
    df = query_twse_margin()
    if df.empty:
        return pd.DataFrame(columns=_MARGIN_COLS)
    if code and "股票代號" in df.columns:
        df = df[df["股票代號"] == str(code)]
    keep = [c for c in _MARGIN_TWSE_RENAME if c in df.columns]
    out = df[keep].rename(columns=_MARGIN_TWSE_RENAME).copy()
    for col in _MARGIN_NUMERIC_COLS:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col].astype(str).str.replace(",", ""), errors="coerce").fillna(0)
    out["日期"] = _today_str()
    return out[[c for c in _MARGIN_COLS if c in out.columns]]


def _margin_from_finmind(code: str, start: str, end: str) -> pd.DataFrame:
    """歷史區間融資融券（逐股）— 來源 FinMind taiwan_stock_margin_purchase_short_sale。"""
    df = query_margin_short(code, start, end)
    if df.empty:
        return pd.DataFrame(columns=_MARGIN_COLS)
    out = df.copy()
    out["代號"] = str(code)
    out["名稱"] = ""
    return out[[c for c in _MARGIN_COLS if c in out.columns]]


def get_margin(code: str = None, start: str = None, end: str = None) -> pd.DataFrame:
    """
    融資融券路由：
    - start/end 皆未指定，或指定區間就是今天 → TWSE MI_MARGN（code 可留空查全市場）
    - 指定歷史區間 → FinMind（此時必須帶 code）

    回傳欄位：日期, 代號, 名稱, 融資今餘, 融資買進, 融資賣出, 融券今餘, 融券買進, 融券賣出, 資券互抵
    """
    today = _today_str()
    is_today_only = (start is None or start == today) and (end is None or end == today)

    if is_today_only:
        return _margin_from_twse(code)

    if not code:
        raise ValueError("get_margin()：查歷史區間必須指定 code（FinMind 僅支援逐股查詢）")
    return _margin_from_finmind(code, start or (date.today() - timedelta(days=30)).isoformat(), end or today)
