"""
永豐金 Shioaji API 資料來源客戶端 — 負責行情、合約、大單分析與帳務查詢
"""

import sys
import os
import pandas as pd
import yfinance as yf
from datetime import date
from logging_config import main_logger
from datasources.twse_client import query_twse_daily_all

try:
    import shioaji as sj
    HAS_SHIOAJI = True
except ImportError:
    HAS_SHIOAJI = False


def _has_shioaji() -> bool:
    """動態取得 HAS_SHIOAJI 狀態，優先讀取被 Mock 的 sinopac_query 模組屬性"""
    if "sinopac_query" in sys.modules:
        sq = sys.modules["sinopac_query"]
        if hasattr(sq, "HAS_SHIOAJI"):
            return sq.HAS_SHIOAJI
    return HAS_SHIOAJI


def _get_sinopac_config():
    """從 config.json 載入永豐金 API 設定"""
    try:
        from config import load_config
        cfg = load_config()
        return (
            cfg.get("api_key", ""),
            cfg.get("secret_key", ""),
            cfg.get("simulation_mode", True)
        )
    except Exception:
        return "", "", True


class ShioajiConnectionPool:
    """永豐金 Shioaji API 連線池管理器（單例模式）"""
    _instance = None
    _api = None
    _fetch_contract = True

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ShioajiConnectionPool, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_api(cls, fetch_contract: bool = True):
        if not _has_shioaji():
            raise RuntimeError("環境中未安裝 Shioaji 庫，無法進行券商連線。")

        api_key, secret_key, simulation = _get_sinopac_config()
        if not api_key or not secret_key:
            raise RuntimeError("未設定券商 API 金鑰，請至側邊欄『系統設定』填寫。")

        pool = cls()
        if cls._api is None:
            cls._api = sj.Shioaji(simulation=simulation)
            cls._api.login(api_key=api_key, secret_key=secret_key, fetch_contract=fetch_contract)
            cls._fetch_contract = fetch_contract
        else:
            if fetch_contract != cls._fetch_contract:
                try:
                    cls._api.logout()
                except Exception:
                    pass
                cls._api = sj.Shioaji(simulation=simulation)
                cls._api.login(api_key=api_key, secret_key=secret_key, fetch_contract=fetch_contract)
                cls._fetch_contract = fetch_contract
        return cls._api

    @classmethod
    def close(cls):
        if cls._api is not None:
            try:
                cls._api.logout()
            except Exception:
                pass
            cls._api = None


def login(fetch_contract: bool = True):
    """登入並取得 Shioaji API 實例（具備單元測試 Mock 動態路由）"""
    if "sinopac_query" in sys.modules:
        sq = sys.modules["sinopac_query"]
        if hasattr(sq, "login") and sq.login != login:
            return sq.login(fetch_contract=fetch_contract)
    return ShioajiConnectionPool.get_api(fetch_contract=fetch_contract)


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


def query_ticks(
    code: str,
    query_date: str,
    market: str = "Stocks",
    time_start: str = None,
    time_end: str = None,
    last_cnt: int = None,
) -> pd.DataFrame:
    """逐筆成交（動態支援永豐金 Shioaji API）"""
    if not _has_shioaji():
        return pd.DataFrame({"說明": ["環境中未安裝 Shioaji 庫，不支援逐筆成交。請在本地/NAS端安裝：pip install shioaji"]})
    try:
        api = login(fetch_contract=True)
        if market == "Stocks":
            contract = api.Contracts.Stocks[code]
        elif market == "Futures":
            contract = api.Contracts.Futures[code]
        else:
            contract = api.Contracts.Options[code]

        kwargs = {"contract": contract, "date": query_date}
        if time_start and time_end:
            from shioaji.constant import TicksQueryType
            kwargs["query_type"] = TicksQueryType.RangeTime
            kwargs["time_start"] = time_start
            kwargs["time_end"] = time_end
        elif last_cnt:
            from shioaji.constant import TicksQueryType
            kwargs["query_type"] = TicksQueryType.LastCount
            kwargs["last_cnt"] = last_cnt

        ticks = api.ticks(**kwargs)
        if not ticks or not ticks.close:
            return pd.DataFrame()
        return pd.DataFrame({**ticks}).set_index("ts")
    except Exception as e:
        return pd.DataFrame({"說明": [f"❌ 逐筆成交查詢失敗: {e}"]})


def query_shioaji_snapshot(codes: list) -> pd.DataFrame:
    """即時快照與最佳五檔（動態支援永豐金 Shioaji API）"""
    if not _has_shioaji():
        return pd.DataFrame({"說明": ["環境中未安裝 Shioaji 庫，不支援即時快照。請在本地/NAS端安裝：pip install shioaji"]})
    try:
        api = login(fetch_contract=True)
        contracts = []
        for code in codes:
            code = code.strip()
            if not code:
                continue
            if code in api.Contracts.Stocks:
                contracts.append(api.Contracts.Stocks[code])

        if not contracts:
            return pd.DataFrame({"說明": ["查無對應的股票合約資訊，請檢查股票代號。"]})

        snapshots = api.snapshots(contracts)
        if not snapshots:
            return pd.DataFrame()

        data = []
        for s in snapshots:
            bid_p = getattr(s, "buy_price", getattr(s, "bid_price", []))
            bid_v = getattr(s, "buy_volume", getattr(s, "bid_volume", []))
            ask_p = getattr(s, "ask_price", getattr(s, "sell_price", []))
            ask_v = getattr(s, "ask_volume", getattr(s, "sell_volume", []))

            row = {
                "代號": s.code,
                "名稱": api.Contracts.Stocks[s.code].name if s.code in api.Contracts.Stocks else s.code,
                "開盤": s.open,
                "最高": s.high,
                "最低": s.low,
                "收盤": s.close,
                "昨收": s.yesterday_close,
                "漲跌": s.change,
                "漲跌幅(%)": round(s.change_rate * 100, 2) if hasattr(s, "change_rate") else 0.0,
                "單量": s.volume,
                "總量": s.total_volume,
                "委買價": bid_p,
                "委買量": bid_v,
                "委賣價": ask_p,
                "委賣量": ask_v,
            }
            data.append(row)

        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame({"說明": [f"❌ 快照查詢失敗: {e}"]})


def query_shioaji_kbars(
    code: str,
    start_date: str,
    end_date: str = None,
    resolution: str = "1min",
) -> pd.DataFrame:
    """多週期盤中/歷史 K 線（動態支援永豐金 Shioaji API）"""
    if not _has_shioaji():
        return pd.DataFrame({"說明": ["環境中未安裝 Shioaji 庫，不支援分K線。請在本地/NAS端安裝：pip install shioaji"]})
    try:
        api = login(fetch_contract=True)
        if code not in api.Contracts.Stocks:
            return pd.DataFrame({"說明": [f"查無股票代號 {code} 的合約資訊"]})
        contract = api.Contracts.Stocks[code]

        import shioaji as sj
        res_map = {
            "1min": sj.constant.KBarTimeResolution.Min1,
            "5min": sj.constant.KBarTimeResolution.Min5,
            "15min": sj.constant.KBarTimeResolution.Min15,
            "30min": sj.constant.KBarTimeResolution.Min30,
            "60min": sj.constant.KBarTimeResolution.Min60,
            "1d": sj.constant.KBarTimeResolution.Day,
        }
        sj_res = res_map.get(resolution, sj.constant.KBarTimeResolution.Min1)

        if not end_date:
            end_date = str(date.today())

        kbars = api.kbars(
            contract=contract,
            start_date=start_date,
            end_date=end_date,
            resolution=sj_res
        )
        if not kbars or not kbars.close:
            return pd.DataFrame()

        df = pd.DataFrame({**kbars})
        df.index = pd.to_datetime(df["ts"])
        df.index.name = "ts"
        df = df.drop(columns=["ts"])

        col_map = {
            "open": "開盤",
            "high": "最高",
            "low": "最低",
            "close": "收盤",
            "volume": "成交量"
        }
        df = df.rename(columns=col_map)
        return df
    except Exception as e:
        return pd.DataFrame({"說明": [f"❌ 分K線查詢失敗: {e}"]})


def query_shioaji_contract_info(code: str) -> pd.DataFrame:
    """商品官方合約與交易限制（動態支援永豐金 Shioaji API）"""
    if not _has_shioaji():
        return pd.DataFrame({"說明": ["環境中未安裝 Shioaji 庫，不支援合約查詢。請在本地/NAS端安裝：pip install shioaji"]})
    try:
        api = login(fetch_contract=True)
        if code not in api.Contracts.Stocks:
            return pd.DataFrame({"說明": [f"查無股票代號 {code} 的官方合約資訊。"]})
        c = api.Contracts.Stocks[code]

        day_trade_val = getattr(c, "day_trade", "N/A")
        day_trade_str = "可現股當沖 (資券互抵)" if str(day_trade_val) in ["Yes", "DayTrade.Yes", "1"] else "不可當沖"

        info = {
            "屬性": [
                "股票代號", "股票名稱", "交易所", "產業類別",
                "是否可信用融資", "是否可信用融券", "融資成數/比率", "融券保證金成數",
                "現股當沖/資券互抵", "今日參考價", "今日漲停價", "今日跌停價"
            ],
            "官方設定值": [
                getattr(c, "code", code),
                getattr(c, "name", "N/A"),
                getattr(c, "exchange", "N/A"),
                getattr(c, "category", "N/A"),
                "是" if getattr(c, "margin", False) else "否",
                "是" if getattr(c, "short_selling", False) else "否",
                f"{int(getattr(c, 'margin_rate', 0.0) * 100)}%" if getattr(c, 'margin_rate', 0.0) else "N/A",
                f"{int(getattr(c, 'short_selling_rate', 0.0) * 100)}%" if getattr(c, 'short_selling_rate', 0.0) else "N/A",
                day_trade_str,
                getattr(c, "reference", "N/A"),
                getattr(c, "limit_up", "N/A"),
                getattr(c, "limit_down", "N/A")
            ]
        }
        return pd.DataFrame(info)
    except Exception as e:
        return pd.DataFrame({"說明": [f"❌ 合約查詢失敗: {e}"]})


def analyze_shioaji_big_orders(
    code: str,
    query_date: str,
    threshold_volume: int = 50,
    threshold_amount: float = 5000000.0
) -> dict:
    """逐筆成交 ticks 大單分析（動態支援永豐金 Shioaji API）"""
    if not _has_shioaji():
        err_df = pd.DataFrame({"說明": ["環境中未安裝 Shioaji 庫，不支援大單分析。請在本地/NAS端安裝：pip install shioaji"]})
        return {"summary": pd.DataFrame(), "detail": err_df}
    try:
        api = login(fetch_contract=True)
        if code not in api.Contracts.Stocks:
            err_df = pd.DataFrame({"說明": [f"查無股票代號 {code} 的合約資訊。"]})
            return {"summary": pd.DataFrame(), "detail": err_df}
        contract = api.Contracts.Stocks[code]

        ticks = api.ticks(contract=contract, date=query_date)
        if not ticks or not ticks.close:
            err_df = pd.DataFrame({"說明": [f"📅 {query_date} 該股票無逐筆成交資料。"]})
            return {"summary": pd.DataFrame(), "detail": err_df}

        df = pd.DataFrame({**ticks})
        df["ts"] = pd.to_datetime(df["ts"])
        df["金額"] = df["close"] * df["volume"] * 1000

        df_big = df[(df["volume"] >= threshold_volume) | (df["金額"] >= threshold_amount)].copy()

        total_ticks = len(df)
        total_volume = df["volume"].sum()
        total_amount = df["金額"].sum()

        big_buy = df_big[df_big["tick_type"] == 1]
        big_sell = df_big[df_big["tick_type"] == 2]

        big_buy_cnt = len(big_buy)
        big_buy_vol = big_buy["volume"].sum()
        big_buy_amt = big_buy["金額"].sum()

        big_sell_cnt = len(big_sell)
        big_sell_vol = big_sell["volume"].sum()
        big_sell_amt = big_sell["金額"].sum()

        net_buy_amt = big_buy_amt - big_sell_amt

        summary_info = {
            "指標項目": [
                "總成交筆數", "總成交張數", "總成交金額 (元)",
                "主力大單買入筆數", "主力大單買入張數", "主力大單買入金額 (元)",
                "主力大單賣出筆數", "主力大單賣出張數", "主力大單賣出金額 (元)",
                "主力大單淨流入金額 (元)", "大單佔總成交金額比例(%)"
            ],
            "數值": [
                total_ticks, total_volume, round(total_amount, 2),
                big_buy_cnt, big_buy_vol, round(big_buy_amt, 2),
                big_sell_cnt, big_sell_vol, round(big_sell_amt, 2),
                round(net_buy_amt, 2),
                round(((big_buy_amt + big_sell_amt) / total_amount * 100), 2) if total_amount > 0 else 0.0
            ]
        }

        df_big_show = df_big.sort_values("ts", ascending=False).head(50).copy()
        if not df_big_show.empty:
            df_big_show["時間"] = df_big_show["ts"].dt.strftime("%H:%M:%S")
            df_big_show["買賣方向"] = df_big_show["tick_type"].map({1: "🔴 主動買入(外盤)", 2: "🟢 主動賣出(內盤)"}).fillna("⚪ 中性/盤後")
            df_big_show = df_big_show.rename(columns={
                "close": "成交價",
                "volume": "成交張數"
            })
            df_result = df_big_show[["時間", "成交價", "成交張數", "金額", "買賣方向"]].reset_index(drop=True)
        else:
            df_result = pd.DataFrame(columns=["時間", "成交價", "成交張數", "金額", "買賣方向"])

        return {
            "summary": pd.DataFrame(summary_info),
            "detail": df_result
        }
    except Exception as e:
        err_df = pd.DataFrame({"說明": [f"❌ 大單分析失敗: {e}"]})
        return {"summary": pd.DataFrame(), "detail": err_df}


# ── 帳務相關功能 ──

def _check_shioaji_accounting() -> bool:
    if not _has_shioaji():
        return False
    return True


_ACCOUNTING_ERR = "❌ 環境中未安裝 Shioaji 庫，不支援帳務功能。請在本地/NAS端安裝：pip install shioaji"


def query_positions(account_type: str = "stock", *args, **kwargs) -> pd.DataFrame:
    if not _check_shioaji_accounting():
        return pd.DataFrame({"說明": [_ACCOUNTING_ERR]})
    try:
        api = login(fetch_contract=False)
        account = api.stock_account if account_type == "stock" else api.futopt_account
        positions = api.list_positions(account)
        return pd.DataFrame([p.dict() for p in positions]) if positions else pd.DataFrame()
    except Exception as e:
        return pd.DataFrame({"說明": [f"❌ 查詢庫存失敗: {e}"]})


def query_position_detail(code: str, account_type: str = "stock", *args, **kwargs) -> pd.DataFrame:
    if not _check_shioaji_accounting():
        return pd.DataFrame({"說明": [_ACCOUNTING_ERR]})
    try:
        api = login(fetch_contract=True)
        account = api.stock_account if account_type == "stock" else api.futopt_account
        contract = api.Contracts.Stocks[code] if account_type == "stock" else None
        details = api.list_position_detail(account, contract)
        return pd.DataFrame([d.dict() for d in details]) if details else pd.DataFrame()
    except Exception as e:
        return pd.DataFrame({"說明": [f"❌ 查詢庫存明細失敗: {e}"]})


def query_profit_loss(
    begin_date: str = None,
    end_date: str = None,
    account_type: str = "stock",
    *args, **kwargs
) -> pd.DataFrame:
    if not _check_shioaji_accounting():
        return pd.DataFrame({"說明": [_ACCOUNTING_ERR]})
    try:
        from datetime import date as dt_date
        if begin_date is None:
            begin_date = str(dt_date.today())
        if end_date is None:
            end_date = str(dt_date.today())
        api = login(fetch_contract=False)
        account = api.stock_account if account_type == "stock" else api.futopt_account
        pnl = api.list_profit_loss(account, begin_date=begin_date, end_date=end_date)
        return pd.DataFrame([p.dict() for p in pnl]) if pnl else pd.DataFrame()
    except Exception as e:
        return pd.DataFrame({"說明": [f"❌ 查詢已實現損益失敗: {e}"]})


def query_profit_loss_summary(
    begin_date: str = None,
    end_date: str = None,
    account_type: str = "stock",
    *args, **kwargs
) -> pd.DataFrame:
    if not _check_shioaji_accounting():
        return pd.DataFrame({"說明": [_ACCOUNTING_ERR]})
    try:
        from datetime import date as dt_date
        if begin_date is None:
            begin_date = str(dt_date.today())
        if end_date is None:
            end_date = str(dt_date.today())
        api = login(fetch_contract=False)
        account = api.stock_account if account_type == "stock" else api.futopt_account
        summary = api.list_profit_loss_summary(account, begin_date=begin_date, end_date=end_date)
        return pd.DataFrame([s.dict() for s in summary]) if summary else pd.DataFrame()
    except Exception as e:
        return pd.DataFrame({"說明": [f"❌ 查詢已實現損益彙總失敗: {e}"]})


def query_account_balance(*args, **kwargs) -> dict:
    if not _check_shioaji_accounting():
        return {"說明": _ACCOUNTING_ERR}
    try:
        api = login(fetch_contract=False)
        balance = api.account_balance()
        return balance.dict() if balance else {}
    except Exception as e:
        return {"說明": f"❌ 查詢銀行餘額失敗: {e}"}


def query_margin(*args, **kwargs) -> dict:
    if not _check_shioaji_accounting():
        return {"說明": _ACCOUNTING_ERR}
    try:
        api = login(fetch_contract=False)
        margin = api.margin(api.futopt_account)
        return margin.dict() if margin else {}
    except Exception as e:
        return {"說明": f"❌ 查詢期貨保證金失敗: {e}"}


def query_trading_limits(*args, **kwargs) -> dict:
    if not _check_shioaji_accounting():
        return {"說明": _ACCOUNTING_ERR}
    try:
        api = login(fetch_contract=False)
        limits = api.trading_limits(api.stock_account)
        return limits.dict() if limits else {}
    except Exception as e:
        return {"說明": f"❌ 查詢交易額度限制失敗: {e}"}


def query_settlements(*args, **kwargs) -> pd.DataFrame:
    if not _check_shioaji_accounting():
        return pd.DataFrame({"說明": [_ACCOUNTING_ERR]})
    try:
        api = login(fetch_contract=False)
        settlements = api.settlements(api.stock_account)
        return pd.DataFrame([s.dict() for s in settlements]) if settlements else pd.DataFrame()
    except Exception as e:
        return pd.DataFrame({"說明": [f"❌ 查詢交割款明細失敗: {e}"]})
