"""
Gemini AI 引擎 — Phase 7 Task 7.5 (SDK 升級版)
使用最新的 google-genai SDK 提供智能查詢與分析
"""

import os
import re
import time
from typing import Dict, Any, List, Optional, Callable
import pandas as pd
import query_wrapper as qw
from logging_config import main_logger
from datetime import date, datetime, timedelta
from google import genai
from google.genai import types


def _extract_retry_delay(err_str: str, default: float = 15.0) -> float:
    """從 429 錯誤訊息中解析 retryDelay 秒數"""
    m = re.search(r"['\"]retryDelay['\"]\s*:\s*['\"](\d+(?:\.\d+)?)s['\"]", err_str)
    if m:
        return float(m.group(1))
    # 備援：直接抓數字後跟 s
    m2 = re.search(r"retry in (\d+(?:\.\d+)?)s", err_str, re.IGNORECASE)
    if m2:
        return float(m2.group(1))
    return default


def _is_rate_limit_error(err_str: str) -> bool:
    return "429" in err_str or "RESOURCE_EXHAUSTED" in err_str


def _is_transient_error(err_str: str) -> bool:
    """503 超載 / 502 / 暫時性錯誤（值得短暫等待後重試）"""
    return (
        "503" in err_str or "UNAVAILABLE" in err_str or
        "502" in err_str or "high demand" in err_str.lower() or
        "temporarily" in err_str.lower()
    )


def _call_with_retry(fn: Callable, max_retries: int = 3) -> Any:
    """
    執行 fn()，遇到可重試錯誤時自動等待並重試：
    - 429 速率限制：等待 API 指定的 retryDelay
    - 503 超載：短暫等待 3s 後重試（最多 2 次，之後交給 fallback 處理）
    """
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            err_str = str(e)
            if _is_rate_limit_error(err_str) and attempt < max_retries - 1:
                delay = _extract_retry_delay(err_str, default=15.0 * (2 ** attempt))
                main_logger.warning(
                    f"Gemini 速率限制（429），等待 {delay:.0f}s 後重試 "
                    f"（第 {attempt + 1}/{max_retries - 1} 次）"
                )
                time.sleep(delay)
            elif _is_transient_error(err_str) and attempt < 1:
                # 503 只重試一次（3秒後），失敗就讓外層做 model fallback
                main_logger.warning(f"Gemini 503 暫時超載，等待 3s 後重試...")
                time.sleep(3)
            else:
                raise


# ── 工具包裝函式（DataFrame → str，讓 Gemini 可讀） ────────────────────

def _df_to_str(df: pd.DataFrame) -> str:
    """把 DataFrame 轉成 Gemini 可讀的文字表格"""
    if df is None or df.empty:
        return "（查無資料）"
    try:
        return df.to_string(index=False, max_rows=80)
    except Exception:
        return str(df)


def tool_query_ranking(ranking_type: str, limit: int = 20) -> str:
    """
    查詢台股市場排行榜。
    ranking_type: "up"=漲幅排行, "down"=跌幅排行, "volume"=成交量排行, "amount"=成交金額排行
    limit: 筆數，預設 20
    """
    df = qw.query_ranking(ranking_type, limit)
    return _df_to_str(df)


def tool_query_snapshot(codes: List[str]) -> str:
    """
    查詢個股即時快照（收盤價、漲跌幅、成交量等）。
    codes: 台股代號列表，例如 ["2330", "2412"]，上限 500 檔
    """
    df = qw.query_snapshot(codes)
    return _df_to_str(df)


def tool_query_daily_kbar(code: str, start_date: str, end_date: str) -> str:
    """
    查詢個股日K線（開高低收、成交量）。
    code: 台股代號，例如 "2330"
    start_date: 開始日期，格式 YYYY-MM-DD
    end_date: 結束日期，格式 YYYY-MM-DD
    """
    try:
        s = date.fromisoformat(start_date)
        e = date.fromisoformat(end_date)
    except Exception:
        return "日期格式錯誤，請用 YYYY-MM-DD"
    df = qw.query_daily_kbar(code, s, e)
    return _df_to_str(df)


def tool_query_institutional_investors(code: str, start_date: str, end_date: str) -> str:
    """
    查詢個股三大法人（外資、投信、自營商）歷史買賣超明細。
    code: 台股代號，例如 "2330"
    start_date: 開始日期，格式 YYYY-MM-DD
    end_date: 結束日期，格式 YYYY-MM-DD
    """
    try:
        s = date.fromisoformat(start_date)
        e = date.fromisoformat(end_date)
    except Exception:
        return "日期格式錯誤，請用 YYYY-MM-DD"
    df = qw.query_institutional_investors(code, s, e)
    return _df_to_str(df)


def tool_query_month_revenue(code: str, start_date: str, end_date: str) -> str:
    """
    查詢個股月營收歷史資料（2002年起）。
    code: 台股代號，例如 "2330"
    start_date: 開始日期，格式 YYYY-MM-DD
    end_date: 結束日期，格式 YYYY-MM-DD
    """
    try:
        s = date.fromisoformat(start_date)
        e = date.fromisoformat(end_date)
    except Exception:
        return "日期格式錯誤，請用 YYYY-MM-DD"
    df = qw.query_month_revenue(code, s, e)
    return _df_to_str(df)


def tool_query_financial_statement(code: str, start_date: str, end_date: str) -> str:
    """
    查詢個股綜合損益表（季報，含營業收入、稅後淨利、EPS 等）。
    code: 台股代號，例如 "2330"
    start_date: 開始日期，格式 YYYY-MM-DD
    end_date: 結束日期，格式 YYYY-MM-DD
    """
    try:
        s = date.fromisoformat(start_date)
        e = date.fromisoformat(end_date)
    except Exception:
        return "日期格式錯誤，請用 YYYY-MM-DD"
    df = qw.query_financial_statement(code, s, e)
    return _df_to_str(df)


def tool_query_futu_market_state() -> str:
    """
    查詢全球各大市場（香港、美國、上海、深圳等）當前開收盤狀態。
    """
    df = qw.query_futu_market_state()
    return _df_to_str(df)


def tool_query_exchange_rate(currency: str, start_date: str, end_date: str) -> str:
    """
    查詢台銀歷史匯率。
    currency: 幣別代碼，例如 "USD"、"JPY"、"EUR"、"CNY"、"HKD"
    start_date: 開始日期，格式 YYYY-MM-DD
    end_date: 結束日期，格式 YYYY-MM-DD
    """
    try:
        s = date.fromisoformat(start_date)
        e = date.fromisoformat(end_date)
    except Exception:
        return "日期格式錯誤，請用 YYYY-MM-DD"
    df = qw.query_exchange_rate(currency, s, e)
    return _df_to_str(df)


def tool_query_stock_news(code: str, limit: int = 10) -> str:
    """
    查詢個股最新新聞（Yahoo Finance，英文）。
    code: 台股代號（或 ^TWII 查大盤），例如 "2330"
    limit: 筆數，預設 10
    """
    df = qw.query_stock_news(code, limit)
    return _df_to_str(df)


def tool_query_margin_short(code: str, start_date: str, end_date: str) -> str:
    """
    查詢個股融資融券餘額歷史資料。
    code: 台股代號，例如 "2330"
    start_date: 開始日期，格式 YYYY-MM-DD
    end_date: 結束日期，格式 YYYY-MM-DD
    """
    try:
        s = date.fromisoformat(start_date)
        e = date.fromisoformat(end_date)
    except Exception:
        return "日期格式錯誤，請用 YYYY-MM-DD"
    df = qw.query_margin_short(code, s, e)
    return _df_to_str(df)


def tool_query_twse_institutional(code: Optional[str] = None) -> str:
    """
    查詢當日全市場三大法人買賣超（TWSE 即時資料）。
    code: 可選，篩選特定股票代號；不填則回傳全市場
    """
    df = qw.query_twse_institutional(code)
    return _df_to_str(df)


def tool_query_twse_valuation(code: Optional[str] = None) -> str:
    """
    查詢當日全市場本益比、殖利率、股淨比（TWSE 即時資料）。
    code: 可選，篩選特定股票代號；不填則回傳全市場
    """
    df = qw.query_twse_valuation(code)
    return _df_to_str(df)


# ── GeminiEngine 類別 ────────────────────────────────────────────────────

class GeminiEngine:
    """Gemini 智能查詢 engine (使用新版 google-genai SDK)"""

    FALLBACK_MODELS = [
        "gemini-3.5-flash",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    ]

    # 舊 preview 版本 → 新正式版對照表
    _MODEL_ALIASES = {
        "gemini-2.5-flash-preview-05-20": "gemini-2.5-flash",
        "gemini-2.5-flash-preview-04-17": "gemini-2.5-flash",
        "gemini-2.5-pro-preview-05-06":   "gemini-2.5-pro",
        "gemini-2.5-pro-preview-03-25":   "gemini-2.5-pro",
        "gemini-2.0-flash-exp":           "gemini-2.0-flash",
        "gemini-1.5-flash-002":           "gemini-1.5-flash",
        "gemini-1.5-pro-002":             "gemini-1.5-pro",
        "gemini-3.0-flash":               "gemini-2.5-flash",  # 不存在，回退
        "gemini-3.0-pro":                 "gemini-2.5-pro",
    }

    @classmethod
    def _resolve_model(cls, model_name: str) -> str:
        """將舊/已下線的模型名稱自動對應到現有版本"""
        if not model_name:
            return cls.FALLBACK_MODELS[0]
        # 精確對照
        if model_name in cls._MODEL_ALIASES:
            resolved = cls._MODEL_ALIASES[model_name]
            main_logger.warning(f"模型 '{model_name}' 已下線，自動改用 '{resolved}'")
            return resolved
        return model_name

    def __init__(self, api_key: str, model_name: str = ""):
        self.api_key = api_key
        self.model_name = self._resolve_model(model_name)
        if not api_key or not self.model_name:
            self.client = None
            return
        try:
            self.client = genai.Client(api_key=api_key)
            main_logger.info(f"Gemini Engine 初始化成功: {self.model_name}")
        except Exception as e:
            main_logger.error(f"Gemini Engine 初始化失敗: {str(e)}")
            self.client = None

    @staticmethod
    def list_available_models(api_key: str) -> List[str]:
        """列出該 API Key 可用的模型（回傳 API model ID）"""
        if not api_key:
            return []
        try:
            client = genai.Client(api_key=api_key)
            main_logger.info("正在從 Google API 獲取可用模型清單...")
            models = []
            for m in client.models.list():
                raw_name = getattr(m, 'name', '') or ''
                api_id = raw_name[7:] if raw_name.startswith('models/') else raw_name
                if not api_id or 'gemini' not in api_id.lower() or '-' not in api_id:
                    continue
                supported = getattr(m, 'supported_actions', None) or getattr(m, 'supported_methods', None) or []
                if supported and 'generateContent' not in str(supported):
                    continue
                models.append(api_id)
                main_logger.debug(f"偵測到可用模型: {api_id}")
            if not models:
                main_logger.warning("API 未回傳可用模型，使用保底清單")
                return GeminiEngine.FALLBACK_MODELS[:]
            return sorted(list(set(models)))
        except Exception as e:
            main_logger.error(f"獲取 Gemini 模型列表失敗: {str(e)}")
            return GeminiEngine.FALLBACK_MODELS[:]

    def _get_tools(self) -> List[Any]:
        """工具清單 — 全部回傳 str，讓 Gemini 自動函式調用可正常序列化"""
        return [
            tool_query_ranking,
            tool_query_snapshot,
            tool_query_daily_kbar,
            tool_query_institutional_investors,
            tool_query_month_revenue,
            tool_query_financial_statement,
            tool_query_futu_market_state,
            tool_query_exchange_rate,
            tool_query_stock_news,
            tool_query_margin_short,
            tool_query_twse_institutional,
            tool_query_twse_valuation,
        ]

    def smart_query(self, user_input: str) -> Dict[str, Any]:
        """執行智能查詢 (新版 SDK 自動函式調用)"""
        if not self.client:
            return {"error": "Gemini API Key 或模型未設定"}

        main_logger.info(f"[GEMINI SMART QUERY] 用戶輸入: {user_input}")

        today = date.today()
        default_start = (today - timedelta(days=30)).isoformat()
        default_end = today.isoformat()

        system_context = (
            f"你是一個專業的台股/港美股分析助手，今天是 {today}。"
            f"預設查詢日期範圍：{default_start} 到 {default_end}（若用戶未指定）。\n"
            "你有以下本地工具可直接調用獲取精確數據：\n"
            "- tool_query_ranking：台股漲跌幅/成交量排行\n"
            "- tool_query_snapshot：個股即時報價快照\n"
            "- tool_query_daily_kbar：個股日K線\n"
            "- tool_query_institutional_investors：三大法人歷史買賣超\n"
            "- tool_query_twse_institutional：當日全市場三大法人\n"
            "- tool_query_month_revenue：月營收\n"
            "- tool_query_financial_statement：季報損益表\n"
            "- tool_query_margin_short：融資融券餘額\n"
            "- tool_query_futu_market_state：全球市場開收盤狀態\n"
            "- tool_query_exchange_rate：台銀匯率\n"
            "- tool_query_stock_news：個股新聞\n"
            "- tool_query_twse_valuation：本益比/殖利率\n\n"
            "規則：\n"
            "1. 優先調用本地工具取得精確數據，再進行分析。\n"
            "2. 本地工具不足時，使用 Google Search 補充網路資訊。\n"
            "3. 回覆使用繁體中文，提供專業且有深度的分析。\n"
            "4. 若工具回傳『查無資料』，請說明可能原因（如非交易日、代號錯誤等）。"
        )

        tools = self._get_tools()
        contents = f"{system_context}\n\n用戶問題：{user_input}"

        def _do_call():
            # 優先嘗試加入 Google Search
            try:
                tools_with_search = tools + [types.Tool(google_search=types.GoogleSearch())]
                return self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        tools=tools_with_search,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(),
                    ),
                )
            except Exception as e_inner:
                if _is_rate_limit_error(str(e_inner)):
                    raise  # 讓外層 retry 處理
                main_logger.warning(f"Google Search 不可用，降級為純本地工具: {e_inner}")
                return self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        tools=tools,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(),
                    ),
                )

        try:
            response = _call_with_retry(_do_call, max_retries=3)
            answer = response.text or "（AI 無回應，請重試）"
            return {"analysis": answer, "raw_response": response}

        except Exception as e:
            err_str = str(e)
            main_logger.error(f"Gemini 執行查詢失敗: {err_str}")

            # 模型不可用（404 不存在 / 503 超載）→ 自動嘗試 FALLBACK_MODELS
            _should_fallback = (
                "404" in err_str or "NOT_FOUND" in err_str or "not found" in err_str.lower() or
                "503" in err_str or "UNAVAILABLE" in err_str or "unavailable" in err_str.lower() or
                "high demand" in err_str.lower()
            )
            if _should_fallback:
                reason = "不存在" if ("404" in err_str or "NOT_FOUND" in err_str) else "暫時超載"
                main_logger.warning(f"模型 '{self.model_name}' {reason}，嘗試回退模型...")
                for fallback in self.FALLBACK_MODELS:
                    if fallback == self.model_name:
                        continue
                    try:
                        self.model_name = fallback
                        main_logger.info(f"切換至回退模型: {fallback}")
                        response = _call_with_retry(_do_call, max_retries=2)
                        answer = response.text or "（AI 無回應，請重試）"
                        return {
                            "analysis": answer,
                            "raw_response": response,
                            "model_fallback": fallback,
                        }
                    except Exception as fe:
                        # 回退模型也超載就繼續下一個
                        if "503" in str(fe) or "UNAVAILABLE" in str(fe):
                            main_logger.warning(f"回退模型 {fallback} 也超載，繼續...")
                            continue
                        break
                return {"error": f"所有模型均暫時不可用，請稍後再試。\n\n原始錯誤：{err_str}"}

            return {"error": f"AI 查詢發生異常: {err_str}"}

    def summarize_news(self, news_text: str, subject: str = "") -> Dict[str, Any]:
        """
        將英文新聞翻譯並摘要成繁體中文投資分析。
        news_text: 新聞原文（標題+摘要的純文字）
        subject: 查詢主題，例如 "台積電(2330)" 或 "台股大盤"
        """
        if not self.client:
            return {"error": "Gemini API Key 或模型未設定"}

        topic = f"關於【{subject}】的" if subject else ""
        prompt = (
            f"以下是{topic}英文財經新聞，請你：\n"
            "1. 用繁體中文逐則摘要（保留原文時間與來源）\n"
            "2. 最後加上「📊 投資觀點」：綜合這些消息，對投資人有什麼啟示或需要注意的風險\n\n"
            f"新聞原文：\n{news_text}"
        )
        try:
            response = _call_with_retry(
                lambda: self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                ),
                max_retries=3,
            )
            return {"analysis": response.text or "（AI 無回應）"}
        except Exception as e:
            main_logger.error(f"Gemini 新聞摘要失敗: {str(e)}")
            return {"error": str(e)}


def get_gemini_engine() -> Optional[GeminiEngine]:
    """快捷獲取引擎實例"""
    from config import load_config
    cfg = load_config()
    api_key = cfg.get("gemini_api_key", "")
    model_name = cfg.get("gemini_model", "")
    if api_key and model_name:
        return GeminiEngine(api_key, model_name=model_name)
    return None
