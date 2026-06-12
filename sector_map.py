"""
Phase H: 產業對照表 + 族群熱力圖

提供 代號 → 產業別 對照。
資料來源：TWSE OpenAPI（每檔一筆，帶 cache）
"""
import numpy as np

import pandas as pd
from loguru import logger

from datasources.twse_client import query_twse_company
from query_wrapper import cached_query


# TWSE OpenAPI 產業別代碼簡易映射
SECTOR_NAMES = {
    "24": "半導體/積體電路", "25": "光電/顯示器",
    "28": "化學工業", "31": "半導體", "32": "光電",
    "02": "塑膠工業", "01": "水泥工業", "03": "紡織纖維",
    "11": "金融保險", "13": "鋼鐵", "15": "貿易貨販",
    "99": "其他股票", "ETF": "ETF",
}


@cached_query(ttl=86400, sqlite_ttl=604800, name="sector_map")
def get_sector_map() -> pd.DataFrame:
    """
    產業對照表：代號 → 產業別代碼。
    每檔呼叫 query_twse_company（含內部 cache），快取命中極快。
    回傳 DataFrame: [公司代號, 公司名稱, 產業別代碼, 來源]
    """
    import query_wrapper as qw
    daily = qw.query_twse_daily_all()
    if daily.empty:
        return pd.DataFrame(columns=["公司代號", "公司名稱", "產業別代碼", "來源"])

    if "Code" in daily.columns:
        all_codes = daily["Code"].astype(str).str.replace(r'[A-Z]+$', '', regex=True).str.strip().unique().tolist()
    else:
        all_codes = daily.iloc[:, 0].astype(str).str.zfill(4).unique().tolist()

    rows = []
    batch = []
    for code in all_codes:
        batch.append(code)
        if len(batch) >= 100:
            rows.extend(_batch_query(batch))
            batch = []
    if batch:
        rows.extend(_batch_query(batch))

    if not rows:
        return pd.DataFrame(columns=["公司代號", "公司名稱", "產業別代碼", "來源"])

    return pd.DataFrame(rows)


def _batch_query(codes: list) -> list:
    """批次查詢單檔基本資料"""
    rows = []
    for code in codes:
        try:
            df = query_twse_company(code)
            if not df.empty and len(df) > 0:
                row = df.iloc[0]
                rows.append({
                    "公司代號": str(row.iloc[0]).strip(),
                    "公司名稱": str(row.iloc[1]).strip() if len(row) > 1 else "",
                    "產業別代碼": str(row.iloc[3]).strip() if len(row) > 3 else "",
                    "來源": "TWSE API",
                })
        except Exception:
            continue
    return rows


def get_code_to_sector() -> dict:
    """代號 → 產業別代碼（快速查表）"""
    df = get_sector_map()
    if df.empty:
        return {}
    return dict(zip(df["公司代號"], df["產業別代碼"]))


def get_stocks_by_sector(sector_code: str) -> pd.DataFrame:
    """查詢某產業的所有股票"""
    df = get_sector_map()
    if df.empty:
        return pd.DataFrame()
    return df[df["產業別代碼"] == sector_code][["公司代號", "公司名稱"]].reset_index(drop=True)


def get_unique_sectors() -> list:
    """取得所有不重複的產業別代碼"""
    df = get_sector_map()
    if df.empty:
        return []
    return sorted(df["產業別代碼"].unique().tolist())


def get_sector_heatmap_data() -> pd.DataFrame:
    """聚合各產業今日行情：成交金額加權平均漲跌幅 + 成交金額合計"""
    import query_wrapper as qw

    daily = qw.query_twse_daily_all()
    if daily.empty:
        return pd.DataFrame()

    sector_df = get_sector_map()
    if sector_df.empty:
        return pd.DataFrame()

    # 統一欄位名
    col_map = {}
    if "Code" in daily.columns:
        col_map["Code"] = "代號"
    if "TradeValue" in daily.columns:
        col_map["TradeValue"] = "成交金額"
    if "Change" in daily.columns:
        col_map["Change"] = "漲跌幅%"

    if col_map:
        daily = daily.rename(columns=col_map)

    if "代號" in daily.columns:
        daily["代號"] = daily["代號"].astype(str).str.replace(r'[A-Z]+$', '', regex=True).str.strip()

    merged = daily.merge(
        sector_df[["公司代號", "公司名稱", "產業別代碼"]],
        left_on="代號", right_on="公司代號", how="left"
    )

    sector_merged = merged.dropna(subset=["產業別代碼"])
    if sector_merged.empty:
        return pd.DataFrame()

    if "成交金額" in sector_merged.columns:
        sector_merged["成交金額"] = pd.to_numeric(sector_merged["成交金額"], errors="coerce")
    if "漲跌幅%" in sector_merged.columns:
        sector_merged["漲跌幅%"] = pd.to_numeric(sector_merged["漲跌幅%"], errors="coerce")

    result = sector_merged.groupby(["產業別代碼"]).agg(
        加權漲跌幅=("漲跌幅%", lambda x: np.average(
            x.dropna(),
            weights=sector_merged.loc[x.dropna().index, "成交金額"].dropna()
        ) if len(x.dropna()) > 0 else 0),
        成交金額合計=("成交金額", "sum"),
        股票數=("代號", "count")
    ).reset_index()

    return result


def get_sector_name(sector_code: str) -> str:
    """產業別代碼 → 中文名稱（簡易映射）"""
    return SECTOR_NAMES.get(str(sector_code), str(sector_code))


def get_sector_name(sector_code: str) -> str:
    """產業別代碼 → 中文名稱（簡易映射）"""
    return SECTOR_NAMES.get(sector_code, sector_code)
