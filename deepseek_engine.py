"""
DeepSeek AI 引擎 — Phase 7 (取代 Gemini)
使用 openai SDK 連線至 DeepSeek API，提供智能查詢與分析
"""

import os
import re
import time
import json
import inspect
from typing import Dict, Any, List, Optional, Callable
import pandas as pd
import query_wrapper as qw
from logging_config import main_logger
from datetime import date, datetime, timedelta
from openai import OpenAI

# ── 工具包裝函式（DataFrame → str，讓 AI 可讀） ────────────────────

def _df_to_str(df: pd.DataFrame) -> str:
    """把 DataFrame 轉成 AI 可讀的文字表格"""
    if df is None or df.empty:
        return "（查無資料）"
    try:
        return df.to_string(index=False, max_rows=80)
    except Exception:
        return str(df)


def tool_query_ranking(ranking_type: str, limit: int = 20) -> str:
    """查詢台股市場排行榜。ranking_type: "up"=漲幅, "down"=跌幅, "volume"=成交量, "amount"=成交金額"""
    df = qw.query_ranking(ranking_type, limit)
    return _df_to_str(df)


def tool_query_snapshot(codes: List[str]) -> str:
    """查詢個股即時快照（收盤價、漲跌幅、成交量等）。codes: 台股代號列表"""
    df = qw.query_snapshot(codes)
    return _df_to_str(df)


def tool_query_daily_kbar(code: str, start_date: str, end_date: str) -> str:
    """查詢個股日K線。"""
    try:
        s = date.fromisoformat(start_date)
        e = date.fromisoformat(end_date)
    except Exception:
        return "日期格式錯誤，請用 YYYY-MM-DD"
    df = qw.query_daily_kbar(code, s, e)
    return _df_to_str(df)


def tool_query_institutional_investors(code: str, start_date: str, end_date: str) -> str:
    """查詢個股三大法人（外資、投信、自營商）歷史買賣超明細。"""
    try:
        s = date.fromisoformat(start_date)
        e = date.fromisoformat(end_date)
    except Exception:
        return "日期格式錯誤，請用 YYYY-MM-DD"
    df = qw.query_institutional_investors(code, s, e)
    return _df_to_str(df)


def tool_query_month_revenue(code: str, start_date: str, end_date: str) -> str:
    """查詢個股月營收歷史資料。"""
    try:
        s = date.fromisoformat(start_date)
        e = date.fromisoformat(end_date)
    except Exception:
        return "日期格式錯誤，請用 YYYY-MM-DD"
    df = qw.query_month_revenue(code, s, e)
    return _df_to_str(df)


def tool_query_financial_statement(code: str, start_date: str, end_date: str) -> str:
    """查詢個股綜合損益表（季報）。"""
    try:
        s = date.fromisoformat(start_date)
        e = date.fromisoformat(end_date)
    except Exception:
        return "日期格式錯誤，請用 YYYY-MM-DD"
    df = qw.query_financial_statement(code, s, e)
    return _df_to_str(df)


def tool_query_futu_market_state() -> str:
    """查詢全球各大市場開收盤狀態。"""
    df = qw.query_futu_market_state()
    return _df_to_str(df)


def tool_query_exchange_rate(currency: str, start_date: str, end_date: str) -> str:
    """查詢台銀歷史匯率。currency: 幣別代碼，例如 USD, JPY"""
    try:
        s = date.fromisoformat(start_date)
        e = date.fromisoformat(end_date)
    except Exception:
        return "日期格式錯誤，請用 YYYY-MM-DD"
    df = qw.query_exchange_rate(currency, s, e)
    return _df_to_str(df)


def tool_query_stock_news(code: str, limit: int = 10) -> str:
    """查詢個股最新新聞。"""
    df = qw.query_stock_news(code, limit)
    return _df_to_str(df)


def tool_query_margin_short(code: str, start_date: str, end_date: str) -> str:
    """查詢個股融資融券餘額歷史資料。"""
    try:
        s = date.fromisoformat(start_date)
        e = date.fromisoformat(end_date)
    except Exception:
        return "日期格式錯誤，請用 YYYY-MM-DD"
    df = qw.query_margin_short(code, s, e)
    return _df_to_str(df)


def tool_query_twse_institutional(code: Optional[str] = None) -> str:
    """查詢當日全市場三大法人買賣超（TWSE 即時資料）。"""
    df = qw.query_twse_institutional(code)
    return _df_to_str(df)


def tool_query_twse_valuation(code: Optional[str] = None) -> str:
    """查詢當日全市場本益比、殖利率、股淨比（TWSE 即時資料）。"""
    df = qw.query_twse_valuation(code)
    return _df_to_str(df)


# 定義所有可用工具的字典映射
_TOOL_FUNCTIONS = {
    "tool_query_ranking": tool_query_ranking,
    "tool_query_snapshot": tool_query_snapshot,
    "tool_query_daily_kbar": tool_query_daily_kbar,
    "tool_query_institutional_investors": tool_query_institutional_investors,
    "tool_query_month_revenue": tool_query_month_revenue,
    "tool_query_financial_statement": tool_query_financial_statement,
    "tool_query_futu_market_state": tool_query_futu_market_state,
    "tool_query_exchange_rate": tool_query_exchange_rate,
    "tool_query_stock_news": tool_query_stock_news,
    "tool_query_margin_short": tool_query_margin_short,
    "tool_query_twse_institutional": tool_query_twse_institutional,
    "tool_query_twse_valuation": tool_query_twse_valuation,
}

_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "tool_query_ranking",
            "description": "查詢台股市場排行榜。",
            "parameters": {
                "type": "object",
                "properties": {
                    "ranking_type": {"type": "string", "description": "\"up\"=漲幅排行, \"down\"=跌幅排行, \"volume\"=成交量排行, \"amount\"=成交金額排行"},
                    "limit": {"type": "integer", "description": "筆數，預設 20"}
                },
                "required": ["ranking_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tool_query_snapshot",
            "description": "查詢個股即時快照（收盤價、漲跌幅、成交量等）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "codes": {"type": "array", "items": {"type": "string"}, "description": "台股代號列表，例如 [\"2330\", \"2412\"]"}
                },
                "required": ["codes"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tool_query_daily_kbar",
            "description": "查詢個股日K線（開高低收、成交量）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "台股代號，例如 \"2330\""},
                    "start_date": {"type": "string", "description": "開始日期，格式 YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "結束日期，格式 YYYY-MM-DD"}
                },
                "required": ["code", "start_date", "end_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tool_query_institutional_investors",
            "description": "查詢個股三大法人（外資、投信、自營商）歷史買賣超明細。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"}
                },
                "required": ["code", "start_date", "end_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tool_query_month_revenue",
            "description": "查詢個股月營收歷史資料。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"}
                },
                "required": ["code", "start_date", "end_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tool_query_financial_statement",
            "description": "查詢個股綜合損益表（季報）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"}
                },
                "required": ["code", "start_date", "end_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tool_query_futu_market_state",
            "description": "查詢全球各大市場開收盤狀態。",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tool_query_exchange_rate",
            "description": "查詢台銀歷史匯率。",
            "parameters": {
                "type": "object",
                "properties": {
                    "currency": {"type": "string", "description": "幣別代碼，例如 USD, JPY"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"}
                },
                "required": ["currency", "start_date", "end_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tool_query_stock_news",
            "description": "查詢個股最新新聞。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "台股代號"},
                    "limit": {"type": "integer", "description": "筆數，預設 10"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tool_query_margin_short",
            "description": "查詢個股融資融券餘額歷史資料。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"}
                },
                "required": ["code", "start_date", "end_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tool_query_twse_institutional",
            "description": "查詢當日全市場三大法人買賣超（TWSE 即時資料）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "可選，篩選特定股票代號"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tool_query_twse_valuation",
            "description": "查詢當日全市場本益比、殖利率、股淨比（TWSE 即時資料）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "可選，篩選特定股票代號"}
                }
            }
        }
    }
]


# ── DeepSeekEngine 類別 ────────────────────────────────────────────────────

class DeepSeekEngine:
    """DeepSeek 智能查詢 engine (相容於 OpenAI 格式)"""

    FALLBACK_MODELS = [
        "deepseek-v4-flash",
        "deepseek-v4-pro",
        "deepseek-chat",     # V3
        "deepseek-reasoner", # R1
    ]

    def __init__(self, api_key: str, model_name: str = ""):
        self.api_key = api_key
        self.model_name = model_name if model_name else self.FALLBACK_MODELS[0]
        
        if not api_key:
            self.client = None
            return
            
        try:
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com"
            )
            main_logger.info(f"DeepSeek Engine 初始化成功: {self.model_name}")
        except Exception as e:
            main_logger.error(f"DeepSeek Engine 初始化失敗: {str(e)}")
            self.client = None

    @staticmethod
    def list_available_models(api_key: str) -> List[str]:
        """列出該 API Key 可用的模型"""
        if not api_key:
            return []
        try:
            client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
            main_logger.info("正在從 DeepSeek API 獲取可用模型清單...")
            models = client.models.list()
            model_ids = sorted([m.id for m in models.data])
            if not model_ids:
                return DeepSeekEngine.FALLBACK_MODELS[:]
            return model_ids
        except Exception as e:
            main_logger.error(f"獲取 DeepSeek 模型列表失敗: {str(e)}")
            return DeepSeekEngine.FALLBACK_MODELS[:]

    def smart_query(self, user_input: str) -> Dict[str, Any]:
        """執行智能查詢 (自動函式調用)"""
        if not self.client:
            return {"error": "DeepSeek API Key 或模型未設定"}

        main_logger.info(f"[DEEPSEEK SMART QUERY] 用戶輸入: {user_input}")

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
            "1. 必須優先調用本地工具取得精確數據，再進行分析。\n"
            "2. 回覆使用繁體中文，提供專業且有深度的分析。\n"
            "3. 若工具回傳『查無資料』，請說明可能原因（如非交易日、代號錯誤等）。\n"
            "4. 不要瞎掰數據，沒有資料就說沒有資料。"
        )

        messages = [
            {"role": "system", "content": system_context},
            {"role": "user", "content": user_input}
        ]

        try:
            # 第一次對話，請求調用工具
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=_TOOL_SCHEMAS,
                tool_choice="auto"
            )
            
            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls
            
            # 處理多次工具調用
            if tool_calls:
                messages.append(response_message)
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    main_logger.info(f"DeepSeek 調用工具: {function_name}，參數: {function_args}")
                    
                    if function_name in _TOOL_FUNCTIONS:
                        function_to_call = _TOOL_FUNCTIONS[function_name]
                        try:
                            function_response = function_to_call(**function_args)
                        except Exception as e:
                            function_response = f"呼叫工具時發生錯誤: {str(e)}"
                    else:
                        function_response = f"找不到指定的工具: {function_name}"
                        
                    messages.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": function_response,
                        }
                    )
                
                # 發送包含工具結果的第二次對話請求
                second_response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                )
                answer = second_response.choices[0].message.content or "（AI 無回應，請重試）"
                return {"analysis": answer, "raw_response": str(second_response)}

            else:
                answer = response_message.content or "（AI 無回應，請重試）"
                return {"analysis": answer, "raw_response": str(response)}

        except Exception as e:
            err_str = str(e)
            main_logger.error(f"DeepSeek 執行查詢失敗: {err_str}")
            return {"error": f"AI 查詢發生異常: {err_str}"}

    def summarize_news(self, news_text: str, subject: str = "") -> Dict[str, Any]:
        """將英文新聞翻譯並摘要成繁體中文投資分析。"""
        if not self.client:
            return {"error": "DeepSeek API Key 或模型未設定"}

        topic = f"關於【{subject}】的" if subject else ""
        prompt = (
            f"以下是{topic}英文財經新聞，請你：\n"
            "1. 用繁體中文逐則摘要（保留原文時間與來源）\n"
            "2. 最後加上「📊 投資觀點」：綜合這些消息，對投資人有什麼啟示或需要注意的風險\n\n"
            f"新聞原文：\n{news_text}"
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            return {"analysis": response.choices[0].message.content or "（AI 無回應）"}
        except Exception as e:
            main_logger.error(f"DeepSeek 新聞摘要失敗: {str(e)}")
            return {"error": str(e)}


def get_deepseek_engine() -> Optional[DeepSeekEngine]:
    """快捷獲取引擎實例"""
    from config import load_config
    cfg = load_config()
    api_key = cfg.get("deepseek_api_key", "")
    model_name = cfg.get("deepseek_model", "")
    if api_key and model_name:
        return DeepSeekEngine(api_key, model_name=model_name)
    return None
