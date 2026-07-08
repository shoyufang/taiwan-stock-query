"""
資料路由層（R4）— 同一資料主題、多個來源，呼叫端不必知道來源差異。

目前只實作 get_institutional()（三大法人買賣超）；K線/估值/融資融券路由
留待後續 session 擴充（見 docs/plans/REDESIGN_PLAN_2026-07.md R4）。

統一欄位（原始股數，不做張/億轉換，轉換交給呼叫端依用途決定）：
    日期, 代號, 名稱, 外資買賣超, 投信買賣超, 自營商買賣超
"""

from datetime import date, timedelta
import pandas as pd

from datasources.twse_client import query_twse_institutional_numeric
from datasources.finmind_client import query_institutional
from logging_config import main_logger

_UNIFIED_COLS = ["日期", "代號", "名稱", "外資買賣超", "投信買賣超", "自營商買賣超"]


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
