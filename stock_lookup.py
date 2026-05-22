"""
股票代號查詢模組 — 支援中文名稱、英文別名輸入
使用方式：
    from stock_lookup import resolve_code
    code = resolve_code("台積電")    # "2330"
    code = resolve_code("蘋果")      # "AAPL"
    code = resolve_code("2330")      # "2330"（直接返回）
"""

import os
import re
import time
import requests
import pandas as pd
from datetime import date
from typing import Optional

# ══════════════════════════════════════════════════════════
# 美股常見中文 / 英文別名對照表
# ══════════════════════════════════════════════════════════
US_STOCK_ALIASES: dict[str, str] = {
    # 科技巨頭
    "蘋果": "AAPL", "apple": "AAPL",
    "微軟": "MSFT", "microsoft": "MSFT",
    "谷歌": "GOOGL", "google": "GOOGL", "字母": "GOOGL", "alphabet": "GOOGL",
    "亞馬遜": "AMZN", "amazon": "AMZN",
    "臉書": "META", "facebook": "META", "meta": "META",
    "特斯拉": "TSLA", "tesla": "TSLA",
    "輝達": "NVDA", "nvidia": "NVDA", "英偉達": "NVDA",
    "超微": "AMD", "amd": "AMD",
    "英特爾": "INTC", "intel": "INTC",
    "高通": "QCOM", "qualcomm": "QCOM",
    "博通": "AVGO", "broadcom": "AVGO",
    "台積電adr": "TSM", "tsmc adr": "TSM", "tsm": "TSM",
    "美光": "MU", "micron": "MU",
    "應材": "AMAT", "applied materials": "AMAT",
    "克雷達": "KLAC", "kla": "KLAC",
    "泛林": "LRCX", "lam research": "LRCX",
    "arm": "ARM", "安謀": "ARM",
    "台積電美股": "TSM",
    # 電動車
    "rivian": "RIVN", "理想汽車": "LI", "小鵬": "XPEV", "蔚來": "NIO",
    "比亞迪adr": "BYDDY",
    # 消費/電商
    "奈飛": "NFLX", "netflix": "NFLX",
    "迪士尼": "DIS", "disney": "DIS",
    "星巴克": "SBUX", "starbucks": "SBUX",
    "麥當勞": "MCD", "mcdonald": "MCD",
    "沃爾瑪": "WMT", "walmart": "WMT",
    "好市多": "COST", "costco": "COST",
    "耐吉": "NKE", "nike": "NKE",
    "阿里巴巴": "BABA", "alibaba": "BABA",
    "京東": "JD", "jd.com": "JD",
    "拼多多": "PDD", "pinduoduo": "PDD",
    # 金融
    "摩根大通": "JPM", "jp morgan": "JPM",
    "美國銀行": "BAC", "bank of america": "BAC",
    "高盛": "GS", "goldman sachs": "GS",
    "波克夏": "BRK.B", "berkshire": "BRK.B",
    "visa": "V", "mastercard": "MA",
    "貝萊德": "BLK", "blackrock": "BLK",
    # 半導體/設備
    "德儀": "TXN", "texas instruments": "TXN",
    "安森美": "ON", "onsemi": "ON",
    "邁威爾": "MRVL", "marvell": "MRVL",
    "意法半導體": "STM",
    # 其他科技
    "甲骨文": "ORCL", "oracle": "ORCL",
    "salesforce": "CRM",
    "adobe": "ADBE",
    "serviceNow": "NOW",
    "crowdstrike": "CRWD",
    "palantir": "PLTR",
    "snowflake": "SNOW",
    "datadog": "DDOG",
    "uber": "UBER",
    "lyft": "LYFT",
    "airbnb": "ABNB",
    "coinbase": "COIN",
    "robinhood": "HOOD",
    # ETF 常見
    "標普500": "SPY", "s&p 500": "SPY",
    "那斯達克": "QQQ", "nasdaq": "QQQ",
    "道瓊": "DIA",
    "半導體etf": "SOXX",
    "科技etf": "XLK",
    # 港股 (附 .HK)
    "騰訊": "0700.HK", "tencent": "0700.HK",
    "阿里巴巴港股": "9988.HK",
    "美團": "3690.HK", "meituan": "3690.HK",
    "小米": "1810.HK", "xiaomi": "1810.HK",
    "比亞迪": "1211.HK", "byd": "1211.HK",
    "中芯": "0981.HK", "smic": "0981.HK",
    "港交所": "0388.HK", "hkex": "0388.HK",
}

# ══════════════════════════════════════════════════════════
# 台股名稱快取
# ══════════════════════════════════════════════════════════
_tw_name_cache: dict[str, str] = {}      # {"台積電": "2330"}
_tw_cache_loaded_date: str = ""


def _load_tw_name_map() -> dict[str, str]:
    """
    讀取台股名稱→代號對照表。
    優先讀今日本地 CSV 快取，其次即時呼叫 TWSE API。
    """
    global _tw_name_cache, _tw_cache_loaded_date
    today = date.today().isoformat()

    if _tw_cache_loaded_date == today and _tw_name_cache:
        return _tw_name_cache

    # 嘗試讀本地 CSV（data/twse/daily_all/YYYY-MM-DD.csv）
    csv_path = os.path.join("data", "twse", "daily_all", f"{today}.csv")
    df = None

    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path, dtype=str, encoding="utf-8-sig")
        except Exception:
            pass

    # 如果沒有本地快取，呼叫 TWSE API
    if df is None or df.empty:
        try:
            resp = requests.get(
                "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
                timeout=15,
            )
            resp.raise_for_status()
            df = pd.DataFrame(resp.json())
        except Exception:
            return _tw_name_cache  # 回傳舊快取（或空）

    # 建立 名稱→代號 和 代號→代號 對照
    result = {}
    for _, row in df.iterrows():
        code = str(row.get("Code", "")).strip()
        name = str(row.get("Name", "")).strip()
        if code and name and len(code) >= 4:
            result[name] = code
            # 去掉空白/特殊字符的版本
            clean_name = re.sub(r"[\s　（）\(\)（）]", "", name)
            if clean_name != name:
                result[clean_name] = code

    _tw_name_cache = result
    _tw_cache_loaded_date = today
    return result


# ══════════════════════════════════════════════════════════
# 主查詢函數
# ══════════════════════════════════════════════════════════

def resolve_code(raw: str) -> str:
    """
    將使用者輸入（中文/英文名稱或代號）解析為標準股票代號。

    規則：
      1. 去除前後空白
      2. 如果是純數字（4-6碼）→ 台股代號，直接返回
      3. 如果是英文代號（含 .HK/.TW 後綴）→ 直接返回大寫
      4. 查美股中文/英文別名表
      5. 查台股名稱對照表（精確 → 包含 → 首字元）
      6. 都找不到 → 返回原始輸入（讓後續 API 自行報錯）
    """
    if not raw:
        return ""

    s = raw.strip()

    # 規則 2：純數字代號（台股）
    if re.fullmatch(r"\d{4,6}", s):
        return s

    # 規則 3：英文代號（AAPL、TSM、0700.HK 等）
    if re.fullmatch(r"[A-Za-z0-9]+(\.[A-Za-z]+)?", s):
        return s.upper()

    # 小寫化用於查美股
    s_lower = s.lower().strip()

    # 規則 4：美股別名（精確）
    if s_lower in US_STOCK_ALIASES:
        return US_STOCK_ALIASES[s_lower]
    if s in US_STOCK_ALIASES:
        return US_STOCK_ALIASES[s]

    # 規則 5：台股名稱
    tw_map = _load_tw_name_map()

    # 精確匹配
    if s in tw_map:
        return tw_map[s]

    # 去除括號/空白後精確匹配
    s_clean = re.sub(r"[\s　（）\(\)（）]", "", s)
    if s_clean in tw_map:
        return tw_map[s_clean]

    # 包含匹配（名稱包含輸入字串）
    for name, code in tw_map.items():
        if s_clean and s_clean in name:
            return code

    # 美股別名模糊（輸入是某個別名的子集）
    for alias, ticker in US_STOCK_ALIASES.items():
        if s_lower in alias or alias in s_lower:
            return ticker

    # 找不到，返回原始輸入
    return s


def resolve_codes(raw: str, sep: str = ",") -> list[str]:
    """批量解析：'台積電,AAPL,聯發科' → ['2330','AAPL','2454']"""
    parts = [p.strip() for p in raw.split(sep) if p.strip()]
    return [resolve_code(p) for p in parts]


def get_name_hint(raw: str) -> Optional[str]:
    """
    回傳解析提示字串，讓 UI 顯示「台積電 → 2330」。
    如果無法解析（直接返回原始值），回傳 None。
    """
    if not raw:
        return None
    resolved = resolve_code(raw.strip())
    if resolved.upper() != raw.strip().upper() and resolved != raw.strip():
        return f"{raw.strip()} → **{resolved}**"
    return None


def resolve_us_stock(raw: str) -> str:
    """
    將使用者輸入（中文/英文名稱或代號）解析為美股標準代號。
    如果本地字典沒有，則背景呼叫 DeepSeek AI 自動翻譯。
    """
    if not raw:
        return ""
    
    s = raw.strip()
    
    s_lower = s.lower()
    
    # 本地字典精確匹配
    if s_lower in US_STOCK_ALIASES:
        return US_STOCK_ALIASES[s_lower]
    if s in US_STOCK_ALIASES:
        return US_STOCK_ALIASES[s]
        
    # 英文代號直接回傳 (限制長度 1-5 碼，避免把長英文名稱當成代號)
    if re.fullmatch(r"[A-Za-z0-9]{1,5}(\.[A-Za-z]{1,2})?", s):
        return s.upper()
        
    # 本地字典模糊匹配 (避免過短的字串引發誤判)
    if len(s_lower) >= 2:
        for alias, ticker in US_STOCK_ALIASES.items():
            if s_lower in alias or alias in s_lower:
                return ticker
            
    # AI Fallback: 呼叫 DeepSeek
    try:
        from deepseek_engine import get_deepseek_engine
        engine = get_deepseek_engine()
        if engine and engine.client:
            prompt = f"使用者想查詢美股「{s}」，請你判斷它對應的美股股票代號 (Ticker) 是什麼？請只回答純大寫英文代號字串，不要加任何其他廢話或解釋。如果找不到或不確定，請回答 UNKNOWN。"
            response = engine.client.chat.completions.create(
                model=engine.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=10
            )
            ai_result = response.choices[0].message.content.strip().upper()
            
            # 去除可能包含的多餘符號 (如句號)
            ai_result = re.sub(r"[^A-Z0-9\.]", "", ai_result)
            
            if ai_result and ai_result != "UNKNOWN":
                # 把結果快取起來避免重複打 API
                US_STOCK_ALIASES[s_lower] = ai_result
                return ai_result
    except Exception as e:
        import logging
        logging.warning(f"AI 解析美股代號失敗: {e}")
        
    return s

def get_us_name_hint(raw: str) -> Optional[str]:
    if not raw:
        return None
    resolved = resolve_us_stock(raw.strip())
    if resolved.upper() != raw.strip().upper() and resolved != raw.strip():
        return f"{raw.strip()} → **{resolved}** (US)"
    return None
