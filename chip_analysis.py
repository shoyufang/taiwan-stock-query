"""
Phase I: 籌碼深化 — 法人連買天數計算

讀取 data/twse/institutional/*.csv（NAS daily_job 每日累積），
計算每檔股票被外資/投信連續買超天數與累計張數。

降級策略：若本地日檔 < min_days，UI 顯示「籌碼資料累積中」提示。
"""
import os
from pathlib import Path
from typing import Optional

import pandas as pd
from logging_config import main_logger


def _get_institutional_files() -> list:
    """取得 data/twse/institutional/*.csv 檔案路徑（由新到舊排序）"""
    dirs = [
        Path("data/twse/institutional"),
        Path("/volume1/docker/sinopac/data/twse/institutional"),
    ]
    for d in dirs:
        if d.is_dir() and list(d.glob("*.csv")):
            return sorted(d.glob("*.csv"), reverse=True)
    return []


def load_institutional_history(days: int = 20) -> pd.DataFrame:
    """
    讀取最近 N 個日的三大法人 CSV，合併為單一 DataFrame。
    回傳：[日期, 代號, 名稱, 外資買賣超, 投信買賣超, 自營商買賣超, 合計]
    單位：張
    """
    files = _get_institutional_files()
    if not files:
        return pd.DataFrame()

    frames = []
    for f in files[:days]:
        try:
            df = pd.read_csv(f, encoding="utf-8-sig")
            if df.empty:
                continue
            frames.append(df)
        except Exception as e:
            main_logger.debug(f"chip_analysis: 跳過 {f.name}: {e}")

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    return combined


def consecutive_buy_ranking(
    who: str = "外資",
    min_days: int = 3,
    limit: int = 30,
) -> pd.DataFrame:
    """
    計算每檔股票連續買超天數排行。

    who: "外資" 或 "投信"
    min_days: 最少連續天數門檻
    limit: 回傳前 N 筆

    回傳：[代號, 名稱, 連買天數, 累計買賣超, 最近交易日]
    """
    df = load_institutional_history(30)
    if df.empty:
        return pd.DataFrame()

    # 確定欄位位置（TWSE T86 API 回傳 Big5 編碼，欄位名亂碼）
    # 位置：0=代號, 1=名稱, 2=外資買超, 3=外資賣超, 4=外資超,
    #       5=投信買超, 6=投信賣超, 7=投信超
    col_idx_map = {
        "外資": (4, 2),  # (超欄位, 買欄位) — 用超欄位即可
        "投信": (7, 5),
    }

    if who not in col_idx_map:
        return pd.DataFrame()

    super_col, buy_col = col_idx_map[who]
    code_col = 0
    name_col = 1

    if len(df.columns) <= max(super_col, buy_col, code_col, name_col):
        main_logger.warning(f"chip_analysis: 欄位不足（只有{len(df.columns)}列）")
        return pd.DataFrame()

    # 提取需要的欄位
    result = pd.DataFrame()
    result["代號"] = df.iloc[:, code_col].astype(str).str.strip()
    result["名稱"] = df.iloc[:, name_col].astype(str).str.strip()
    result["買賣超"] = pd.to_numeric(df.iloc[:, super_col], errors="coerce")

    # 按代號分組，計算連續買超天數
    stats = []
    for code, grp in result.groupby("代號"):
        grp = grp.sort_index()  # 確保由舊到新
        streak = 0
        max_streak = 0
        total_buy = 0
        last_date = None
        for i, row in grp.iterrows():
            val = row["買賣超"]
            if pd.notna(val) and val > 0:
                streak += 1
                total_buy += val
                max_streak = max(max_streak, streak)
                last_date = i
            else:
                streak = 0

        if max_streak >= min_days:
            stats.append({
                "代號": code,
                "名稱": grp.iloc[0]["名稱"],
                "連買天數": max_streak,
                "累計買賣超": total_buy,
                "最近交易日": str(last_date) if last_date else "",
            })

    if not stats:
        return pd.DataFrame()

    out = pd.DataFrame(stats)
    out = out.sort_values("連買天數", ascending=False).head(limit).reset_index(drop=True)
    return out


def consecutive_sell_ranking(
    who: str = "外資",
    min_days: int = 3,
    limit: int = 30,
) -> pd.DataFrame:
    """連續賣超排行（正面向負面翻轉）"""
    df = load_institutional_history(30)
    if df.empty:
        return pd.DataFrame()

    col_idx_map = {
        "外資": 4,
        "投信": 7,
    }

    if who not in col_idx_map:
        return pd.DataFrame()

    super_col = col_idx_map[who]
    code_col = 0
    name_col = 1

    if len(df.columns) <= max(super_col, code_col, name_col):
        return pd.DataFrame()

    result = pd.DataFrame()
    result["代號"] = df.iloc[:, code_col].astype(str).str.strip()
    result["名稱"] = df.iloc[:, name_col].astype(str).str.strip()
    result["買賣超"] = pd.to_numeric(df.iloc[:, super_col], errors="coerce")

    stats = []
    for code, grp in result.groupby("代號"):
        grp = grp.sort_index()
        streak = 0
        max_streak = 0
        total_sell = 0
        for i, row in grp.iterrows():
            val = row["買賣超"]
            if pd.notna(val) and val < 0:
                streak += 1
                total_sell += abs(val)
                max_streak = max(max_streak, streak)
            else:
                streak = 0

        if max_streak >= min_days:
            stats.append({
                "代號": code,
                "名稱": grp.iloc[0]["名稱"],
                "連賣天數": max_streak,
                "累計賣超": total_sell,
            })

    if not stats:
        return pd.DataFrame()

    out = pd.DataFrame(stats)
    out = out.sort_values("連賣天數", ascending=False).head(limit).reset_index(drop=True)
    return out


def dual_buy_ranking(min_days: int = 3, limit: int = 30) -> pd.DataFrame:
    """
    外資 + 投信雙買超排行（兩者都連續買超 ≥ min_days）。
    這是 daily_job 雙買超邏輯的 UI 版。
    """
    foreign = consecutive_buy_ranking("外資", min_days, limit * 2)
    trust = consecutive_buy_ranking("投信", min_days, limit * 2)

    if foreign.empty or trust.empty:
        return pd.DataFrame()

    # 取交集
    foreign_codes = set(foreign["代號"])
    trust_codes = set(trust["代號"])
    common = foreign_codes & trust_codes

    if not common:
        return pd.DataFrame()

    rows = []
    for code in common:
        f_row = foreign[foreign["代號"] == code].iloc[0]
        t_row = trust[trust["代號"] == code].iloc[0]
        rows.append({
            "代號": code,
            "名稱": f_row["名稱"],
            "外資連買": int(f_row["連買天數"]),
            "外資累計": int(f_row["累計買賣超"]),
            "投信連買": int(t_row["連買天數"]),
            "投信累計": int(t_row["累計買賣超"]),
        })

    if not rows:
        return pd.DataFrame()

    out = pd.DataFrame(rows)
    out = out.sort_values("外資連買", ascending=False).head(limit).reset_index(drop=True)
    return out


def get_individual_chip_summary(code: str) -> dict:
    """
    個股籌碼摘要：外資連買 N 天、投信連買 N 天、近 20 日外資累計。
    用於個股全景籌碼分頁頂部的摘要磚。
    """
    df = load_institutional_history(20)
    if df.empty:
        return {"error": "籌碼資料不足"}

    code_col = 0
    name_col = 1
    foreign_super_col = 4  # 外資超
    trust_super_col = 7    # 投信超

    if len(df.columns) <= max(name_col, foreign_super_col, trust_super_col):
        return {"error": "欄位不足"}

    code_str = str(code).strip().zfill(4)
    stock_df = df[df.iloc[:, code_col].astype(str).str.strip() == code_str]

    if stock_df.empty:
        return {"error": "查無此股"}

    # 計算連買天數
    def calc_streak(col_idx):
        vals = pd.to_numeric(stock_df.iloc[:, col_idx], errors="coerce")
        streak = 0
        max_streak = 0
        for v in vals:
            if pd.notna(v) and v > 0:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0
        return max_streak

    foreign_streak = calc_streak(foreign_super_col)
    trust_streak = calc_streak(trust_super_col)

    # 近 N 日累計
    foreign_vals = pd.to_numeric(stock_df.iloc[:, foreign_super_col], errors="coerce")
    trust_vals = pd.to_numeric(stock_df.iloc[:, trust_super_col], errors="coerce")
    foreign_cum = foreign_vals.sum()
    trust_cum = trust_vals.sum()

    return {
        "代號": code_str,
        "名稱": str(stock_df.iloc[0, name_col]).strip(),
        "外資連買": foreign_streak,
        "外資累計": int(foreign_cum),
        "投信連買": trust_streak,
        "投信累計": int(trust_cum),
    }
