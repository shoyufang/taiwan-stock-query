"""
新聞資料來源客戶端 — 負責個股與大盤即時新聞查詢。
使用 yfinance 免除帳號登入依賴。
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, timezone


def query_news(code: str = None, count: int = 10) -> pd.DataFrame:
    """
    查詢個股或大盤即時新聞（來源：Yahoo Finance）。
    code：台股代號，如 "2330"（會自動加 .TW）；不填則查台灣市場大盤新聞。
    count：顯示筆數（最多約 20 筆）。
    """
    if code:
        symbol = f"{code}.TW"
    else:
        symbol = "^TWII"  # 加權指數，代表大盤新聞

    ticker = yf.Ticker(symbol)
    news_list = ticker.news[:count]

    rows = []
    for item in news_list:
        c = item.get("content", {})
        pub = c.get("pubDate", "")
        # 轉換時間為台灣時間（UTC+8）
        if pub:
            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            dt_tw = dt.astimezone(timezone(timedelta(hours=8)))
            pub = dt_tw.strftime("%Y-%m-%d %H:%M")

        rows.append({
            "時間":   pub,
            "標題":   c.get("title", ""),
            "摘要":   c.get("summary", ""),
            "來源":   c.get("provider", {}).get("displayName", ""),
            "連結":   (c.get("clickThroughUrl") or c.get("canonicalUrl") or {}).get("url", ""),
        })

    return pd.DataFrame(rows)


def print_news(code: str = None, count: int = 10):
    """格式化輸出新聞（適合終端閱讀）"""
    label = f"{code}（{code}.TW）" if code else "台灣大盤（^TWII）"
    print(f"\n{'='*60}")
    print(f"  {label} 最新新聞")
    print(f"{'='*60}")

    df = query_news(code, count)
    if df.empty:
        print("查無新聞資料")
        return

    for i, row in df.iterrows():
        print(f"\n[{i+1}] {row['時間']}  {row['來源']}")
        print(f"    {row['標題']}")
        if row["摘要"]:
            print(f"    {row['摘要'][:80]}{'...' if len(row['摘要']) > 80 else ''}")
        print(f"    {row['連結']}")


def query_stock_news(code: str, limit: int = 10) -> pd.DataFrame:
    """查詢個股新聞別名（相容新版匯出介面）"""
    return query_news(code, limit)


def query_market_news(limit: int = 10) -> pd.DataFrame:
    """查詢大盤新聞別名（相容新版匯出介面）"""
    return query_news(None, limit)
