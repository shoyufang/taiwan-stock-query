#!/usr/bin/env python3
"""
台股歷史資料回填（本地執行，勿放入 GitHub Actions）

執行方式：
  python backfill.py

產出：
  data/market/YYYY-MM-DD.csv    大盤摘要（TAIEX + 三大法人合計）
  data/screener/YYYY-MM-DD.csv  外資＋投信雙買超選股清單

說明：
  - 已存在的日期自動跳過，中斷後可重跑
  - 處置股清單無歷史 API，不回填
  - 完成後執行 git add data/ && git commit && git push 上傳
"""

import os
import sys
import time
import requests
import urllib3
import pandas as pd
from datetime import date

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ─── 設定 ───────────────────────────────────────────────────
START_DATE = "2021-01-01"          # 近 5 年起點
END_DATE   = date.today().isoformat()
SLEEP_SEC  = 0.8                   # 每次 TWSE API 呼叫間隔（限速用）


# ═══════════════════════════════════════════════════════════
# 工具函式
# ═══════════════════════════════════════════════════════════

def save_csv(df: pd.DataFrame, category: str, date_str: str) -> None:
    path = os.path.join("data", category)
    os.makedirs(path, exist_ok=True)
    df.to_csv(os.path.join(path, f"{date_str}.csv"),
              index=False, encoding="utf-8-sig")


def already_done(category: str, date_str: str) -> bool:
    return os.path.exists(os.path.join("data", category, f"{date_str}.csv"))


# ═══════════════════════════════════════════════════════════
# Step 1：下載 TAIEX 歷史（yfinance，一次全取）
# ═══════════════════════════════════════════════════════════

def get_taiex_history() -> dict:
    """回傳 {date: {taiex, taiex_chg, taiex_pct}} 字典"""
    import yfinance as yf
    hist = yf.Ticker("^TWII").history(start=START_DATE, end=END_DATE)
    hist.index = pd.to_datetime(hist.index).tz_localize(None)
    hist["Change"] = hist["Close"].diff()
    hist["Pct"]    = hist["Close"].pct_change() * 100

    result = {}
    for ts, row in hist.iterrows():
        d = ts.date()
        result[d] = {
            "taiex":     round(float(row["Close"]), 2),
            "taiex_chg": None if pd.isna(row["Change"]) else round(float(row["Change"]), 2),
            "taiex_pct": None if pd.isna(row["Pct"])    else round(float(row["Pct"]), 2),
        }
    return result


# ═══════════════════════════════════════════════════════════
# Step 2：TWSE 歷史 T86（逐日）
# ═══════════════════════════════════════════════════════════

def fetch_t86(date_str: str) -> pd.DataFrame:
    """抓取指定日期的三大法人每股明細（舊版 TWSE API）"""
    d = date_str.replace("-", "")
    try:
        resp = requests.get(
            "https://www.twse.com.tw/rwd/zh/fund/T86",
            params={"response": "json", "date": d, "selectType": "ALLBUT0999"},
            timeout=20,
            verify=False,
        )
        j = resp.json()
        if j.get("stat") != "OK" or not j.get("data"):
            return pd.DataFrame()
        df = pd.DataFrame(j["data"], columns=j["fields"])
        # 移除千分位逗號、前後空白
        for col in df.columns:
            df[col] = df[col].astype(str).str.replace(",", "").str.strip()
        return df
    except Exception as e:
        print(f"\n  ⚠️  T86 {date_str}: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════
# Step 3：處理單一交易日
# ═══════════════════════════════════════════════════════════

def process_day(day: date, taiex_data: dict, t86: pd.DataFrame) -> None:
    date_str = day.isoformat()

    # ── 大盤快照 ─────────────────────────────────────────
    if not already_done("market", date_str):
        row = {"date": date_str}

        # TAIEX
        if day in taiex_data:
            row.update(taiex_data[day])

        # 三大法人合計（億股）
        if not t86.empty:
            f_col = next((c for c in t86.columns if "外資" in c and "買賣超" in c and "自營" not in c), None)
            t_col = next((c for c in t86.columns if "投信" in c and "買賣超" in c), None)
            d_col = next((c for c in t86.columns if "自營" in c and "買賣超" in c and "避險" not in c), None)
            for key, col in [("foreign", f_col), ("trust", t_col), ("dealer", d_col)]:
                if col:
                    vals = pd.to_numeric(t86[col], errors="coerce")
                    row[key] = round(float(vals.sum()) / 10000, 2)

        save_csv(pd.DataFrame([row]), "market", date_str)

    # ── 選股紀錄 ─────────────────────────────────────────
    if not already_done("screener", date_str) and not t86.empty:
        code_col = next((c for c in t86.columns if "代號" in c), None)
        name_col = next((c for c in t86.columns if "名稱" in c), None)
        f_col    = next((c for c in t86.columns if "外資" in c and "買賣超" in c and "自營" not in c), None)
        t_col    = next((c for c in t86.columns if "投信" in c and "買賣超" in c), None)

        if code_col and f_col and t_col:
            t86[f_col] = pd.to_numeric(t86[f_col], errors="coerce")
            t86[t_col] = pd.to_numeric(t86[t_col], errors="coerce")

            mask = (
                (t86[f_col] > 0) &
                (t86[t_col] > 0) &
                (t86[code_col].astype(str).str.len() == 4)   # 排除 ETF
            )
            hits = t86[mask].copy()
            if not hits.empty:
                hits.insert(0, "date", date_str)
                save_csv(hits, "screener", date_str)


# ═══════════════════════════════════════════════════════════
# 主程式
# ═══════════════════════════════════════════════════════════

def main():
    print(f"\n{'='*54}")
    print(f"  台股歷史資料回填  {START_DATE} ～ {END_DATE}")
    print(f"{'='*54}\n")

    # --- 一次下載所有 TAIEX 歷史 ---
    print("📈 Step 1  下載加權指數歷史（yfinance）...")
    try:
        taiex_data = get_taiex_history()
    except Exception as e:
        print(f"  ⚠️  yfinance 失敗: {e}，繼續（TAIEX 欄位將為空）")
        taiex_data = {}

    trading_days = sorted(taiex_data.keys())
    print(f"  共 {len(trading_days)} 個交易日（{trading_days[0]} ～ {trading_days[-1]}）\n")

    # --- 逐日回填 ---
    print("📥 Step 2  逐日抓取 TWSE T86 歷史...")

    try:
        from tqdm import tqdm
        iterator = tqdm(trading_days, desc="回填進度", unit="日")
    except ImportError:
        iterator = trading_days
        print("  （安裝 tqdm 可顯示進度條：pip install tqdm）\n")

    for i, day in enumerate(iterator):
        date_str = day.isoformat()

        # 兩個類別都已存在 → 跳過
        if already_done("market", date_str) and already_done("screener", date_str):
            continue

        t86 = fetch_t86(date_str)
        process_day(day, taiex_data, t86)
        time.sleep(SLEEP_SEC)

        # 每 50 天顯示一次進度（沒有 tqdm 時）
        if not hasattr(iterator, "update") and (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(trading_days)}] 已處理至 {date_str}")

    # --- 統計結果 ---
    m_count = len(os.listdir("data/market"))   if os.path.exists("data/market")   else 0
    s_count = len(os.listdir("data/screener")) if os.path.exists("data/screener") else 0

    print(f"\n{'='*54}")
    print(f"  ✅ 回填完成！")
    print(f"  大盤快照  data/market/    {m_count} 個檔案")
    print(f"  選股紀錄  data/screener/  {s_count} 個檔案（有雙買超的交易日）")
    print(f"{'='*54}")
    print("\n📤 上傳到 GitHub：")
    print("  git add data/")
    print('  git commit -m "data: 5年歷史資料回填"')
    print("  git push\n")


if __name__ == "__main__":
    main()
