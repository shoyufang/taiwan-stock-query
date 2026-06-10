"""
證交所 TWSE API 資料來源客戶端 — 負責當日行情、估值、法人、資券、公司資料、處置/注意股與 ESG 資訊查詢
"""

import requests as _requests
import pandas as pd
from datetime import date
from logging_config import main_logger

_SESSION = _requests.Session()
_TWSE = "https://openapi.twse.com.tw/v1"


def _twse_get(path: str) -> pd.DataFrame:
    """
    呼叫 TWSE 新版 OpenAPI。
    注意：Streamlit Cloud（海外 IP）可能被 TWSE 限流，回傳空 body 或 HTML。
    """
    r = _SESSION.get(f"{_TWSE}{path}", timeout=15,
                     headers={"Accept": "application/json"})
    r.raise_for_status()

    # 先排除明顯的 HTML 回覆
    if not r.text or r.text.strip().startswith("<!"):
        raise RuntimeError(
            "TWSE OpenAPI 回傳空白或 HTML（可能因海外 IP 被限制）。\n"
            "今日資料將於 20:05 自動快取後可查詢，或請稍後再試。"
        )

    try:
        data = r.json()
    except ValueError:
        raise RuntimeError(
            "TWSE OpenAPI 回傳非 JSON 格式（可能因海外 IP 被限制）。\n"
            "今日資料將於 20:05 自動快取後可查詢，或請稍後再試。"
        )

    return pd.DataFrame(data)


def _twse_old(path: str, params: dict = None) -> pd.DataFrame:
    """舊版 TWSE REST API（www.twse.com.tw/rwd/zh/...）"""
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
    rows = data.get("data", [])
    if not rows:
        return pd.DataFrame(columns=fields if fields else [])
    return pd.DataFrame(rows, columns=fields) if fields else pd.DataFrame(rows)


def query_twse_daily_all(code: str = None) -> pd.DataFrame:
    """全市場上市個股當日收盤行情（TWSE OpenAPI，免費）"""
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
    """全市場上市個股本益比、殖利率及股價淨值比（當日）"""
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
    """三大法人買賣超（全市場，當日）"""
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
        "住址": "地址",
        "營利事業統一編號": "統一編號",
        "上市日期": "上市日期",
        "上櫃日期": "上市日期"
    })
    cols = ["代號", "名稱", "英文名稱", "產業別", "地址", "統一編號", "董事長", "發言人", "發言人職稱", "上市日期"]
    if "產業別" in df.columns:
        cols[3] = "產業別"
    return df[[c for c in cols if c in df.columns]]


def query_twse_company(code: str) -> pd.DataFrame:
    """上市公司、上櫃公司與興櫃公司基本資料 (整合 TWSE OpenAPI 與 MOPS OpenData)"""
    code = str(code).strip()

    # 方案 A: 優先使用本機的 TWSE OpenAPI 查詢上市公司 JSON
    try:
        df = _twse_get("/opendata/t187ap03_L")
        if not df.empty and "公司代號" in df.columns:
            df["公司代號"] = df["公司代號"].astype(str).str.strip()
            match_df = df[df["公司代號"] == code]
            if not match_df.empty:
                return _process_company_df(match_df)
    except Exception as e:
        main_logger.warning(f"TWSE OpenAPI 查詢失敗，將嘗試公開資訊觀測站備用方案: {e}")

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
        except Exception:
            continue

    return pd.DataFrame()


def query_twse_disposition() -> pd.DataFrame:
    """公布處置有價證券（當前生效清單）"""
    df = _twse_old("announcement/punish")
    if df.empty:
        return df
    keep = ["證券代號", "證券名稱", "累計", "處置條件", "處置起迄時間", "公布日期"]
    return df[[c for c in keep if c in df.columns]]


def query_twse_notice() -> pd.DataFrame:
    """公布注意有價證券（當日注意股清單）"""
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
    """上市公司綜合損益表。"""
    return _twse_get(f"/opendata/t187ap06_X_{industry}")


def query_twse_balance_sheet_openapi(industry: str = "ci") -> pd.DataFrame:
    """上市公司資產負債表（TWSE OpenAPI）。"""
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
    """上市公司 ESG 揭露（指定主題）。"""
    return _twse_get(f"/opendata/t187ap46_L_{topic_id}")
