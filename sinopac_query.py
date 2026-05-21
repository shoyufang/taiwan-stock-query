"""
台股查詢工具箱（公開版 / main 分支）
不依賴永豐金 Shioaji API，使用 TWSE OpenAPI + yfinance 替代。
帳務功能不支援（需券商 CA 憑證）。

local 分支為含永豐金完整版。

需求：pip install pandas yfinance FinMind requests streamlit plotly
"""

import sys
import os
import pandas as pd
import yfinance as yf
from FinMind.data import DataLoader
from datetime import date, timedelta, timezone

def _get_finmind_token() -> str:
    """FinMind Token 讀取順序：環境變數 → config.json → Streamlit Secrets"""
    token = os.environ.get("FINMIND_TOKEN", "")
    if not token:
        try:
            from config import load_config
            token = load_config().get("finmind_token", "")
        except Exception:
            pass
    return token

FINMIND_TOKEN = _get_finmind_token()

# ── 共通連線 Session（用於 REST API 優化） ───────────────
import requests as _requests
_SESSION = _requests.Session()


def _finmind() -> DataLoader:
    """取得 FinMind DataLoader（使用單例池）"""
    return FinMindConnectionPool.get_api()

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


# ── FinMind 連線池單例模式 ────────────────────────────────
class FinMindConnectionPool:
    """FinMind 連線池管理器（單例模式）"""
    _instance = None
    _api = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FinMindConnectionPool, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_api(cls) -> DataLoader:
        if cls._api is None:
            cls._api = DataLoader()
            cls._api.login_by_token(api_token=FINMIND_TOKEN)
        return cls._api


# ══════════════════════════════════════════════════════════
# 一、市場排行（TWSE 盤後資料，非即時）
# ══════════════════════════════════════════════════════════

def query_scanner(
    scanner_type: str = "ChangePercentRank",
    ascending: bool = True,
    query_date: str = None,
    count: int = 10,
) -> pd.DataFrame:
    """
    市場排行（TWSE 盤後資料，收盤後更新，非即時盤中資料）。

    scanner_type 選項：
        ChangePercentRank  漲跌幅%排行
        ChangePriceRank    漲跌價排行
        DayRangeRank       日振幅排行
        VolumeRank         成交量排行
        AmountRank         成交金額排行

    ascending=True  → 由大到小（漲幅最高 / 量最大）
    ascending=False → 由小到大（跌幅最深）
    count           → 取前 N 筆
    """
    df = query_twse_daily_all()
    if df.empty:
        return df

    # 轉數字（TWSE 欄位含千分位逗號）
    num_cols = ["成交量(股)", "成交金額", "開盤", "最高", "最低", "收盤", "漲跌"]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", "").str.replace("+", ""),
                errors="coerce"
            )

    df["昨收"] = (df["收盤"] - df["漲跌"]).round(2)
    with_zeros = df["昨收"].replace(0, float("nan"))
    df["漲跌幅%"] = (df["漲跌"] / with_zeros * 100).round(2)
    df["振幅%"]   = ((df["最高"] - df["最低"]) / with_zeros * 100).round(2)

    sort_map = {
        "ChangePercentRank": "漲跌幅%",
        "ChangePriceRank":   "漲跌",
        "DayRangeRank":      "振幅%",
        "VolumeRank":        "成交量(股)",
        "AmountRank":        "成交金額",
    }
    sort_col = sort_map.get(scanner_type, "漲跌幅%")
    df = df.dropna(subset=[sort_col])
    df = df.sort_values(sort_col, ascending=not ascending).head(count)
    return df.reset_index(drop=True)


# ══════════════════════════════════════════════════════════
# 二、即時快照（不需 CA）
# ══════════════════════════════════════════════════════════

def query_snapshot(codes: list) -> pd.DataFrame:
    """
    個股報價快照（yfinance，約 15 分鐘延遲）。
    codes 範例：["2330", "2317", "2454"]
    """
    rows = []
    for code in codes:
        try:
            t  = yf.Ticker(f"{code}.TW")
            fi = t.fast_info
            prev  = fi.previous_close or 0
            close = fi.last_price or prev
            chg   = round(close - prev, 2) if prev else 0
            chg_p = round(chg / prev * 100, 2) if prev else 0
            rows.append({
                "代號":    code,
                "漲跌幅%": chg_p,
                "昨收":    prev,
                "開盤":    fi.open,
                "最高":    fi.day_high,
                "最低":    fi.day_low,
                "收盤":    close,
                "漲跌":    chg,
                "成交量":  fi.three_month_average_volume,
            })
        except Exception as e:
            rows.append({"代號": code, "說明": f"查無資料 ({e})"})
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════
# 三、歷史資料（不需 CA）
# ══════════════════════════════════════════════════════════

def query_kbars(
    code: str,
    start: str,
    end: str = None,
    market: str = "Stocks",
) -> pd.DataFrame:
    """
    台股日K線（yfinance，2000年起）。
    code：股票代號，如 "2330"
    start/end："YYYY-MM-DD"
    market：Stocks（其他市場不支援公開版）
    """
    if end is None:
        end = str(date.today())
    ticker_code = f"{code}.TW"
    df = yf.download(ticker_code, start=start, end=end,
                     progress=False, auto_adjust=True, multi_level_index=False)
    if df.empty:
        return pd.DataFrame({"說明": [f"查無 {code} 的 K 線資料"]})
    df.index.name = "ts"
    col_map = {"Open": "開盤", "High": "最高", "Low": "最低",
               "Close": "收盤", "Volume": "成交量"}
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    return df


def query_ticks(*args, **kwargs) -> pd.DataFrame:
    """逐筆成交（公開版不支援，請使用 local 分支完整版）"""
    return pd.DataFrame({"說明": ["逐筆成交需要永豐金 API，公開版不支援。"
                                   "請切換至 local 分支（本機完整版）。"]})


# ══════════════════════════════════════════════════════════
# 四、帳務查詢（公開版不支援，需永豐金 CA 憑證）
# ══════════════════════════════════════════════════════════

_BROKER_MSG = "此功能需要永豐金券商帳號及 CA 憑證，公開版不支援。請切換至 local 分支（本機完整版）。"


def query_positions(*args, **kwargs) -> pd.DataFrame:
    return pd.DataFrame({"說明": [_BROKER_MSG]})


def query_position_detail(*args, **kwargs) -> pd.DataFrame:
    return pd.DataFrame({"說明": [_BROKER_MSG]})


def query_profit_loss(*args, **kwargs) -> pd.DataFrame:
    return pd.DataFrame({"說明": [_BROKER_MSG]})


def query_profit_loss_summary(*args, **kwargs) -> pd.DataFrame:
    return pd.DataFrame({"說明": [_BROKER_MSG]})


def query_account_balance(*args, **kwargs) -> dict:
    return {"說明": _BROKER_MSG}


def query_margin(*args, **kwargs) -> dict:
    return {"說明": _BROKER_MSG}


def query_trading_limits(*args, **kwargs) -> dict:
    return {"說明": _BROKER_MSG}


def query_settlements(*args, **kwargs) -> pd.DataFrame:
    return pd.DataFrame({"說明": [_BROKER_MSG]})


# ══════════════════════════════════════════════════════════
# 五、FinMind 查詢（籌碼面資料）
# ══════════════════════════════════════════════════════════

def query_institutional(
    code: str,
    start_date: str = None,
    end_date: str = None,
) -> pd.DataFrame:
    """
    三大法人買賣超（免費）。
    回傳欄位：date, name, buy, sell, net（買超=buy-sell）
    name 說明：
        Foreign_Investor    外資
        Investment_Trust    投信
        Dealer_self         自營商（自行買賣）
        Dealer_Hedging      自營商（避險）
        Foreign_Dealer_Self 外資自營
    """
    if start_date is None:
        start_date = str(date.today() - timedelta(days=30))
    if end_date is None:
        end_date = str(date.today())

    api = _finmind()
    df = api.taiwan_stock_institutional_investors(
        stock_id=code,
        start_date=start_date,
        end_date=end_date,
    )
    name_map = {
        "Foreign_Investor":    "外資",
        "Investment_Trust":    "投信",
        "Dealer_self":         "自營(自行)",
        "Dealer_Hedging":      "自營(避險)",
        "Foreign_Dealer_Self": "外資自營",
    }
    df["name"] = df["name"].map(name_map).fillna(df["name"])
    df["net"]  = df["buy"] - df["sell"]
    df = df.rename(columns={"date": "日期", "name": "法人", "buy": "買進", "sell": "賣出", "net": "買超"})
    return df[["日期", "法人", "買進", "賣出", "買超"]]


def query_institutional_summary(
    code: str,
    start_date: str = None,
    end_date: str = None,
) -> pd.DataFrame:
    """三大法人買賣超彙總（每日合計，方便看趨勢）"""
    df = query_institutional(code, start_date, end_date)
    summary = (
        df.groupby("日期")[["買進", "賣出", "買超"]]
        .sum()
        .reset_index()
    )
    summary["累計買超"] = summary["買超"].cumsum()
    return summary


def query_daily_kbar_finmind(
    code: str,
    start_date: str = None,
    end_date: str = None,
) -> pd.DataFrame:
    """
    股價日 K（FinMind，免費）。
    回傳欄位：date, open, max, min, close, volume, Trading_money, spread, spread_per
    """
    if start_date is None:
        start_date = str(date.today() - timedelta(days=60))
    if end_date is None:
        end_date = str(date.today())

    api = _finmind()
    df = api.taiwan_stock_daily(
        stock_id=code,
        start_date=start_date,
        end_date=end_date,
    )
    df = df.rename(columns={
        "date":             "日期",
        "open":             "開盤",
        "max":              "最高",
        "min":              "最低",
        "close":            "收盤",
        "Trading_Volume":   "成交量(股)",
        "Trading_money":    "成交金額",
        "spread":           "漲跌",
        "Trading_turnover": "成交筆數",
    })
    return df[["日期", "開盤", "最高", "最低", "收盤", "漲跌", "成交量(股)", "成交金額", "成交筆數"]]


def query_margin_short(code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """融資融券（免費）：融資餘額、融券餘額、券資比"""
    if start_date is None: start_date = str(date.today() - timedelta(days=30))
    if end_date   is None: end_date   = str(date.today())
    df = _finmind().taiwan_stock_margin_purchase_short_sale(
        stock_id=code, start_date=start_date, end_date=end_date
    )
    df = df.rename(columns={
        "date": "日期",
        "MarginPurchaseBuy":        "融資買進",
        "MarginPurchaseSell":       "融資賣出",
        "MarginPurchaseCashRepayment": "融資現還",
        "MarginPurchaseYesterdayBalance": "融資昨餘",
        "MarginPurchaseTodayBalance":     "融資今餘",
        "MarginPurchaseLimit":      "融資限額",
        "ShortSaleBuy":             "融券買進",
        "ShortSaleSell":            "融券賣出",
        "ShortSaleStockRepayment":  "融券現還",
        "ShortSaleYesterdayBalance":"融券昨餘",
        "ShortSaleTodayBalance":    "融券今餘",
        "ShortSaleLimit":           "融券限額",
        "OffsetLoanAndShort":       "資券互抵",
    })
    cols = ["日期", "融資今餘", "融資買進", "融資賣出", "融券今餘", "融券買進", "融券賣出", "資券互抵"]
    return df[[c for c in cols if c in df.columns]]


def query_shareholding(code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """外資持股比例（免費）"""
    if start_date is None: start_date = str(date.today() - timedelta(days=90))
    if end_date   is None: end_date   = str(date.today())
    df = _finmind().taiwan_stock_shareholding(
        stock_id=code, start_date=start_date, end_date=end_date
    )
    df = df.rename(columns={
        "date":                       "日期",
        "ForeignInvestmentRemainingShares": "外資可買張數",
        "ForeignInvestmentShares":         "外資持股張數",
        "ForeignInvestmentRemainPercent":  "外資可買%",
        "ForeignInvestmentSharesPercent":  "外資持股%",
        "ForeignInvestmentUpperLimitPercent": "外資上限%",
    })
    cols = ["日期", "外資持股張數", "外資持股%", "外資可買張數", "外資可買%", "外資上限%"]
    return df[[c for c in cols if c in df.columns]]


def query_securities_lending(code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """借券成交明細（免費）"""
    if start_date is None: start_date = str(date.today() - timedelta(days=30))
    if end_date   is None: end_date   = str(date.today())
    df = _finmind().taiwan_stock_securities_lending(
        stock_id=code, start_date=start_date, end_date=end_date
    )
    df = df.rename(columns={
        "date":           "日期",
        "BorrowingShares":"借券張數",
        "ReturnShares":   "還券張數",
        "LendingShares":  "借券餘額",
        "LendingMoney":   "借券金額",
    })
    cols = ["日期", "借券張數", "還券張數", "借券餘額", "借券金額"]
    return df[[c for c in cols if c in df.columns]]


def query_per_pbr(code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """本益比／股價淨值比（免費）"""
    if start_date is None: start_date = str(date.today() - timedelta(days=60))
    if end_date   is None: end_date   = str(date.today())
    df = _finmind().taiwan_stock_per_pbr(
        stock_id=code, start_date=start_date, end_date=end_date
    )
    df = df.rename(columns={
        "date":           "日期",
        "PER":            "本益比(PER)",
        "PBR":            "股淨比(PBR)",
        "dividend_yield": "殖利率%",
    })
    cols = ["日期", "本益比(PER)", "股淨比(PBR)", "殖利率%"]
    return df[[c for c in cols if c in df.columns]]


def query_day_trading(code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """當沖交易量（免費）"""
    if start_date is None: start_date = str(date.today() - timedelta(days=30))
    if end_date   is None: end_date   = str(date.today())
    df = _finmind().taiwan_stock_day_trading(
        stock_id=code, start_date=start_date, end_date=end_date
    )
    df = df.rename(columns={
        "date":              "日期",
        "BuyAfterSale":      "先買後賣(張)",
        "SaleAfterBuy":      "先賣後買(張)",
        "DayTradingMoney":   "當沖金額",
    })
    cols = ["日期", "先買後賣(張)", "先賣後買(張)", "當沖金額"]
    return df[[c for c in cols if c in df.columns]]


def query_month_revenue(code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """月營收（免費，2002年起）"""
    if start_date is None: start_date = "2025-01-01"
    if end_date   is None: end_date   = str(date.today())
    df = _finmind().taiwan_stock_month_revenue(
        stock_id=code, start_date=start_date, end_date=end_date
    )
    df = df.rename(columns={
        "date":          "日期",
        "revenue":       "月營收",
        "revenue_month": "當月",
        "revenue_year":  "年份",
    })
    cols = ["日期", "月營收"]
    return df[[c for c in cols if c in df.columns]]


def query_financial_statements(code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """綜合損益表（免費，1990年起）"""
    if start_date is None: start_date = "2024-01-01"
    if end_date   is None: end_date   = str(date.today())
    df = _finmind().taiwan_stock_financial_statement(
        stock_id=code, start_date=start_date, end_date=end_date
    )
    df = df.rename(columns={"date": "日期", "type": "科目", "value": "金額"})
    return df[["日期", "科目", "金額"]]


def query_balance_sheet(code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """資產負債表（免費，2011年起）"""
    if start_date is None: start_date = "2024-01-01"
    if end_date   is None: end_date   = str(date.today())
    df = _finmind().taiwan_stock_balance_sheet(
        stock_id=code, start_date=start_date, end_date=end_date
    )
    df = df.rename(columns={"date": "日期", "type": "科目", "value": "金額"})
    return df[["日期", "科目", "金額"]]


def query_dividend(code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """股利政策（免費，2005年起）"""
    if start_date is None: start_date = "2015-01-01"
    if end_date   is None: end_date   = str(date.today())
    df = _finmind().taiwan_stock_dividend(
        stock_id=code, start_date=start_date, end_date=end_date
    )
    keep = ["date", "StockEarningsDistribution", "StockStatutorySurplus",
            "StockExDividendTradingDate", "TotalEmployeeStockDividend",
            "CashEarningsDistribution", "CashStatutorySurplus",
            "CashExDividendTradingDate", "TotalEmployeeCashDividend"]
    df = df[[c for c in keep if c in df.columns]]
    df = df.rename(columns={
        "date":                        "年度",
        "StockEarningsDistribution":   "股票股利(盈餘)",
        "StockStatutorySurplus":        "股票股利(公積)",
        "StockExDividendTradingDate":   "除權日",
        "TotalEmployeeStockDividend":   "員工股利",
        "CashEarningsDistribution":     "現金股利(盈餘)",
        "CashStatutorySurplus":         "現金股利(公積)",
        "CashExDividendTradingDate":    "除息日",
        "TotalEmployeeCashDividend":    "員工現金",
    })
    return df


def query_futures_daily(code: str = "TX", start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """期貨日行情（免費，1998年起）。code 範例：TX=台指期, MTX=小台"""
    if start_date is None: start_date = str(date.today() - timedelta(days=30))
    if end_date   is None: end_date   = str(date.today())
    df = _finmind().taiwan_futures_daily(
        futures_id=code, start_date=start_date, end_date=end_date
    )
    df = df.rename(columns={
        "date":              "日期",
        "ContractDate":      "合約月份",
        "Open":              "開盤",
        "Max":               "最高",
        "Min":               "最低",
        "Close":             "收盤",
        "Change":            "漲跌",
        "ChangePer":         "漲跌%",
        "Volume":            "成交量",
        "SettlementPrice":   "結算價",
        "OpenInterest":      "未平倉",
    })
    cols = ["日期", "合約月份", "開盤", "最高", "最低", "收盤", "漲跌", "漲跌%", "成交量", "未平倉"]
    return df[[c for c in cols if c in df.columns]]


def _finmind_api(dataset: str, data_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """直接呼叫 FinMind REST API（DataLoader 未封裝的 dataset 用此函式）"""
    import requests
    r = requests.get(
        "https://api.finmindtrade.com/api/v4/data",
        params={"dataset": dataset, "data_id": data_id,
                "start_date": start_date, "end_date": end_date,
                "token": FINMIND_TOKEN},
        timeout=15,
    )
    d = r.json()
    if d.get("status") != 200:
        raise ValueError(d.get("msg", "API 錯誤"))
    return pd.DataFrame(d["data"])


def query_futures_institutional(code: str = "TX", start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """期貨三大法人（免費，2018年起）"""
    if start_date is None: start_date = str(date.today() - timedelta(days=30))
    if end_date   is None: end_date   = str(date.today())
    df = _finmind_api("TaiwanFuturesInstitutionalInvestors", code, start_date, end_date)
    name_map = {
        "Foreign_Dealer_Self": "外資自營",
        "Foreign_Investor":    "外資",
        "Investment_Trust":    "投信",
        "Dealer":              "自營商",
    }
    df["institutional_investors"] = df["institutional_investors"].map(name_map).fillna(df["institutional_investors"])
    df["多單淨"] = df["long_deal_volume"].astype(int) - df["short_deal_volume"].astype(int)
    df = df.rename(columns={
        "date":                              "日期",
        "institutional_investors":           "法人",
        "long_deal_volume":                  "多單買進",
        "short_deal_volume":                 "空單賣出",
        "long_open_interest_balance_volume": "多方未平倉",
        "short_open_interest_balance_volume":"空方未平倉",
    })
    cols = ["日期", "法人", "多單買進", "空單賣出", "多單淨", "多方未平倉", "空方未平倉"]
    return df[[c for c in cols if c in df.columns]]


def query_exchange_rate(currency: str = "USD", start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """台灣銀行匯率（免費）。
    currency 選項：USD, JPY, EUR, CNY, HKD, GBP, AUD, KRW, SGD, CHF 等
    """
    if start_date is None: start_date = str(date.today() - timedelta(days=30))
    if end_date   is None: end_date   = str(date.today())
    df = _finmind_api("TaiwanExchangeRate", currency, start_date, end_date)
    df = df.rename(columns={
        "date":     "日期",
        "currency": "幣別",
        "cash_buy": "現金買入",
        "cash_sell":"現金賣出",
        "spot_buy": "即期買入",
        "spot_sell":"即期賣出",
    })
    cols = ["日期", "幣別", "現金買入", "現金賣出", "即期買入", "即期賣出"]
    return df[[c for c in cols if c in df.columns]]


# ══════════════════════════════════════════════════════════
# 六、新聞查詢（yfinance，不需帳號）
# ══════════════════════════════════════════════════════════

def query_news(code: str = None, count: int = 10) -> pd.DataFrame:
    """
    查詢個股或大盤即時新聞（來源：Yahoo Finance）。
    code：台股代號，如 "2330"（會自動加 .TW）；不填則查台灣市場大盤新聞
    count：顯示筆數（最多約 20 筆）
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
            from datetime import datetime
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


# ══════════════════════════════════════════════════════════
# 七、證交所 TWSE OpenAPI（完全免費，無需金鑰，查當日資料）
# ══════════════════════════════════════════════════════════

import requests as _requests

_TWSE = "https://openapi.twse.com.tw/v1"


def _twse_get(path: str) -> pd.DataFrame:
    """
    呼叫 TWSE 新版 OpenAPI。
    注意：Streamlit Cloud（海外 IP）可能被 TWSE 限流，回傳空 body 或 HTML。
    此時拋出 RuntimeError 讓上層顯示友善訊息，而非 JSON parse error。
    """
    r = _SESSION.get(f"{_TWSE}{path}", timeout=15,
                     headers={"Accept": "application/json"})
    r.raise_for_status()
    ct = r.headers.get("Content-Type", "")
    
    # Check for obvious HTML response first
    if not r.text or r.text.strip().startswith("<!"):
        raise RuntimeError(
            "TWSE OpenAPI 回傳空白或 HTML（可能因海外 IP 被限制）。\n"
            "今日資料將於 20:05 自動快取後可查詢，或請稍後再試。"
        )
        
    try:
        data = r.json()
    except ValueError:
        # JSONDecodeError inherits from ValueError
        raise RuntimeError(
            "TWSE OpenAPI 回傳非 JSON 格式（可能因海外 IP 被限制）。\n"
            "今日資料將於 20:05 自動快取後可查詢，或請稍後再試。"
        )
        
    return pd.DataFrame(data)


def query_twse_daily_all(code: str = None) -> pd.DataFrame:
    """
    全市場上市個股當日收盤行情（TWSE OpenAPI，免費）。
    code：篩選特定股票代號，如 "2330"；不填則傳回全市場。
    """
    df = _twse_get("/exchangeReport/STOCK_DAY_ALL")
    df = df.rename(columns={
        "Code":          "代號",
        "Name":          "名稱",
        "TradeVolume":   "成交量(股)",
        "TradeValue":    "成交金額",
        "OpeningPrice":  "開盤",
        "HighestPrice":  "最高",
        "LowestPrice":   "最低",
        "ClosingPrice":  "收盤",
        "Change":        "漲跌",
        "Transaction":   "成交筆數",
    })
    if code:
        df = df[df["代號"] == code]
    return df


def query_twse_bwibbu(code: str = None) -> pd.DataFrame:
    """
    全市場上市個股本益比、殖利率及股價淨值比（當日）。
    code：篩選特定代號；不填則傳回全市場。
    """
    df = _twse_get("/exchangeReport/BWIBBU_ALL")
    df = df.rename(columns={
        "Code":          "代號",
        "Name":          "名稱",
        "PEratio":       "本益比",
        "DividendYield": "殖利率%",
        "PBratio":       "股淨比",
    })
    if code:
        df = df[df["代號"] == code]
    return df


def query_twse_institutional(code: str = None) -> pd.DataFrame:
    """
    三大法人買賣超（全市場，當日）。
    新版 OpenAPI /fund/T86 已失效，改用舊版 rwd API。
    必須帶 date 與 selectType=ALL，否則只回傳約 7 筆摘要資料。
    code：篩選特定代號；不填則傳回全市場。
    """
    today = date.today().strftime("%Y%m%d")
    df = _twse_old("fund/T86", {"date": today, "selectType": "ALL"})
    if code and "證券代號" in df.columns:
        df = df[df["證券代號"] == code]
    elif code and "Code" in df.columns:
        df = df[df["Code"] == code]
    return df


def query_twse_margin() -> pd.DataFrame:
    """融資融券彙總（當日）"""
    return _twse_get("/exchangeReport/MI_MARGN")


def _process_company_df(df: pd.DataFrame) -> pd.DataFrame:
    """處理並重新命名公司基本資料的欄位 (維持向後相容)"""
    df = df.rename(columns={
        "公司代號": "代號",
        "公司名稱": "名稱",
        "英文簡稱": "英文名稱",
        "產業別": "產業別",
        "住址": "地址",
        "營利事業統一編號": "統一編號",
        "董事長": "董事長",
        "發言人": "發言人",
        "發言人職稱": "發言人職稱",
        "上市日期": "上市日期",
        "上櫃日期": "上市日期"
    })
    cols = ["代號", "名稱", "英文名稱", "產業別", "地址", "統一編號", "董事長", "發言人", "發言人職稱", "上市日期"]
    # 兼容簡繁體
    if "產業別" in df.columns:
        cols[3] = "產業別"
    return df[[c for c in cols if c in df.columns]]


def query_twse_company(code: str) -> pd.DataFrame:
    """
    上市公司、上櫃公司與興櫃公司基本資料 (整合 TWSE OpenAPI 與 MOPS OpenData)
    code：股票代號，如 "2330" 或 "5483"
    """
    code = str(code).strip()
    
    # 方案 A: 優先使用本機的 TWSE OpenAPI 查詢上市公司 JSON (最快且有快取與 Session 機制)
    try:
        df = _twse_get("/opendata/t187ap03_L")
        if not df.empty and "公司代號" in df.columns:
            df["公司代號"] = df["公司代號"].astype(str).str.strip()
            match_df = df[df["公司代號"] == code]
            if not match_df.empty:
                return _process_company_df(match_df)
    except Exception as e:
        import logging
        logging.warning(f"TWSE OpenAPI 查詢失敗，將嘗試公開資訊觀測站備用方案: {e}")

    # 方案 B: 透過公開資訊觀測站 (MOPS) CSV 查詢 (同時支援 上市 _L, 上櫃 _O, 興櫃 _R)
    import urllib3
    from io import StringIO
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    for suffix in ["L", "O", "R"]:
        url = f"https://mopsfin.twse.com.tw/opendata/t187ap03_{suffix}.csv"
        try:
            r = _SESSION.get(url, timeout=10, verify=False)
            r.raise_for_status()
            r.encoding = "utf-8-sig"
            df_csv = pd.read_csv(StringIO(r.text))
            if not df_csv.empty and "公司代號" in df_csv.columns:
                df_csv["公司代號"] = df_csv["公司代號"].astype(str).str.strip()
                match_df = df_csv[df_csv["公司代號"] == code]
                if not match_df.empty:
                    return _process_company_df(match_df)
        except Exception as e:
            continue
            
    return pd.DataFrame()


def _twse_old(path: str, params: dict = None) -> pd.DataFrame:
    """舊版 TWSE REST API（www.twse.com.tw/rwd/zh/...）
    TWSE 憑證缺少 Subject Key Identifier，需關閉 SSL 驗證。"""
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    url = f"https://www.twse.com.tw/rwd/zh/{path}"
    p = {"response": "json"}
    if params:
        p.update(params)
    r = _SESSION.get(url, params=p, timeout=15, verify=False,
                     headers={"Accept": "application/json"})
    r.raise_for_status()
    data = r.json()
    fields = data.get("fields") or data.get("title") or []
    rows   = data.get("data", [])
    if not rows:
        return pd.DataFrame(columns=fields if fields else [])
    return pd.DataFrame(rows, columns=fields) if fields else pd.DataFrame(rows)


def query_twse_disposition() -> pd.DataFrame:
    """
    公布處置有價證券（當前生效清單）。
    處置措施：分盤撮合、禁止當沖、限制委託量等。
    只顯示重點欄位：代號 / 名稱 / 累計 / 處置條件 / 處置起迄時間 / 公布日期
    """
    df = _twse_old("announcement/punish")
    if df.empty:
        return df
    keep = ["證券代號", "證券名稱", "累計", "處置條件", "處置起迄時間", "公布日期"]
    return df[[c for c in keep if c in df.columns]]


def query_twse_notice() -> pd.DataFrame:
    """
    公布注意有價證券（當日注意股清單）。
    欄位：編號 / 證券代號 / 名稱 / 累計次數 / 注意交易資訊 / 日期 / 收盤價 / 本益比
    """
    return _twse_old("announcement/notice")


def query_twse_mi_index() -> pd.DataFrame:
    """大盤今日收盤指數（加權指數、成交金額、漲跌家數等）"""
    return _twse_get("/exchangeReport/MI_INDEX")


def query_twse_stock_day_avg(code: str = None) -> pd.DataFrame:
    """個股日收盤價及月平均價（全市場當日）"""
    df = _twse_get("/exchangeReport/STOCK_DAY_AVG_ALL")
    rename = {"Code": "代號", "Name": "名稱",
               "ClosingPrice": "收盤價", "MonthlyAveragePrice": "月均價"}
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    if code and "代號" in df.columns:
        df = df[df["代號"] == code]
    return df


def query_twse_monthly(code: str = None) -> pd.DataFrame:
    """個股月成交資訊（當月成交量、成交金額、開高低收）"""
    df = _twse_get("/exchangeReport/FMSRFK_ALL")
    if code and "Code" in df.columns:
        df = df[df["Code"] == code]
    return df


def query_twse_annual(code: str = None) -> pd.DataFrame:
    """個股年成交資訊"""
    df = _twse_get("/exchangeReport/FMNPTK_ALL")
    if code and "Code" in df.columns:
        df = df[df["Code"] == code]
    return df


def query_twse_qfiis_cat() -> pd.DataFrame:
    """外資及陸資持股比例（依產業別彙總）"""
    return _twse_get("/fund/MI_QFIIS_cat")


def query_twse_qfiis_top20() -> pd.DataFrame:
    """外資及陸資持股前 20 名彙總"""
    return _twse_get("/fund/MI_QFIIS_sort_20")


def query_twse_newlisting() -> pd.DataFrame:
    """最近上市公司清單"""
    return _twse_get("/company/newlisting")


def query_twse_suspend_listing() -> pd.DataFrame:
    """下市公司清單"""
    return _twse_get("/company/suspendListingCsvAndHtml")


def query_twse_apply_listing_local() -> pd.DataFrame:
    """國內公司申請上市清單"""
    return _twse_get("/company/applylistingLocal")


def query_twse_apply_listing_foreign() -> pd.DataFrame:
    """外國公司申請上市清單"""
    return _twse_get("/company/applylistingForeign")


def query_twse_news_list() -> pd.DataFrame:
    """證交所官方新聞列表"""
    return _twse_get("/news/newsList")


def query_twse_event_list() -> pd.DataFrame:
    """證交所活動公告列表"""
    return _twse_get("/news/eventList")


def query_twse_dividend_policy() -> pd.DataFrame:
    """上市公司股利分派資訊（現金股利、股票股利等）"""
    return _twse_get("/opendata/t187ap45_L")


def query_twse_fund_basic() -> pd.DataFrame:
    """基金基本資訊彙總"""
    return _twse_get("/opendata/t187ap47_L")


def query_twse_monthly_revenue() -> pd.DataFrame:
    """上市公司月營收彙總"""
    return _twse_get("/opendata/t187ap05_P")


def query_twse_income_statement(industry: str = "ci") -> pd.DataFrame:
    """上市公司綜合損益表。
    industry: ci=一般業, basi=金融業, bd=證券期貨, fh=金控保險, ins=保險業, mim=KY外國公司
    """
    return _twse_get(f"/opendata/t187ap06_X_{industry}")


def query_twse_balance_sheet_openapi(industry: str = "ci") -> pd.DataFrame:
    """上市公司資產負債表（TWSE OpenAPI）。
    industry: ci=一般業, mim=KY外國公司
    """
    return _twse_get(f"/opendata/t187ap07_X_{industry}")


def query_twse_etf_rank() -> pd.DataFrame:
    """ETF 定期定額月排行（開戶數 / 交易筆數）"""
    return _twse_get("/ETFReport/ETFRank")


_ESG_TOPICS = {
    1: "溫室氣體排放", 2: "能源管理", 3: "用水管理", 4: "廢棄物管理",
    5: "人力資源發展", 6: "董事會", 7: "投資人溝通", 8: "氣候相關議題管理",
    9: "功能性委員會", 10: "燃料管理", 11: "產品生命週期管理", 12: "食品安全",
    13: "供應鏈管理", 14: "產品品質與安全", 15: "社區關係", 16: "資訊安全",
    17: "普惠金融", 18: "股權與控制", 19: "風險管理政策",
    20: "反競爭行為法律爭議", 21: "職業安全衛生",
}


def query_twse_esg(topic_id: int) -> pd.DataFrame:
    """上市公司 ESG 揭露（指定主題）。
    topic_id: 1-21，主題對照見 sinopac_query._ESG_TOPICS
    """
    return _twse_get(f"/opendata/t187ap46_L_{topic_id}")


# ══════════════════════════════════════════════════════════
# 八、港美股查詢（yfinance 替代 FutuOpenD，無需本機軟體）
# ══════════════════════════════════════════════════════════

def _futu_to_yf(code: str) -> str:
    """將富途代號格式轉換為 yfinance 格式。
    HK.00700 → 0700.HK，US.AAPL → AAPL，其他原樣回傳"""
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
        {"市場": "market_hk", "名稱": "香港",   "tz": "Asia/Hong_Kong",   "sessions": [("09:30","12:00"),("13:00","16:00")]},
        {"市場": "market_us", "名稱": "美國",   "tz": "America/New_York", "sessions": [("09:30","16:00")]},
        {"市場": "market_sh", "名稱": "上海",   "tz": "Asia/Shanghai",    "sessions": [("09:30","11:30"),("13:00","15:00")]},
        {"市場": "market_sz", "名稱": "深圳",   "tz": "Asia/Shanghai",    "sessions": [("09:30","11:30"),("13:00","15:00")]},
        {"市場": "market_tw", "名稱": "台灣",   "tz": "Asia/Taipei",      "sessions": [("09:00","13:30")]},
        {"市場": "market_jp", "名稱": "日本",   "tz": "Asia/Tokyo",       "sessions": [("09:00","11:30"),("12:30","15:30")]},
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
    cols = ["代號","開盤","最高","最低","收盤","成交量"]
    return df[[c for c in cols if c in df.columns]].reset_index().rename(columns={"index":"日期","Date":"日期"})


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
        "可改用 Gemini AI 頁面詢問相關籌碼資訊，",
        "或參考 FinMind → 外資持股 / 融資融券 等替代數據。"
    ]})


def query_futu_capital_flow(code: str) -> pd.DataFrame:
    """資金流向（分鐘級）— 此功能需 FutuOpenD，目前不支援"""
    return pd.DataFrame({"說明": [
        "⚠️ 資金流向功能需要 FutuOpenD 才能使用。",
        "可改用 Gemini AI 頁面詢問相關資訊。"
    ]})


# 主要市場 ETF / 指數板塊清單（取代 Futu 板塊列表）
_PLATES_HK = [
    {"板塊代號": "^HSI",    "板塊名稱": "恒生指數",       "市場": "HK"},
    {"板塊代號": "^HSCE",   "板塊名稱": "H股指數",         "市場": "HK"},
    {"板塊代號": "2800.HK", "板塊名稱": "盈富基金(HSI ETF)","市場": "HK"},
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


# ══════════════════════════════════════════════════════════
# 智能查詢路由（? 模式）
# ══════════════════════════════════════════════════════════

# 格式：(關鍵字列表, 選單號碼, 說明, 需要代號?)
_ROUTES = [
    # ── 台股即時（Shioaji）──────────────────────────────
    (["漲幅", "漲停", "漲最多", "漲榜", "漲幅排行"],         "1",  "漲幅排行",         False),
    (["跌幅", "跌停", "跌最多", "跌榜", "跌幅排行"],         "2",  "跌幅排行",         False),
    (["成交量排行", "量排行", "爆量"],                        "3",  "成交量排行",       False),
    (["成交金額排行", "金額排行"],                            "4",  "成交金額排行",     False),
    (["即時", "快照", "現價", "報價", "現在股價"],            "5",  "個股即時快照",     True),
    (["K線", "日K", "走勢", "歷史行情", "台股K"],            "6",  "台股K線（Shioaji）", True),
    (["逐筆", "tick", "每筆成交"],                            "7",  "個股逐筆成交",     True),
    # ── 帳務 ────────────────────────────────────────────
    (["庫存", "持倉", "未實現損益"],                          "8",  "庫存未實現損益",   False),
    (["已實現", "出場損益"],                                  "9",  "已實現損益",       False),
    (["帳戶餘額", "可動用", "現金"],                          "10", "帳戶餘額",         False),
    # ── 新聞 ────────────────────────────────────────────
    (["新聞", "消息", "報導"],                                "14", "個股/大盤新聞",    True),
    # ── FinMind 籌碼/技術 ────────────────────────────────
    (["三大法人歷史", "法人歷史", "外資歷史"],                "16", "三大法人明細（歷史）", True),
    (["法人合計", "累計買超", "法人趨勢"],                    "17", "三大法人合計+累計", True),
    (["本益比歷史", "PER歷史", "股淨比歷史", "殖利率歷史"],  "19", "本益比/殖利率（歷史）", True),
    (["當沖"],                                                "20", "當沖交易量",       True),
    (["融資融券歷史", "資券歷史"],                            "21", "融資融券（歷史）", True),
    (["外資持股", "外資比例"],                                "22", "外資持股比例",     True),
    (["借券"],                                                "23", "借券成交",         True),
    # ── FinMind 基本面 ───────────────────────────────────
    (["月營收", "營收"],                                      "24", "月營收",           True),
    (["損益表", "獲利", "EPS", "淨利", "營業利益"],          "25", "綜合損益表",       True),
    (["資產", "負債", "淨值", "資產負債"],                    "26", "資產負債表",       True),
    (["股利", "股息", "配息", "除息", "除權"],                "27", "股利政策",         True),
    # ── FinMind 期貨/匯率 ────────────────────────────────
    (["台指期", "期貨行情", "TX", "小台", "MTX"],             "28", "期貨日行情",       False),
    (["期貨法人", "期貨三大法人", "期貨外資"],                "29", "期貨三大法人",     False),
    (["匯率", "外幣", "USD", "JPY", "EUR", "美元", "日圓"],  "30", "匯率查詢",         False),
    # ── TWSE 今日全市場 ──────────────────────────────────
    (["今日行情", "全市場行情", "所有股票", "上市行情"],      "41", "全市場當日行情（TWSE）", False),
    (["今日本益比", "今日殖利率", "全市場本益比"],            "42", "本益比/殖利率—今日全市場（TWSE）", False),
    (["今日法人", "今日三大法人", "法人今天", "今天法人"],    "43", "三大法人—今日全市場（TWSE）", False),
    (["今日融資", "今日融券", "融資今天", "融券今天"],        "44", "融資融券彙總今日（TWSE）", False),
    (["公司資料", "基本資料", "公司簡介", "股票資料"],        "45", "公司基本資料（TWSE）", True),
    (["處置", "處置股", "分盤", "禁止當沖", "處置有價證券"], "46", "處置有價證券（TWSE）", False),
    (["注意股", "注意有價證券", "警示", "注意交易"],          "47", "注意有價證券（TWSE）", False),
    # ── Futu 港美股 ─────────────────────────────────────
    (["港股", "HK.", "香港股", "騰訊", "阿里"],              "32", "港股K線（Futu）",  False),
    (["美股", "US.", "蘋果", "特斯拉", "AAPL", "TSLA"],     "32", "美股K線（Futu）",  False),
    (["全球市場", "市場開市", "開市狀態"],                    "31", "全球市場狀態（Futu）", False),
    (["板塊", "行業", "產業分類", "類股"],                    "36", "板塊列表（Futu）", False),
    (["資金分布", "大戶資金", "主力資金"],                    "34", "資金分布（Futu）", False),
    (["資金流向", "分鐘資金"],                                "35", "資金流向（Futu）", False),
]


def smart_query(question: str) -> list:
    """
    根據描述推薦最適合的查詢選項。
    傳回 [(選單號碼, 說明, 需要代號?), ...]，依命中關鍵字數量排序。
    """
    matches = {}  # choice → (score, desc, need_code)
    for keywords, choice, desc, need_code in _ROUTES:
        score = sum(1 for kw in keywords if kw in question)
        if score > 0:
            if choice not in matches or score > matches[choice][0]:
                matches[choice] = (score, desc, need_code)
    # 依分數由高到低排序
    ranked = sorted(matches.items(), key=lambda x: -x[1][0])
    return [(c, info[1], info[2]) for c, info in ranked]


# ── 決策速查表（給使用者參考）──────────────────────────────
DECISION_GUIDE = """
┌─────────────────────────────────────────────────────────────────────┐
│  📌  快速決策：我要查什麼 → 用哪個工具？                            │
├────────────────┬────────────────────────────────────────────────────┤
│  今日 / 即時   │  台股排行/快照/K線/逐筆 → 1~7（Shioaji）          │
│                │  今日全市場行情/法人/融資 → 41~44（TWSE）          │
│                │  港美股即時行情 → 需訂閱（Futu 受限）              │
├────────────────┼────────────────────────────────────────────────────┤
│  歷史 / 趨勢   │  法人/融資/外資/借券/當沖 → 16~23（FinMind）      │
│                │  月營收/損益表/資產負債/股利 → 24~27（FinMind）    │
│                │  港美股K線（歷史） → 32（Futu）                    │
│                │  台股K線（歷史） → 6（Shioaji）或 18（FinMind）    │
├────────────────┼────────────────────────────────────────────────────┤
│  評價指標      │  本益比/殖利率—今日全市場 → 42（TWSE）             │
│                │  本益比/殖利率—個股歷史 → 19（FinMind）            │
├────────────────┼────────────────────────────────────────────────────┤
│  期貨 / 匯率   │  台指期行情 → 28（FinMind）                        │
│                │  期貨三大法人 → 29（FinMind）                      │
│                │  匯率 → 30（FinMind）                              │
├────────────────┼────────────────────────────────────────────────────┤
│  港股 / 美股   │  K線 → 32  資金分布 → 34  板塊 → 36~38（Futu）    │
├────────────────┼────────────────────────────────────────────────────┤
│  公司資料      │  基本資料 → 45（TWSE）                             │
│  新聞          │  個股/大盤新聞 → 14/15（yfinance）                 │
│  帳務          │  庫存/損益/餘額 → 8~13（需CA憑證）                 │
└────────────────┴────────────────────────────────────────────────────┘"""


# ══════════════════════════════════════════════════════════
# 互動式選單（直接執行時使用）
# ══════════════════════════════════════════════════════════

MENU = """
╔══════════════════════════════════╦══════════════════════════════════╦══════════════════════════════════╗
║  【台股市場】不需CA              ║  【FinMind 籌碼/技術面】         ║  【富途 Futu OpenAPI】            ║
║   1. 漲幅排行                    ║  16. 三大法人明細                ║  需FutuOpenD運行中               ║
║   2. 跌幅排行                    ║  17. 三大法人合計+累計           ║  31. 全球市場狀態                ║
║   3. 成交量排行                  ║  18. 股價日K                     ║  32. 港/美股K線                  ║
║   4. 成交金額排行                ║  19. 本益比/股淨比/殖利率        ║  33. 股票基本資訊                ║
║   5. 個股即時快照                ║  20. 當沖交易量                  ║  34. 資金分布（大中小散）        ║
║   6. 個股K線                     ║  21. 融資融券                    ║  35. 資金流向（分鐘）            ║
║   7. 個股逐筆成交                ║  22. 外資持股比例                ║  36. 板塊列表                    ║
║  【帳務】需CA憑證                ║  23. 借券成交                    ║  37. 板塊股票                    ║
║   8. 庫存未實現損益              ║  【FinMind 基本面】              ║  38. 股票所屬板塊                ║
║   9. 已實現損益                  ║  24. 月營收                      ║  【證交所 TWSE】免費無金鑰       ║
║  10. 帳戶餘額                    ║  25. 綜合損益表                  ║  41. 全市場當日行情               ║
║  11. 交易額度                    ║  26. 資產負債表                  ║  42. 本益比/殖利率/股淨比        ║
║  12. 期貨保證金                  ║  27. 股利政策                    ║  43. 三大法人（全市場）           ║
║  13. 交割款明細                  ║  【FinMind 期貨/匯率】           ║  44. 融資融券彙總                 ║
║  【新聞】不需帳號                ║  28. 期貨日行情                  ║  45. 公司基本資料                 ║
║  14. 個股新聞                    ║  29. 期貨三大法人                ║   ?. 智能查詢                    ║
║  15. 大盤新聞                    ║  30. 匯率查詢                    ║   0. 離開                        ║
║                                  ║                                  ║  46. 處置有價證券                ║
║                                  ║                                  ║  47. 注意有價證券                ║
╚══════════════════════════════════╩══════════════════════════════════╩══════════════════════════════════╝"""

def _input(prompt: str, default=None):
    val = input(prompt).strip()
    return val if val else default


def main():
    while True:
        print(MENU)
        choice = input("請選擇功能（? 智能查詢 / g 決策指南）：").strip()

        # ── 決策指南 ─────────────────────────────────────────
        if choice in ("g", "G", "guide"):
            print(DECISION_GUIDE)
            input("\n按 Enter 返回選單...")
            continue

        # ── 智能查詢 ─────────────────────────────────────────
        if choice in ("?", "？", "s"):
            q = input("描述你要查的資料（如：2330今日融資、外資今天買超）：").strip()
            hits = smart_query(q)
            if not hits:
                print("  找不到符合的查詢，請直接輸入選單號碼。")
                input("\n按 Enter 返回選單...")
                continue
            print("\n  推薦查詢方式：")
            for i, (c, d, _) in enumerate(hits[:6], 1):
                print(f"  [{i}] 選單 {c:>2}  {d}")
            pick = input("\n  輸入編號立即執行（Enter 返回選單）：").strip()
            if pick.isdigit() and 1 <= int(pick) <= len(hits[:6]):
                choice = hits[int(pick) - 1][0]
            elif not pick:
                continue
            else:
                choice = pick  # 使用者直接輸入選單號碼

        if choice == "1":
            n = int(_input("筆數（預設10）：", "10"))
            d = _input("日期 YYYY-MM-DD（預設今日）：", None)
            df = query_scanner("ChangePercentRank", ascending=True, query_date=d, count=n)
            print(df.to_string(index=False))
        elif choice == "2":
            n = int(_input("筆數（預設10）：", "10"))
            d = _input("日期 YYYY-MM-DD（預設今日）：", None)
            df = query_scanner("ChangePercentRank", ascending=False, query_date=d, count=n)
            print(df.to_string(index=False))
        elif choice == "3":
            n = int(_input("筆數（預設10）：", "10"))
            d = _input("日期 YYYY-MM-DD（預設今日）：", None)
            df = query_scanner("VolumeRank", ascending=True, query_date=d, count=n)
            print(df.to_string(index=False))
        elif choice == "4":
            n = int(_input("筆數（預設10）：", "10"))
            d = _input("日期 YYYY-MM-DD（預設今日）：", None)
            df = query_scanner("AmountRank", ascending=True, query_date=d, count=n)
            print(df.to_string(index=False))
        elif choice == "5":
            codes = _input("股票代號（逗號分隔，如 2330,2317）：", "2330").split(",")
            codes = [c.strip() for c in codes]
            df = query_snapshot(codes)
            print(df.to_string(index=False))
        elif choice == "6":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期 YYYY-MM-DD：", str(date.today() - timedelta(days=30)))
            end   = _input("結束日期 YYYY-MM-DD（預設今日）：", None)
            df = query_kbars(code, start, end)
            print(df.tail(20).to_string())
        elif choice == "7":
            code = _input("股票代號（如 2330）：", "2330")
            d    = _input("日期 YYYY-MM-DD：", str(date.today()))
            last = _input("只取最後 N 筆（不填則取全日）：", None)
            df = query_ticks(code, d, last_cnt=int(last) if last else None)
            print(df.tail(20).to_string())
        elif choice == "8":
            t = _input("帳戶類型 stock/future（預設 stock）：", "stock")
            df = query_positions(t)
            print("無庫存部位" if df.empty else df.to_string(index=False))
        elif choice == "9":
            t = _input("帳戶類型 stock/future（預設 stock）：", "stock")
            b = _input("開始日期（預設今日）：", str(date.today()))
            e = _input("結束日期（預設今日）：", str(date.today()))
            df = query_profit_loss(b, e, t)
            print("查無損益資料" if df.empty else df.to_string(index=False))
        elif choice == "10":
            print(query_account_balance())
        elif choice == "11":
            print(query_trading_limits())
        elif choice == "12":
            print(query_margin())
        elif choice == "13":
            print(query_settlements().to_string(index=False))
        elif choice == "14":
            code = _input("股票代號（如 2330）：", "2330")
            n    = int(_input("筆數（預設10）：", "10"))
            print_news(code, n)
        elif choice == "15":
            n = int(_input("筆數（預設10）：", "10"))
            print_news(None, n)
        elif choice == "16":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期（預設近30天）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_institutional(code, start, end).to_string(index=False))
        elif choice == "17":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期（預設近30天）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_institutional_summary(code, start, end).to_string(index=False))
        elif choice == "18":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期（預設近60天）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_daily_kbar_finmind(code, start, end).to_string(index=False))
        elif choice == "19":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期（預設近60天）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_per_pbr(code, start, end).to_string(index=False))
        elif choice == "20":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期（預設近30天）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_day_trading(code, start, end).to_string(index=False))
        elif choice == "21":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期（預設近30天）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_margin_short(code, start, end).to_string(index=False))
        elif choice == "22":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期（預設近90天）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_shareholding(code, start, end).to_string(index=False))
        elif choice == "23":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期（預設近30天）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_securities_lending(code, start, end).to_string(index=False))
        elif choice == "24":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期（預設2025-01-01）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_month_revenue(code, start, end).to_string(index=False))
        elif choice == "25":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期（預設2024-01-01）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_financial_statements(code, start, end).to_string(index=False))
        elif choice == "26":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期（預設2024-01-01）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_balance_sheet(code, start, end).to_string(index=False))
        elif choice == "27":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期（預設2015-01-01）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_dividend(code, start, end).to_string(index=False))
        elif choice == "28":
            code  = _input("期貨代號（TX=台指/MTX=小台，預設TX）：", "TX")
            start = _input("開始日期（預設近30天）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_futures_daily(code, start, end).to_string(index=False))
        elif choice == "29":
            code  = _input("期貨代號（TX=台指，預設TX）：", "TX")
            start = _input("開始日期（預設近30天）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_futures_institutional(code, start, end).to_string(index=False))
        elif choice == "30":
            cur   = _input("幣別（USD/JPY/EUR/CNY/HKD，預設USD）：", "USD")
            start = _input("開始日期（預設近30天）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_exchange_rate(cur, start, end).to_string(index=False))
        elif choice == "41":
            code = _input("篩選代號（不填則查全市場）：", None)
            df = query_twse_daily_all(code)
            print(df.to_string(index=False))
        elif choice == "42":
            code = _input("篩選代號（不填則查全市場）：", None)
            df = query_twse_bwibbu(code)
            print(df.to_string(index=False))
        elif choice == "43":
            code = _input("篩選代號（不填則查全市場）：", None)
            df = query_twse_institutional(code)
            print(df.to_string(index=False))
        elif choice == "44":
            print(query_twse_margin().to_string(index=False))
        elif choice == "45":
            code = _input("股票代號（如 2330）：", "2330")
            print(query_twse_company(code).to_string(index=False))
        elif choice == "46":
            df = query_twse_disposition()
            if df.empty:
                print("目前無處置有價證券")
            else:
                pd.set_option("display.max_colwidth", 30)
                print(df.to_string(index=False))
        elif choice == "47":
            df = query_twse_notice()
            if df.empty:
                print("今日無注意有價證券")
            else:
                print(df.to_string(index=False))
        elif choice == "31":
            print(query_futu_market_state().to_string(index=False))
        elif choice == "32":
            code  = _input("代碼（如 HK.00700 / US.AAPL）：", "HK.00700")
            start = _input("開始日期 YYYY-MM-DD：", str(date.today() - timedelta(days=30)))
            end   = _input("結束日期（預設今日）：", None)
            print(query_futu_kbar(code, start, end).to_string(index=False))
        elif choice == "33":
            mkt   = _input("市場 HK/US/SH/SZ（預設HK）：", "HK")
            raw   = _input("代碼逗號分隔（不填查全市場）：", None)
            codes = [c.strip() for c in raw.split(",")] if raw else []
            print(query_futu_basicinfo(mkt, codes).to_string(index=False))
        elif choice == "34":
            code = _input("代碼（如 HK.00700 / US.TSLA）：", "HK.00700")
            print(query_futu_capital_distribution(code).to_string(index=False))
        elif choice == "35":
            code = _input("代碼（如 HK.00700 / US.TSLA）：", "HK.00700")
            print(query_futu_capital_flow(code).to_string(index=False))
        elif choice == "36":
            mkt = _input("市場 HK/US（預設HK）：", "HK")
            print(query_futu_plate_list(mkt).to_string(index=False))
        elif choice == "37":
            pc = _input("板塊代碼（從選單36取得，如 HK.LIST1003）：", "HK.LIST1003")
            print(query_futu_plate_stocks(pc).to_string(index=False))
        elif choice == "38":
            raw = _input("代碼逗號分隔（如 HK.00700,US.AAPL）：", "HK.00700,US.AAPL")
            codes = [c.strip() for c in raw.split(",")]
            print(query_futu_owner_plate(codes).to_string(index=False))
        elif choice == "0":
            print("離開")
            break
        else:
            print("無效選項")

        input("\n按 Enter 返回選單...")


if __name__ == "__main__":
    main()
