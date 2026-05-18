#!/usr/bin/env python3
"""
台股每日自動抓取 → 存入 Notion
每個交易日 18:00 由 GitHub Actions 觸發

GitHub Secrets 需設定：
  NOTION_TOKEN          — Notion Integration Token
  NOTION_MARKET_DB_ID   — 每日大盤快照 Database ID
  NOTION_SCREENER_DB_ID — 選股紀錄 Database ID
  FINMIND_TOKEN         — FinMind API Token（選填）
"""

import os
import sys
import time
import requests
import pandas as pd
from datetime import date

# ─── 環境變數 ───────────────────────────────────────────────
NOTION_TOKEN          = os.environ.get("NOTION_TOKEN", "")
NOTION_MARKET_DB_ID   = os.environ.get("NOTION_MARKET_DB_ID", "")
NOTION_SCREENER_DB_ID = os.environ.get("NOTION_SCREENER_DB_ID", "")
FINMIND_TOKEN         = os.environ.get("FINMIND_TOKEN", "")

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

TODAY = date.today().isoformat()
WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]


# ═══════════════════════════════════════════════════════════
# Notion 寫入工具
# ═══════════════════════════════════════════════════════════

def _title(v: str) -> dict:
    return {"title": [{"text": {"content": str(v)[:200]}}]}

def _text(v) -> dict:
    return {"rich_text": [{"text": {"content": str(v)[:2000]}}]}

def _num(v) -> dict:
    try:
        return {"number": round(float(v), 2)}
    except Exception:
        return {"number": None}

def _date_prop(d: str) -> dict:
    return {"date": {"start": d}}


def notion_insert(db_id: str, props: dict) -> bool:
    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers=NOTION_HEADERS,
        json={"parent": {"database_id": db_id}, "properties": props},
        timeout=15,
    )
    if resp.status_code not in (200, 201):
        print(f"  ⚠️  Notion 寫入失敗 {resp.status_code}: {resp.text[:150]}")
        return False
    return True


# ═══════════════════════════════════════════════════════════
# Step 1：抓取大盤資料
# ═══════════════════════════════════════════════════════════

def fetch_market() -> dict:
    data: dict = {}

    # ── 全市場行情 (STOCK_DAY_ALL) ──────────────────────────
    try:
        df = pd.DataFrame(
            requests.get(
                "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
                timeout=15,
            ).json()
        )
        for col in ["ClosingPrice", "Change", "TradeVolume", "TradeValue"]:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")
        stocks = df[df["Code"].str.len() == 4]
        data["up"]    = int((stocks["Change"] > 0).sum())
        data["down"]  = int((stocks["Change"] < 0).sum())
        data["value"] = round(stocks["TradeValue"].sum() / 1e8, 1)
        data["stock_df"] = df
        print(f"  上漲 {data['up']} 下跌 {data['down']} 成交 {data['value']:.0f} 億")
    except Exception as e:
        print(f"  ⚠️  STOCK_DAY_ALL: {e}")

    # ── 三大法人 (T86) ─────────────────────────────────────
    try:
        df = pd.DataFrame(
            requests.get("https://openapi.twse.com.tw/v1/fund/T86", timeout=15).json()
        )
        for col in ["ForeignInvestmentNetBuySell", "InvestmentTrustNetBuySell", "DealerNetBuySell"]:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")
        data["foreign"] = round(df["ForeignInvestmentNetBuySell"].sum() / 10000, 2)
        data["trust"]   = round(df["InvestmentTrustNetBuySell"].sum() / 10000, 2)
        data["dealer"]  = round(df["DealerNetBuySell"].sum() / 10000, 2)
        data["t86_df"]  = df
        print(f"  外資 {data['foreign']:+.2f} 投信 {data['trust']:+.2f} 自營 {data['dealer']:+.2f} 億股")
    except Exception as e:
        print(f"  ⚠️  T86: {e}")

    # ── 加權指數 (yfinance) ────────────────────────────────
    try:
        import yfinance as yf
        hist = yf.Ticker("^TWII").history(period="3d")
        if len(hist) >= 1:
            close = float(hist["Close"].iloc[-1])
            prev  = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else close
            chg   = close - prev
            pct   = chg / prev * 100 if prev else 0
            data["taiex"]     = round(close, 2)
            data["taiex_chg"] = round(chg, 2)
            data["taiex_pct"] = round(pct, 2)
            print(f"  加權指數 {close:.2f} ({chg:+.2f} / {pct:+.2f}%)")
    except Exception as e:
        print(f"  ⚠️  指數: {e}")

    return data


# ═══════════════════════════════════════════════════════════
# Step 2：寫入大盤快照
# ═══════════════════════════════════════════════════════════

def write_market(data: dict) -> bool:
    wd  = WEEKDAY_CN[date.today().weekday()]
    props = {
        "名稱": _title(f"{TODAY} (週{wd})"),
        "日期": _date_prop(TODAY),
    }
    for key, col in [
        ("taiex",     "加權指數"),
        ("taiex_chg", "漲跌點"),
        ("taiex_pct", "漲跌幅%"),
        ("up",        "上漲家數"),
        ("down",      "下跌家數"),
        ("value",     "成交金額(億)"),
        ("foreign",   "外資買賣超(億)"),
        ("trust",     "投信買賣超(億)"),
        ("dealer",    "自營商買賣超(億)"),
    ]:
        if key in data:
            props[col] = _num(data[key])

    ok = notion_insert(NOTION_MARKET_DB_ID, props)
    if ok:
        print("  ✅ 大盤快照已存入 Notion")
    return ok


# ═══════════════════════════════════════════════════════════
# Step 3：籌碼面選股（外資 + 投信雙買超）
# ═══════════════════════════════════════════════════════════

def run_screener(data: dict) -> pd.DataFrame:
    t86      = data.get("t86_df", pd.DataFrame())
    stock_df = data.get("stock_df", pd.DataFrame())
    if t86.empty:
        return pd.DataFrame()

    # 外資 + 投信同時買超，排除 ETF
    mask = (
        (t86["ForeignInvestmentNetBuySell"] > 0) &
        (t86["InvestmentTrustNetBuySell"] > 0) &
        (t86["Code"].str.len() == 4)
    )
    hits = t86[mask].copy()

    # 合併股價
    if not stock_df.empty:
        hits = hits.merge(
            stock_df[["Code", "ClosingPrice", "Change", "TradeVolume"]],
            on="Code", how="left",
        )

    # 合併估值 (BWIBBU)
    try:
        val = pd.DataFrame(
            requests.get(
                "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL",
                timeout=15,
            ).json()
        )
        for c in ["PEratio", "DividendYield", "PBratio"]:
            val[c] = pd.to_numeric(val[c], errors="coerce")
        hits = hits.merge(val[["Code", "PEratio", "DividendYield", "PBratio"]],
                          on="Code", how="left")
    except Exception:
        pass

    rows = []
    for _, r in hits.iterrows():
        close = float(r.get("ClosingPrice", 0) or 0)
        chg   = float(r.get("Change", 0) or 0)
        pct   = round(chg / (close - chg) * 100, 2) if (close - chg) > 0 else 0
        rows.append({
            "代號":          str(r["Code"]),
            "名稱":          str(r.get("Name", "")),
            "收盤價":        close,
            "漲跌幅%":       pct,
            "成交量(張)":    int(float(r.get("TradeVolume", 0) or 0) // 1000),
            "外資買賣超(張)": int(r["ForeignInvestmentNetBuySell"]),
            "投信買賣超(張)": int(r["InvestmentTrustNetBuySell"]),
            "本益比":        r.get("PEratio"),
            "殖利率%":       r.get("DividendYield"),
            "股淨比":        r.get("PBratio"),
            "符合條件":      "外資買超、投信買超",
        })

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════
# Step 4：寫入選股紀錄
# ═══════════════════════════════════════════════════════════

def write_screener(df: pd.DataFrame) -> int:
    count = 0
    for _, r in df.iterrows():
        props = {
            "股票":    _title(f"{r['代號']} {r['名稱']}"),
            "日期":    _date_prop(TODAY),
            "代號":    _text(r["代號"]),
            "名稱":    _text(r["名稱"]),
            "符合條件": _text(r["符合條件"]),
        }
        for field in ["收盤價", "漲跌幅%", "成交量(張)", "外資買賣超(張)",
                      "投信買賣超(張)", "本益比", "殖利率%", "股淨比"]:
            val = r.get(field)
            if val is not None and not (isinstance(val, float) and pd.isna(val)):
                props[field] = _num(val)

        if notion_insert(NOTION_SCREENER_DB_ID, props):
            count += 1
        time.sleep(0.4)   # Notion API: 3 req/s 上限

    return count


# ═══════════════════════════════════════════════════════════
# 主程式
# ═══════════════════════════════════════════════════════════

def main():
    print(f"\n{'='*52}")
    print(f"  台股每日自動抓取  {TODAY}")
    print(f"{'='*52}\n")

    if not NOTION_TOKEN:
        print("❌ NOTION_TOKEN 未設定，中止")
        sys.exit(1)

    print("📊 Step 1/4  抓取大盤資料...")
    data = fetch_market()

    print("\n💾 Step 2/4  寫入大盤快照...")
    write_market(data)

    print("\n🔍 Step 3/4  籌碼選股（外資＋投信雙買超）...")
    screener_df = run_screener(data)
    print(f"  符合條件：{len(screener_df)} 檔")
    if not screener_df.empty:
        print(screener_df[["代號", "名稱", "外資買賣超(張)", "投信買賣超(張)"]].to_string(index=False))

    print(f"\n💾 Step 4/4  寫入選股紀錄...")
    if not screener_df.empty:
        saved = write_screener(screener_df)
        print(f"  ✅ 已存入 {saved}/{len(screener_df)} 筆")
    else:
        print("  今日無符合選股條件的股票")

    print(f"\n✅ 完成  {TODAY}\n")


if __name__ == "__main__":
    main()
