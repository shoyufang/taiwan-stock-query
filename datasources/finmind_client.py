"""
FinMind 資料來源客戶端 — 負責技術、籌碼、基本面、期指與匯率之歷史數據查詢
"""

import os
import requests
import pandas as pd
import yfinance as yf
from FinMind.data import DataLoader
from datetime import datetime, date, timedelta
from logging_config import main_logger

_SESSION = requests.Session()


def get_finmind_token() -> str:
    """取得 FinMind Token（動態由 get_secret 載入）"""
    from config import get_secret
    return get_secret("FINMIND_TOKEN")


# 為了向後相容保留的模組級別屬性
FINMIND_TOKEN = get_finmind_token()


class FinMindConnectionPool:
    """FinMind 連線池管理器（單例模式）"""
    _instance = None
    _api = None
    _current_token = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FinMindConnectionPool, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_api(cls) -> DataLoader:
        token = get_finmind_token()
        if cls._api is None or token != cls._current_token:
            cls._api = DataLoader()
            cls._api.login_by_token(api_token=token)
            cls._current_token = token
        return cls._api


def _finmind() -> DataLoader:
    """取得 FinMind DataLoader 實例"""
    return FinMindConnectionPool.get_api()


def _finmind_api(dataset: str, data_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """直接呼叫 FinMind REST API（DataLoader 未封裝的 dataset 用此函式）"""
    token = get_finmind_token()
    r = _SESSION.get(
        "https://api.finmindtrade.com/api/v4/data",
        params={"dataset": dataset, "data_id": data_id,
                "start_date": start_date, "end_date": end_date,
                "token": token},
        timeout=15,
    )
    d = r.json()
    if d.get("status") != 200:
        raise ValueError(d.get("msg", "API 錯誤"))
    return pd.DataFrame(d["data"])


def query_institutional(
    code: str,
    start_date: str = None,
    end_date: str = None,
) -> pd.DataFrame:
    """
    三大法人買賣超（免費）。
    回傳欄位：date, name, buy, sell, net（買超=buy-sell）
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
    df["net"] = df["buy"] - df["sell"]
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
    if start_date is None:
        start_date = str(date.today() - timedelta(days=30))
    if end_date is None:
        end_date = str(date.today())
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
    if start_date is None:
        start_date = str(date.today() - timedelta(days=90))
    if end_date is None:
        end_date = str(date.today())
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
    if start_date is None:
        start_date = str(date.today() - timedelta(days=30))
    if end_date is None:
        end_date = str(date.today())
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
    if start_date is None:
        start_date = str(date.today() - timedelta(days=60))
    if end_date is None:
        end_date = str(date.today())
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
    if start_date is None:
        start_date = str(date.today() - timedelta(days=30))
    if end_date is None:
        end_date = str(date.today())
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
    if start_date is None:
        start_date = "2025-01-01"
    if end_date is None:
        end_date = str(date.today())
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


def query_financial_statement(code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """綜合損益表（免費，1990年起）"""
    if start_date is None:
        start_date = "2024-01-01"
    if end_date is None:
        end_date = str(date.today())
    df = _finmind().taiwan_stock_financial_statement(
        stock_id=code, start_date=start_date, end_date=end_date
    )
    df = df.rename(columns={"date": "日期", "type": "科目", "value": "金額"})
    return df[["開盤", "最高", "最低", "收盤", "漲跌", "成交量(股)", "成交金額", "成交筆數"]] if df.empty else df[["日期", "科目", "金額"]]


# 為了向後相容定義的複數別名
query_financial_statements = query_financial_statement


def query_balance_sheet(code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """資產負債表（免費，2011年起）"""
    if start_date is None:
        start_date = "2024-01-01"
    if end_date is None:
        end_date = str(date.today())
    df = _finmind().taiwan_stock_balance_sheet(
        stock_id=code, start_date=start_date, end_date=end_date
    )
    df = df.rename(columns={"date": "日期", "type": "科目", "value": "金額"})
    return df[["日期", "科目", "金額"]]


def query_dividend(code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """股利政策（免費，2005年起）"""
    if start_date is None:
        start_date = "2015-01-01"
    if end_date is None:
        end_date = str(date.today())
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
    if start_date is None:
        start_date = str(date.today() - timedelta(days=30))
    if end_date is None:
        end_date = str(date.today())
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


def query_futures_institutional(code: str = "TX", start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """期貨三大法人（免費，2018年起）"""
    if start_date is None:
        start_date = str(date.today() - timedelta(days=30))
    if end_date is None:
        end_date = str(date.today())
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
    """台灣銀行匯率（免費）。若 FinMind 失效則自動 Fallback 到 yfinance 國際外匯歷史數據。"""
    if start_date is None:
        start_date = str(date.today() - timedelta(days=30))
    if end_date is None:
        end_date = str(date.today())

    try:
        df = _finmind_api("TaiwanExchangeRate", currency, start_date, end_date)
        if df is None or df.empty:
            raise ValueError("FinMind 回傳空數據")

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

    except Exception as e:
        main_logger.warning(f"從 FinMind 獲取匯率失敗 ({str(e)})，啟動 yfinance Fallback 備用防線...")
        try:
            cur_upper = currency.upper()
            ticker_symbol = "TWD=X" if cur_upper == "USD" else f"{cur_upper}TWD=X"

            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(start=start_date, end=end_date)
            if not hist.empty:
                rows = []
                for ts, row in hist.iterrows():
                    date_str = ts.strftime("%Y-%m-%d")
                    close_val = round(float(row["Close"]), 4)
                    rows.append({
                        "日期": date_str,
                        "幣別": cur_upper,
                        "現金買入": close_val,
                        "現金賣出": close_val,
                        "即期買入": close_val,
                        "即期賣出": close_val
                    })
                df_fallback = pd.DataFrame(rows)
                main_logger.info(f"yfinance Fallback 匯率抓取成功！共 {len(df_fallback)} 筆數據")
                return df_fallback
        except Exception as yf_err:
            main_logger.error(f"yfinance Fallback 匯率抓取也失敗: {str(yf_err)}")

        return pd.DataFrame(columns=["日期", "幣別", "現金買入", "現金賣出", "即期買入", "即期賣出"])
