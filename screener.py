"""
選股引擎 — 技術面 / 財報面 / 籌碼面 / 多因子篩選
A: 技術面  (pandas_ta + yfinance 批量下載)
B: 財報面  (TWSE BWIBBU + FinMind 月營收)
C: 籌碼面  (TWSE T86 三大法人 + FinMind 連續買超)
D: 多因子  (漏斗式：技術→籌碼→財報)
"""

import os
import glob
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import streamlit as st
from datetime import date, timedelta
from typing import List, Dict, Optional, Tuple
import time
import warnings

from config import load_config

warnings.filterwarnings("ignore")

# ═══════════════════════════════════════════════════════════
# 1. 股票清單
# ═══════════════════════════════════════════════════════════

def _load_local_csv_fallback(category: str, max_days: int = 5) -> pd.DataFrame:
    """從 data/twse/{category}/ 尋找最近 max_days 天內最新的 YYYY-MM-DD.csv 檔案並讀取"""
    base_dir = os.path.join("data", "twse", category)
    if not os.path.isdir(base_dir):
        return pd.DataFrame()
    
    # 優先從今天開始往前找 5 天 (覆蓋週末與假日)
    today = date.today()
    for i in range(max_days):
        check_date = today - timedelta(days=i)
        file_path = os.path.join(base_dir, f"{check_date.isoformat()}.csv")
        if os.path.exists(file_path):
            try:
                df = pd.read_csv(file_path, dtype=str, encoding="utf-8-sig")
                if not df.empty:
                    return df
            except Exception:
                pass
                
    # 若無，則透過 glob 找該目錄下修改時間最新的一個 CSV 檔案 (終極安全 fallback)
    try:
        files = glob.glob(os.path.join(base_dir, "*.csv"))
        if files:
            latest_file = max(files, key=os.path.getmtime)
            df = pd.read_csv(latest_file, dtype=str, encoding="utf-8-sig")
            if not df.empty:
                return df
    except Exception:
        pass
        
    return pd.DataFrame()


def _process_universe_df(df: pd.DataFrame) -> pd.DataFrame:
    """統一處理上市行情 (STOCK_DAY_ALL) DataFrame 格式 (相容新舊 API 與 CSV)"""
    rename = {
        "Code": "代號", "Name": "名稱",
        "TradeVolume": "成交量", "ClosingPrice": "收盤", "Change": "漲跌",
        "證券代號": "代號", "證券名稱": "名稱",
        "成交股數": "成交量", "收盤價": "收盤", "漲跌價差": "漲跌",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    for col in ["成交量", "收盤", "漲跌"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")
    if "代號" in df.columns and "收盤" in df.columns:
        return df.dropna(subset=["代號", "收盤"])
    return pd.DataFrame()


def _process_valuation_df(df: pd.DataFrame) -> pd.DataFrame:
    """統一處理本益比估值 (BWIBBU_ALL) DataFrame 格式"""
    rename = {
        "Code": "代號", "Name": "名稱",
        "PEratio": "本益比", "DividendYield": "殖利率", "PBratio": "股淨比",
        "證券代號": "代號", "證券名稱": "名稱",
        "本益比": "本益比", "殖利率(%)": "殖利率", "股價淨值比": "股淨比",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    for col in ["本益比", "殖利率", "股淨比"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _process_institutional_df(df: pd.DataFrame) -> pd.DataFrame:
    """統一處理三大法人 (T86) DataFrame 格式 (相容 OpenAPI, RWD 與 CSV)"""
    rename = {
        # OpenAPI
        "Code": "代號",
        "ForeignInvestmentNetBuySell":  "外資買賣超",
        "InvestmentTrustNetBuySell":    "投信買賣超",
        "DealerNetBuySell":             "自營商買賣超",
        # RWD / 本地 CSV
        "證券代號": "代號",
        "證券名稱": "名稱",
        "外陸資買賣超股數(不含外資自營商)": "外資買賣超",
        "投信買賣超股數": "投信買賣超",
        "自營商買賣超股數": "自營商買賣超",
        "三大法人買賣超股數": "合計買賣超",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    for col in ["外資買賣超", "投信買賣超", "自營商買賣超"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")
            
    if "外資買賣超" in df.columns and "投信買賣超" in df.columns and "自營商買賣超" in df.columns:
        if "合計買賣超" not in df.columns:
            df["合計買賣超"] = df["外資買賣超"].fillna(0) + df["投信買賣超"].fillna(0) + df["自營商買賣超"].fillna(0)
        else:
            df["合計買賣超"] = pd.to_numeric(df["合計買賣超"].astype(str).str.replace(",", ""), errors="coerce")
            
    # 移除重複的名稱欄位以防止 merge 後產生 名稱_x / 名稱_y 導致 KeyError
    for col in ["名稱", "證券名稱", "Name"]:
        if col in df.columns:
            df = df.drop(columns=[col])

    return df


@st.cache_data(ttl=600, show_spinner=False)
def get_twse_universe() -> pd.DataFrame:
    """取得台灣上市股票清單及當日行情 (STOCK_DAY_ALL)"""
    # 1. 優先嘗試讀取今日的本地快取 CSV
    today_str = date.today().isoformat()
    local_path = os.path.join("data", "twse", "daily_all", f"{today_str}.csv")
    if os.path.exists(local_path):
        try:
            df = pd.read_csv(local_path, dtype=str, encoding="utf-8-sig")
            if not df.empty:
                df_p = _process_universe_df(df)
                if not df_p.empty:
                    return df_p
        except Exception:
            pass

    # 2. 若無今日快取，嘗試線上抓取
    try:
        resp = requests.get(
            "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
            timeout=15,
        )
        if resp.status_code == 200:
            df_p = _process_universe_df(pd.DataFrame(resp.json()))
            if not df_p.empty:
                return df_p
    except Exception:
        pass

    # 3. 終極 Fallback：尋找最近 5 天內最新的本地快取
    df_fallback = _load_local_csv_fallback("daily_all")
    if not df_fallback.empty:
        df_p = _process_universe_df(df_fallback)
        if not df_p.empty:
            return df_p

    return pd.DataFrame()


def filter_universe(
    df: pd.DataFrame,
    min_price: float = 10.0,
    max_price: float = 9999.0,
    min_vol: int = 1000,
    exclude_etf: bool = True,
    exclude_preferred: bool = True,
) -> pd.DataFrame:
    """基本股票清單過濾"""
    if df.empty:
        return df
    mask = (df["收盤"] >= min_price) & (df["收盤"] <= max_price) & (df["成交量"] >= min_vol)
    if exclude_etf:
        mask &= df["代號"].str.len() == 4
    if exclude_preferred:
        mask &= ~df["名稱"].str.contains("特", na=False)
    return df[mask].reset_index(drop=True)


# ═══════════════════════════════════════════════════════════
# 2. 歷史價格批量下載
# ═══════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_price_batch(codes: Tuple[str, ...], period: str = "6mo") -> Dict[str, pd.DataFrame]:
    """批量下載歷史日K (yfinance)；codes 必須為 tuple 以支援緩存"""
    if not codes:
        return {}

    tickers = [f"{c}.TW" for c in codes]
    result: Dict[str, pd.DataFrame] = {}

    try:
        raw = yf.download(tickers, period=period, auto_adjust=True, progress=False)
    except Exception:
        return {}

    def _extract(code: str) -> Optional[pd.DataFrame]:
        ticker = f"{code}.TW"
        try:
            if len(codes) == 1:
                df = raw.copy()
                df.columns = df.columns.str.lower()
            else:
                df = raw.xs(ticker, axis=1, level=1).copy()
                df.columns = df.columns.str.lower()
            df = df.dropna(subset=["close"])
            return df if len(df) >= 30 else None
        except Exception:
            return None

    for code in codes:
        df = _extract(code)
        if df is not None:
            result[code] = df

    return result


# ═══════════════════════════════════════════════════════════
# 3. 技術面
# ═══════════════════════════════════════════════════════════

TECH_CONDITIONS: Dict[str, str] = {
    "kd_golden":      "KD 黃金交叉（低檔）",
    "kd_death":       "KD 死亡交叉（高檔）",
    "kd_oversold":    "KD 超賣 K<20",
    "macd_golden":    "MACD 黃金交叉",
    "macd_positive":  "MACD 柱狀翻正",
    "macd_death":     "MACD 死亡交叉",
    "rsi_oversold":   "RSI 超賣 <30",
    "rsi_overbought": "RSI 超買 >70",
    "ma_bullish":     "均線多頭排列",
    "ma_bearish":     "均線空頭排列",
    "ma5_cross_ma20": "MA5 穿越 MA20",
    "bb_breakout":    "布林突破上軌",
    "bb_oversold":    "布林觸下軌",
    "vol_breakout":   "帶量突破 MA20",
    "vol_expand":     "成交量放大 >1.5x",
}


def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()

def _rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    gain = d.clip(lower=0).rolling(n).mean()
    loss = (-d.clip(upper=0)).rolling(n).mean()
    return 100 - 100 / (1 + gain / loss.replace(0, np.nan))

def _macd(s: pd.Series, fast=12, slow=26, sig=9):
    ef = s.ewm(span=fast, adjust=False).mean()
    es = s.ewm(span=slow, adjust=False).mean()
    line = ef - es
    signal = line.ewm(span=sig, adjust=False).mean()
    return line, line - signal, signal

def _stoch(h: pd.Series, l: pd.Series, c: pd.Series, k=9, d=3):
    lo = l.rolling(k).min()
    hi = h.rolling(k).max()
    k_line = 100 * (c - lo) / (hi - lo + 1e-9)
    return k_line, k_line.rolling(d).mean()

def _bbands(s: pd.Series, n=20, std=2):
    mid = s.rolling(n).mean()
    sigma = s.rolling(n).std()
    return mid + std * sigma, mid, mid - std * sigma


def _calc_and_check(
    df: pd.DataFrame,
    conds: List[str],
    mode: str = "OR",
) -> Tuple[bool, Dict[str, bool]]:
    """計算技術指標並逐條檢查，回傳 (是否通過, 各條件結果)"""
    if len(df) < 30:
        return False, {}

    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]

    ma5  = _sma(c, 5)
    ma10 = _sma(c, 10)
    ma20 = _sma(c, 20)
    ma60 = _sma(c, 60)

    k_line, d_line = _stoch(h, l, c)
    macd_line, macd_hist, macd_sig = _macd(c)
    rsi14 = _rsi(c, 14)
    bb_u, _, bb_l = _bbands(c)

    vol_ma5  = _sma(v, 5)
    vol_ma20 = _sma(v, 20)

    def last(s: pd.Series) -> float:
        try:
            return float(s.dropna().iloc[-1])
        except Exception:
            return float("nan")

    def prev(s: pd.Series) -> float:
        try:
            return float(s.dropna().iloc[-2])
        except Exception:
            return float("nan")

    def ok(fn) -> bool:
        try:
            return bool(fn())
        except Exception:
            return False

    checkers = {
        "kd_golden":      lambda: prev(k_line) < prev(d_line) and last(k_line) > last(d_line) and last(k_line) < 50,
        "kd_death":       lambda: prev(k_line) > prev(d_line) and last(k_line) < last(d_line) and last(k_line) > 50,
        "kd_oversold":    lambda: last(k_line) < 20,
        "macd_golden":    lambda: prev(macd_line) < prev(macd_sig) and last(macd_line) > last(macd_sig),
        "macd_positive":  lambda: prev(macd_hist) < 0 and last(macd_hist) > 0,
        "macd_death":     lambda: prev(macd_line) > prev(macd_sig) and last(macd_line) < last(macd_sig),
        "rsi_oversold":   lambda: last(rsi14) < 30,
        "rsi_overbought": lambda: last(rsi14) > 70,
        "ma_bullish":     lambda: last(ma5) > last(ma10) > last(ma20) > last(ma60),
        "ma_bearish":     lambda: last(ma5) < last(ma10) < last(ma20) < last(ma60),
        "ma5_cross_ma20": lambda: prev(ma5) < prev(ma20) and last(ma5) > last(ma20),
        "bb_breakout":    lambda: prev(c) < prev(bb_u) and last(c) > last(bb_u),
        "bb_oversold":    lambda: last(c) <= last(bb_l),
        "vol_breakout":   lambda: prev(c) < prev(ma20) and last(c) > last(ma20) and last(v) > last(vol_ma20) * 1.5,
        "vol_expand":     lambda: last(v) > last(vol_ma5) * 1.5,
    }

    detail = {cond: ok(checkers[cond]) for cond in conds if cond in checkers}
    passed = (all if mode == "AND" else any)(detail.values()) if detail else False
    return passed, detail


def screen_technical(
    universe_df: pd.DataFrame,
    conds: List[str],
    mode: str = "OR",
    period: str = "6mo",
    progress_bar=None,
    status_text=None,
) -> pd.DataFrame:
    """技術面選股主函式"""
    if not conds or universe_df.empty:
        return pd.DataFrame()

    if status_text:
        status_text.text("批量下載歷史K線中...")

    codes = tuple(universe_df["代號"].tolist())
    price_data = _fetch_price_batch(codes, period)

    rows = []
    total = len(price_data)
    for i, (code, df) in enumerate(price_data.items()):
        if progress_bar and total > 0:
            progress_bar.progress((i + 1) / total, text=f"分析 {code} ({i+1}/{total})")

        passed, detail = _calc_and_check(df, conds, mode)
        if not passed:
            continue

        base_rows = universe_df[universe_df["代號"] == code]
        if base_rows.empty:
            continue
        base = base_rows.iloc[0]

        row: Dict = {
            "代號": code,
            "名稱": base["名稱"],
            "收盤": base["收盤"],
            "成交量(張)": int(base["成交量"]),
        }
        for k, v in detail.items():
            row[TECH_CONDITIONS[k]] = "✅" if v else ""
        rows.append(row)

    if progress_bar:
        progress_bar.progress(1.0, text=f"技術面篩選完成，共 {len(rows)} 檔")

    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ═══════════════════════════════════════════════════════════
# 4. 財報面
# ═══════════════════════════════════════════════════════════

@st.cache_data(ttl=600, show_spinner=False)
def _get_twse_valuation() -> pd.DataFrame:
    """取得全市場本益比/股淨比/殖利率 (BWIBBU_ALL)"""
    # 1. 優先嘗試讀取今日的本地快取 CSV
    today_str = date.today().isoformat()
    local_path = os.path.join("data", "twse", "valuation", f"{today_str}.csv")
    if os.path.exists(local_path):
        try:
            df = pd.read_csv(local_path, dtype=str, encoding="utf-8-sig")
            if not df.empty:
                df_p = _process_valuation_df(df)
                if not df_p.empty:
                    return df_p
        except Exception:
            pass

    # 2. 若無今日快取，嘗試線上抓取
    try:
        resp = requests.get(
            "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL",
            timeout=15,
        )
        if resp.status_code == 200:
            df_p = _process_valuation_df(pd.DataFrame(resp.json()))
            if not df_p.empty:
                return df_p
    except Exception:
        pass

    # 3. 終極 Fallback：尋找最近 5 天內最新的本地快取
    df_fallback = _load_local_csv_fallback("valuation")
    if not df_fallback.empty:
        df_p = _process_valuation_df(df_fallback)
        if not df_p.empty:
            return df_p

    return pd.DataFrame()


def _get_finmind_rev(codes: List[str]) -> Dict[str, pd.DataFrame]:
    """批量取得 FinMind 月營收（小批次避免 rate limit）"""
    from config import get_secret
    token = get_secret("FINMIND_TOKEN")
    start = (date.today() - timedelta(days=450)).strftime("%Y-%m-%d")
    end   = date.today().strftime("%Y-%m-%d")

    result: Dict[str, pd.DataFrame] = {}
    for code in codes:
        try:
            resp = requests.get(
                "https://api.finmindtrade.com/api/v4/data",
                params={
                    "dataset": "TaiwanStockMonthRevenue",
                    "data_id": code,
                    "start_date": start,
                    "end_date": end,
                    "token": token,
                },
                timeout=10,
            )
            data = resp.json().get("data", [])
            if data:
                df = pd.DataFrame(data)
                df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce")
                result[code] = df.sort_values("date")
            time.sleep(0.25)
        except Exception:
            pass
    return result


def screen_fundamental(
    universe_df: pd.DataFrame,
    pe_max: Optional[float] = None,
    pb_max: Optional[float] = None,
    yield_min: Optional[float] = None,
    rev_yoy_min: Optional[float] = None,
    rev_cons_n: int = 0,
    progress_bar=None,
    status_text=None,
) -> pd.DataFrame:
    """財報面選股主函式"""
    if universe_df.empty:
        return pd.DataFrame()

    if status_text:
        status_text.text("取得本益比/股淨比/殖利率...")

    val_df = _get_twse_valuation()
    if val_df.empty:
        return pd.DataFrame()

    merged = universe_df.merge(
        val_df[["代號", "本益比", "殖利率", "股淨比"]],
        on="代號", how="left",
    )

    mask = pd.Series(True, index=merged.index)
    if pe_max is not None:
        mask &= (merged["本益比"] > 0) & (merged["本益比"] <= pe_max)
    if pb_max is not None:
        mask &= (merged["股淨比"] > 0) & (merged["股淨比"] <= pb_max)
    if yield_min is not None:
        mask &= merged["殖利率"] >= yield_min

    filtered = merged[mask].copy().reset_index(drop=True)

    # FinMind 月營收篩選（僅對已過濾的小集合查詢）
    if (rev_yoy_min is not None or rev_cons_n > 0) and not filtered.empty:
        codes = filtered["代號"].tolist()
        if status_text:
            status_text.text(f"取得月營收（{len(codes)} 檔）...")
        rev_data = _get_finmind_rev(codes)

        keep = []
        for i, row in filtered.iterrows():
            code = row["代號"]
            if code not in rev_data:
                continue
            df = rev_data[code]
            if len(df) < 14:
                continue

            df = df.copy()
            df["yoy"] = (df["revenue"] / df["revenue"].shift(12) - 1) * 100
            yoy_clean = df["yoy"].dropna()
            if yoy_clean.empty:
                continue

            last_yoy = float(yoy_clean.iloc[-1])

            if rev_yoy_min is not None and last_yoy < rev_yoy_min:
                continue
            if rev_cons_n > 0:
                recent = yoy_clean.tail(rev_cons_n)
                if len(recent) < rev_cons_n or not (recent > 0).all():
                    continue

            filtered.at[i, "月營收YOY%"] = round(last_yoy, 1)
            keep.append(i)

        filtered = filtered.loc[keep]

    if progress_bar:
        progress_bar.progress(1.0, text=f"財報面篩選完成，共 {len(filtered)} 檔")

    out = filtered.rename(columns={"成交量": "成交量(張)"}).reset_index(drop=True)
    return out if not out.empty else pd.DataFrame()


# ═══════════════════════════════════════════════════════════
# 5. 籌碼面
# ═══════════════════════════════════════════════════════════

CHIP_CONDITIONS: Dict[str, str] = {
    "foreign_buy": "外資今日買超",
    "trust_buy":   "投信今日買超",
    "dealer_buy":  "自營商今日買超",
    "total_buy":   "三大法人合計買超",
    "foreign_5d":  "外資連 5 日買超",
}


@st.cache_data(ttl=600, show_spinner=False)
def _get_twse_institutional() -> pd.DataFrame:
    """取得今日三大法人買賣超 (T86)"""
    # 1. 優先嘗試讀取今日的本地快取 CSV
    today_str = date.today().isoformat()
    local_path = os.path.join("data", "twse", "institutional", f"{today_str}.csv")
    if os.path.exists(local_path):
        try:
            df = pd.read_csv(local_path, dtype=str, encoding="utf-8-sig")
            if not df.empty:
                df_p = _process_institutional_df(df)
                if not df_p.empty:
                    return df_p
        except Exception:
            pass

    # 2. 若無今日快取，嘗試線上抓取 (改用可用且穩定的舊版 RWD API)
    try:
        twse_date_str = date.today().strftime("%Y%m%d")
        resp = requests.get(
            "https://www.twse.com.tw/rwd/zh/fund/T86",
            params={
                "response": "json",
                "date": twse_date_str,
                "selectType": "ALL"
            },
            timeout=15,
        )
        if resp.status_code == 200:
            raw = resp.json()
            if raw.get("stat") == "OK" and raw.get("data"):
                df = pd.DataFrame(raw["data"], columns=raw["fields"])
                df_p = _process_institutional_df(df)
                if not df_p.empty:
                    return df_p
    except Exception:
        pass

    # 3. 終極 Fallback：尋找最近 5 天內最新的本地快取
    df_fallback = _load_local_csv_fallback("institutional")
    if not df_fallback.empty:
        df_p = _process_institutional_df(df_fallback)
        if not df_p.empty:
            return df_p

    return pd.DataFrame()


def _get_finmind_inst_history(codes: List[str], days: int = 12) -> Dict[str, pd.DataFrame]:
    """取得 FinMind 三大法人歷史（用於連續買超判斷）"""
    from config import get_secret
    token = get_secret("FINMIND_TOKEN")
    start = (date.today() - timedelta(days=days + 7)).strftime("%Y-%m-%d")
    end   = date.today().strftime("%Y-%m-%d")

    result: Dict[str, pd.DataFrame] = {}
    for code in codes:
        try:
            resp = requests.get(
                "https://api.finmindtrade.com/api/v4/data",
                params={
                    "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
                    "data_id": code,
                    "start_date": start,
                    "end_date": end,
                    "token": token,
                },
                timeout=10,
            )
            data = resp.json().get("data", [])
            if data:
                result[code] = pd.DataFrame(data)
            time.sleep(0.25)
        except Exception:
            pass
    return result


def screen_chip(
    universe_df: pd.DataFrame,
    active_conds: List[str],
    mode: str = "OR",
    progress_bar=None,
    status_text=None,
) -> pd.DataFrame:
    """籌碼面選股主函式"""
    if not active_conds or universe_df.empty:
        return pd.DataFrame()

    if status_text:
        status_text.text("取得三大法人資料...")

    inst_df = _get_twse_institutional()
    merged = universe_df.merge(inst_df, on="代號", how="left") if not inst_df.empty else universe_df.copy()

    twse_cond_map = {
        "foreign_buy": "外資買賣超",
        "trust_buy":   "投信買賣超",
        "dealer_buy":  "自營商買賣超",
        "total_buy":   "合計買賣超",
    }

    rows = []
    for _, row in merged.iterrows():
        detail: Dict[str, bool] = {}
        for cond, col in twse_cond_map.items():
            if cond in active_conds:
                val = row.get(col, None)
                detail[cond] = float(val) > 0 if pd.notna(val) else False

        passed = (all if mode == "AND" else any)(detail.values()) if detail else False
        if not passed and mode == "AND":
            continue
        if not passed and mode == "OR" and "foreign_5d" not in active_conds:
            continue

        out: Dict = {
            "代號": row["代號"],
            "名稱": row["名稱"],
            "收盤": row["收盤"],
            "成交量(張)": int(row["成交量"]) if pd.notna(row["成交量"]) else 0,
        }
        for k, v in detail.items():
            out[CHIP_CONDITIONS[k]] = "✅" if v else ""

        for col in ["外資買賣超", "投信買賣超", "合計買賣超"]:
            if col in row and pd.notna(row[col]):
                out[f"{col}(千股)"] = int(row[col])

        out["_passed_twse"] = passed
        rows.append(out)

    # FinMind 連續外資買超
    if "foreign_5d" in active_conds and rows:
        codes = [r["代號"] for r in rows]
        if status_text:
            status_text.text(f"查詢外資連續買超歷史（{len(codes)} 檔）...")
        hist = _get_finmind_inst_history(codes)

        final_rows = []
        for r in rows:
            code = r["代號"]
            if code not in hist:
                r[CHIP_CONDITIONS["foreign_5d"]] = ""
                if mode == "AND":
                    continue
                if not r.get("_passed_twse", False):
                    continue
                final_rows.append(r)
                continue

            df_h = hist[code]
            name_col = next((c for c in ["name", "institutional_investors"] if c in df_h.columns), None)
            foreign_df = df_h[df_h[name_col].str.contains("Foreign_Investor", na=False)] if name_col else df_h

            consecutive = False
            if not foreign_df.empty and "buy" in foreign_df.columns and "sell" in foreign_df.columns:
                foreign_df = foreign_df.copy()
                foreign_df["net"] = (
                    pd.to_numeric(foreign_df["buy"], errors="coerce") -
                    pd.to_numeric(foreign_df["sell"], errors="coerce")
                )
                last5 = foreign_df["net"].tail(5)
                consecutive = len(last5) >= 5 and bool((last5 > 0).all())

            r[CHIP_CONDITIONS["foreign_5d"]] = "✅" if consecutive else ""

            if mode == "AND" and not consecutive:
                continue
            if mode == "OR" and not consecutive and not r.get("_passed_twse", False):
                continue

            final_rows.append(r)
        rows = final_rows

    # 清理內部欄位
    for r in rows:
        r.pop("_passed_twse", None)

    if progress_bar:
        progress_bar.progress(1.0, text=f"籌碼面篩選完成，共 {len(rows)} 檔")

    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ═══════════════════════════════════════════════════════════
# 6. 多因子組合（漏斗式）
# ═══════════════════════════════════════════════════════════

def screen_multi(
    universe_df: pd.DataFrame,
    tech_conds: List[str],
    tech_mode: str = "OR",
    chip_conds: List[str] = None,
    chip_mode: str = "OR",
    pe_max: Optional[float] = None,
    pb_max: Optional[float] = None,
    yield_min: Optional[float] = None,
    rev_yoy_min: Optional[float] = None,
    rev_cons_n: int = 0,
    progress_bar=None,
    status_text=None,
) -> pd.DataFrame:
    """
    多因子漏斗篩選：技術面 → 籌碼面 → 財報面
    每一步縮小候選池，最後合併欄位輸出。
    """
    if chip_conds is None:
        chip_conds = []

    remaining = universe_df.copy()
    tech_result = chip_result = fund_result = pd.DataFrame()

    # ── Step 1: 技術面 ──────────────────────────────────────
    if tech_conds:
        if status_text:
            status_text.text("步驟 1/3：技術面篩選...")
        tech_result = screen_technical(remaining, tech_conds, tech_mode,
                                       progress_bar=progress_bar, status_text=None)
        if not tech_result.empty:
            remaining = remaining[remaining["代號"].isin(tech_result["代號"])]

    # ── Step 2: 籌碼面 ──────────────────────────────────────
    if chip_conds and not remaining.empty:
        if status_text:
            status_text.text(f"步驟 2/3：籌碼面篩選（剩 {len(remaining)} 檔）...")
        chip_result = screen_chip(remaining, chip_conds, chip_mode,
                                  progress_bar=progress_bar, status_text=None)
        if not chip_result.empty:
            remaining = remaining[remaining["代號"].isin(chip_result["代號"])]

    # ── Step 3: 財報面 ──────────────────────────────────────
    any_fund = any(x is not None for x in [pe_max, pb_max, yield_min, rev_yoy_min]) or rev_cons_n > 0
    if any_fund and not remaining.empty:
        if status_text:
            status_text.text(f"步驟 3/3：財報面篩選（剩 {len(remaining)} 檔）...")
        fund_result = screen_fundamental(remaining, pe_max, pb_max, yield_min,
                                         rev_yoy_min, rev_cons_n,
                                         progress_bar=progress_bar, status_text=None)
        if not fund_result.empty:
            remaining = remaining[remaining["代號"].isin(fund_result["代號"])]

    if remaining.empty:
        return pd.DataFrame()

    # ── 合併輸出欄位 ─────────────────────────────────────────
    out = remaining[["代號", "名稱", "收盤", "成交量"]].copy()
    out = out.rename(columns={"成交量": "成交量(張)"})

    def _merge_extra(base: pd.DataFrame, extra: pd.DataFrame) -> pd.DataFrame:
        if extra.empty:
            return base
        extra_cols = [c for c in extra.columns if c not in base.columns]
        if not extra_cols:
            return base
        return base.merge(extra[["代號"] + extra_cols], on="代號", how="left")

    out = _merge_extra(out, tech_result)
    out = _merge_extra(out, chip_result)

    for col in ["本益比", "殖利率", "股淨比", "月營收YOY%"]:
        if not fund_result.empty and col in fund_result.columns:
            out = out.merge(fund_result[["代號", col]], on="代號", how="left")

    if progress_bar:
        progress_bar.progress(1.0, text=f"多因子篩選完成，共 {len(out)} 檔")

    return out.reset_index(drop=True)
