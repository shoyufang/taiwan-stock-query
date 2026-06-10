"""
港美股 Futu 資料來源客戶端 — 負責全球市場開收盤狀態、個股K線、基本面、成分股與板塊資訊查詢。
使用 yfinance 替代 FutuOpenD 以免除本機軟體依賴。
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, date


def _futu_to_yf(code: str) -> str:
    """
    將富途代號格式轉換為 yfinance 格式。
    HK.00700 → 0700.HK，US.AAPL → AAPL，其他原樣回傳。
    """
    if code.upper().startswith("HK."):
        return code[3:] + ".HK"
    if code.upper().startswith("US."):
        return code[3:]
    return code


def query_futu_market_state() -> pd.DataFrame:
    """全球主要市場開收盤狀態（時區計算，不需 FutuOpenD）"""
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from pytz import timezone as ZoneInfo

    now_utc = datetime.now(tz=ZoneInfo("UTC"))

    markets = [
        {"市場": "market_hk", "名稱": "香港",   "tz": "Asia/Hong_Kong",   "sessions": [("09:30", "12:00"), ("13:00", "16:00")]},
        {"市場": "market_us", "名稱": "美國",   "tz": "America/New_York", "sessions": [("09:30", "16:00")]},
        {"市場": "market_sh", "名稱": "上海",   "tz": "Asia/Shanghai",    "sessions": [("09:30", "11:30"), ("13:00", "15:00")]},
        {"市場": "market_sz", "名稱": "深圳",   "tz": "Asia/Shanghai",    "sessions": [("09:30", "11:30"), ("13:00", "15:00")]},
        {"市場": "market_tw", "名稱": "台灣",   "tz": "Asia/Taipei",      "sessions": [("09:00", "13:30")]},
        {"市場": "market_jp", "名稱": "日本",   "tz": "Asia/Tokyo",       "sessions": [("09:00", "11:30"), ("12:30", "15:30")]},
    ]

    rows = []
    for m in markets:
        local = now_utc.astimezone(ZoneInfo(m["tz"]))
        is_weekday = local.weekday() < 5
        t = local.strftime("%H:%M")
        is_open = is_weekday and any(o <= t <= c for o, c in m["sessions"])
        rows.append({
            "市場":     m["市場"],
            "名稱":     m["名稱"],
            "狀態":     "🟢 交易中" if is_open else "🔴 已收盤",
            "本地時間": local.strftime("%Y-%m-%d %H:%M"),
            "時區":     m["tz"],
        })
    return pd.DataFrame(rows)


def query_futu_kbar(code: str, start: str, end: str = None) -> pd.DataFrame:
    """港/美股日K線（yfinance）。code："HK.00700"或"US.AAPL"或直接用yfinance格式"""
    symbol = _futu_to_yf(code)
    if end is None:
        end = str(date.today())
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start, end=end, auto_adjust=True)
    if df.empty:
        return pd.DataFrame()
    df.index = pd.to_datetime(df.index).strftime("%Y-%m-%d")
    df = df.rename(columns={
        "Open": "開盤", "High": "最高", "Low": "最低",
        "Close": "收盤", "Volume": "成交量",
    })
    df["代號"] = symbol
    cols = ["代號", "開盤", "最高", "最低", "收盤", "成交量"]
    return df[[c for c in cols if c in df.columns]].reset_index().rename(columns={"index": "日期", "Date": "日期"})


def query_futu_basicinfo(market: str = "HK", codes: list = None) -> pd.DataFrame:
    """港/美股基本資訊（yfinance）。codes：["HK.00700","US.AAPL"]"""
    if not codes:
        return pd.DataFrame({"提示": ["請輸入股票代號"]})
    rows = []
    for code in codes:
        symbol = _futu_to_yf(code)
        try:
            info = yf.Ticker(symbol).info
            rows.append({
                "代號":     code,
                "yf代號":   symbol,
                "名稱":     info.get("longName") or info.get("shortName", "N/A"),
                "市場":     info.get("exchange", market),
                "幣別":     info.get("currency", "N/A"),
                "股價":     info.get("currentPrice") or info.get("regularMarketPrice", "N/A"),
                "市值":     info.get("marketCap", "N/A"),
                "本益比":   info.get("trailingPE", "N/A"),
                "板塊":     info.get("sector", "N/A"),
                "產業":     info.get("industry", "N/A"),
                "員工數":   info.get("fullTimeEmployees", "N/A"),
            })
        except Exception as e:
            rows.append({"代號": code, "名稱": f"查詢失敗: {e}"})
    return pd.DataFrame(rows)


def query_futu_capital_distribution(code: str) -> pd.DataFrame:
    """資金分布（大/中/小戶）— 此功能需 FutuOpenD，目前不支援"""
    return pd.DataFrame({"說明": [
        "⚠️ 資金分布功能需要 FutuOpenD 才能使用。",
        "可改用 DeepSeek AI 頁面詢問相關籌碼資訊，",
        "或參考 FinMind → 外資持股 / 融資融券 等替代數據。"
    ]})


def query_futu_capital_flow(code: str) -> pd.DataFrame:
    """資金流向（分鐘級）— 此功能需 FutuOpenD，目前不支援"""
    return pd.DataFrame({"說明": [
        "⚠️ 資金流向功能需要 FutuOpenD 才能使用。",
        "可改用 DeepSeek AI 頁面詢問相關資訊。"
    ]})


# 主要市場 ETF / 指數板塊清單（取代 Futu 板塊列表）
_PLATES_HK = [
    {"板塊代號": "^HSI",    "板塊名稱": "恒生指數",       "市場": "HK"},
    {"板塊代號": "^HSCE",   "板塊名稱": "H股指數",         "市場": "HK"},
    {"板塊代號": "2800.HK", "板塊名稱": "盈富基金(HSI ETF)", "市場": "HK"},
    {"板塊代號": "2828.HK", "板塊名稱": "恒中國ETF",        "市場": "HK"},
    {"板塊代號": "3032.HK", "板塊名稱": "恒科技ETF",        "市場": "HK"},
]
_PLATES_US = [
    {"板塊代號": "^GSPC",  "板塊名稱": "S&P 500",         "市場": "US"},
    {"板塊代號": "^IXIC",  "板塊名稱": "納斯達克綜合",     "市場": "US"},
    {"板塊代號": "^DJI",   "板塊名稱": "道瓊工業",         "市場": "US"},
    {"板塊代號": "QQQ",    "板塊名稱": "納斯達克100 ETF",  "市場": "US"},
    {"板塊代號": "SPY",    "板塊名稱": "S&P500 ETF",       "市場": "US"},
    {"板塊代號": "XLK",    "板塊名稱": "科技板塊 ETF",     "市場": "US"},
    {"板塊代號": "XLF",    "板塊名稱": "金融板塊 ETF",     "市場": "US"},
    {"板塊代號": "XLE",    "板塊名稱": "能源板塊 ETF",     "市場": "US"},
    {"板塊代號": "XLV",    "板塊名稱": "醫療板塊 ETF",     "市場": "US"},
    {"板塊代號": "XLI",    "板塊名稱": "工業板塊 ETF",     "市場": "US"},
    {"板塊代號": "XLY",    "板塊名稱": "非必需消費 ETF",   "市場": "US"},
    {"板塊代號": "ARKK",   "板塊名稱": "ARK 創新 ETF",    "市場": "US"},
]


def query_futu_plate_list(market: str = "HK") -> pd.DataFrame:
    """主要市場 ETF / 指數板塊清單（yfinance 版）。market："HK"/"US" """
    data = _PLATES_HK if market.upper() == "HK" else _PLATES_US
    return pd.DataFrame(data)


def query_futu_plate_stocks(plate_code: str) -> pd.DataFrame:
    """ETF / 指數成分股前20大持股（yfinance）。plate_code：如 "QQQ"、"XLK" """
    symbol = _futu_to_yf(plate_code) if "." in plate_code else plate_code
    try:
        ticker = yf.Ticker(symbol)
        # 嘗試取 ETF 持股
        try:
            fd = ticker.funds_data
            if fd is not None:
                holdings = fd.top_holdings
                if holdings is not None and not holdings.empty:
                    holdings = holdings.reset_index()
                    holdings.columns = [str(c) for c in holdings.columns]
                    return holdings.head(20)
        except Exception:
            pass
        # 備援：回傳基本資訊
        info = ticker.info
        return pd.DataFrame([{
            "代號": symbol,
            "名稱": info.get("longName", symbol),
            "說明": "此代號不是 ETF，無法取得成分股。請用板塊 ETF 代號（如 QQQ、XLK）"
        }])
    except Exception as e:
        return pd.DataFrame({"錯誤": [str(e)]})


def query_futu_owner_plate(codes: list) -> pd.DataFrame:
    """查詢股票所屬板塊與產業（yfinance）。codes：["HK.00700","US.AAPL"] """
    rows = []
    for code in codes:
        symbol = _futu_to_yf(code)
        try:
            info = yf.Ticker(symbol).info
            rows.append({
                "代號":   code,
                "yf代號": symbol,
                "名稱":   info.get("longName") or info.get("shortName", "N/A"),
                "板塊":   info.get("sector", "N/A"),
                "產業":   info.get("industry", "N/A"),
                "國家":   info.get("country", "N/A"),
            })
        except Exception as e:
            rows.append({"代號": code, "板塊": f"查詢失敗: {e}"})
    return pd.DataFrame(rows)
