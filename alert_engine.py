"""
Phase K: 自選股警示系統

警示規則結構：
  {"code": "2330", "type": "price_above", "value": 1100, "enabled": true}

類型：
  price_above / price_below / pct_move / ma20_break

檢查流程：
  1. 讀 alerts.json
  2. 讀當日收盤資料（data/twse/daily_all 快取，不重打 API）
  3. 逐條評估，回傳觸發清單
"""
from pathlib import Path
from datetime import date, timedelta

import pandas as pd
from loguru import logger

from config import load_alerts, load_watchlist


def _load_today_closing() -> pd.DataFrame:
    """
    讀取當日收盤資料（優先本地快取，避免打 API）。
    回傳：[代號, 收盤價, 漲跌幅%]
    """
    # 優先讀本地 TWSE daily_all
    for day_offset in range(5):  # 往前找最多 5 天
        d = date.today() - timedelta(days=day_offset)
        csv_path = Path(f"data/twse/daily_all/{d.strftime('%Y-%m-%d')}.csv")
        if not csv_path.exists():
            csv_path = Path(f"data/twse/daily_all/{d.strftime('%Y%m%d')}.csv")
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path, dtype=str, encoding="utf-8-sig")
                if not df.empty:
                    return df
            except Exception:
                continue
    return pd.DataFrame()


def _find_price_col(df: pd.DataFrame) -> str:
    """找出收盤價欄位名"""
    for col in df.columns:
        cl = col.lower()
        if "close" in cl or "收盤" in col:
            return col
    # 嘗試位置：通常第 8-9 欄
    if len(df.columns) > 8:
        return df.columns[8]
    return ""


def _find_pct_col(df: pd.DataFrame) -> str:
    """找出漲跌幅欄位名"""
    for col in df.columns:
        cl = col.lower()
        if "change" in cl or "漲跌" in cl or "pct" in cl:
            return col
    return ""


def check_alerts() -> list:
    """
    檢查所有警示規則，回傳觸發清單。
    回傳：[{"code", "name", "type", "value", "current", "triggered_at", "message"}]
    """
    alerts = load_alerts()
    if not alerts:
        return []

    today_df = _load_today_closing()
    if today_df.empty:
        logger.warning("alert_engine: 無當日收盤資料，跳過警示檢查")
        return []

    price_col = _find_price_col(today_df)
    pct_col = _find_pct_col(today_df)

    if not price_col:
        logger.warning("alert_engine: 找不到收盤價欄位")
        return []

    # 建立代號 → 行情 的字典
    code_col = ""
    for col in today_df.columns:
        cl = col.lower()
        if "code" in cl or "代號" in col or "stock" in cl:
            code_col = col
            break
    if not code_col and len(today_df.columns) > 0:
        code_col = today_df.columns[0]

    closing_map = {}
    for _, row in today_df.iterrows():
        code = str(row[code_col]).strip().zfill(4) if code_col else ""
        try:
            price = float(row[price_col])
        except (ValueError, TypeError):
            continue
        closing_map[code] = {
            "price": price,
            "pct": float(row[pct_col]) if pct_col and pct_col in row.index else None,
        }

    triggered = []
    for rule in alerts:
        if not rule.get("enabled", True):
            continue

        code = str(rule.get("code", "")).strip().zfill(4)
        rule_type = rule.get("type", "")
        value = rule.get("value", 0)

        if code not in closing_map:
            continue

        info = closing_map[code]
        current_price = info["price"]
        current_pct = info["pct"]

        triggered_rule = None

        if rule_type == "price_above":
            if current_price >= value:
                triggered_rule = {
                    "code": code,
                    "type": rule_type,
                    "value": value,
                    "current": current_price,
                    "message": f"價格突破 {value:,.0f} 元（現價 {current_price:,.0f}）",
                }

        elif rule_type == "price_below":
            if current_price <= value:
                triggered_rule = {
                    "code": code,
                    "type": rule_type,
                    "value": value,
                    "current": current_price,
                    "message": f"價格跌破 {value:,.0f} 元（現價 {current_price:,.0f}）",
                }

        elif rule_type == "pct_move":
            if current_pct is not None and abs(current_pct) >= value:
                direction = "上漲" if current_pct > 0 else "下跌"
                triggered_rule = {
                    "code": code,
                    "type": rule_type,
                    "value": value,
                    "current": round(current_pct, 2),
                    "message": f"單日{direction} {current_pct:+.2f}%（門檻 {value}%）",
                }

        if triggered_rule:
            triggered_rule["name"] = rule.get("name", code)
            triggered.append(triggered_rule)

    return triggered


def check_alerts_intraday(watchlist: list = None) -> list:
    """
    盤中即時檢查（讀 watchlist + 今日快照）。
    用於自選股頁面的視覺高亮。
    """
    if watchlist is None:
        wl = load_watchlist()
        watchlist = wl.get("stocks", [])

    alerts = load_alerts()
    if not alerts:
        return {}

    # 回傳 {code: [triggered_rules]}
    triggered_map = {}

    # 需要即時報價 → 用 Shioaji snapshot 或 cached data
    # 簡化版：回傳 alerts 清單供前端自行判斷
    triggered_map["_alerts"] = [
        {
            "code": str(a.get("code")),
            "type": a.get("type"),
            "value": a.get("value"),
        }
        for a in alerts if a.get("enabled", True)
    ]

    return triggered_map
