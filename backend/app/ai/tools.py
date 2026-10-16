"""AI 助理可用的工具：本站資料（site_*）＋自架 TWStockMCPServer 的精選工具。

TWStockMCPServer 有約 170 個工具，全部交給模型會吃掉大量上下文且容易選錯，
這裡只開放與個股研究、大盤、籌碼、行事曆相關的一組（名稱以伺服器 tools/list 為準，找不到的自動略過）。
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.ai.mcp_client import McpClient
from app.api_portfolio import get_portfolio
from app.api_watchlist import get_watchlist
from app.services import stock_loader as loader

MAX_RESULT_CHARS = 8000

MCP_ALLOW = [
    # 個股基本面
    "get_company_profile", "get_company_monthly_revenue", "get_company_income_statement",
    "get_company_balance_sheet", "get_company_dividend", "get_company_major_news",
    "get_stock_valuation_ratios", "get_industry_peers", "get_company_eps_statistics",
    # 價格與技術
    "get_stock_history", "get_technical_indicators", "get_realtime_quote",
    # 籌碼
    "get_twse_institutional_investors_by_stock", "get_margin_balance", "get_foreign_holdings",
    "get_shareholding_distribution",
    # 上櫃
    "get_otc_daily", "get_otc_index", "get_otc_institutional",
    # 大盤與總經
    "get_market_index_info", "get_taiex_index_history", "get_futures_institutional",
    "get_put_call_ratio", "get_business_cycle_indicators", "get_taiwan_pmi",
    # 事件
    "get_investor_conferences", "get_dividend_rights_schedule", "get_market_disposal_stocks",
    "get_today_notice_stocks", "get_twse_news",
    # ETF
    "get_etf_holdings", "get_etf_info",
]


def _fn(name: str, description: str, properties: dict | None = None, required: list[str] | None = None) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties or {}, "required": required or []}}}


CODE_PARAM = {"code": {"type": "string", "description": "股票代號，例如 2330"}}

SITE_TOOLS = [
    _fn("site_market_overview", "本站市場總覽（最近交易日收盤）：加權指數、櫃買指數、漲跌家數、成交金額、三大法人、成交值與漲跌幅排行、外資買賣超排行、國際市場。"),
    _fn("site_stock", "本站個股資料：最近收盤（盤中有即時價時一併提供）、盤後摘要、近 15 日法人、融資券、集保大戶／散戶股權分散、近 12 月營收、本益比歷史位置。", CODE_PARAM, ["code"]),
    _fn("site_stock_fundamentals", "本站個股基本面深度資料：近 12 季損益表（毛利率／營益率／淨利率／EPS）、資產負債表（ROE／ROA／負債比）、歷年股利與配發率、五年 PER／PBR 分位數、同產業同業比較。", CODE_PARAM, ["code"]),
    _fn("site_screener", "本站多因子與技術選股總表：可依技術訊號（如 ma_bull、kd_gold、macd_bull、high_20d、vol_2x、rsi_oversold）、產業、台灣 50 篩選並排序。", {
        "signal": {"type": "string", "description": "選填，技術訊號 ID，例如 ma_bull、kd_gold、macd_bull、high_20d、vol_2x、rsi_oversold"},
        "industry": {"type": "string", "description": "選填，產業名稱，例如 半導體業"},
        "top50_only": {"type": "boolean", "description": "選填，是否只看台灣 50 成分股"},
        "sort": {"type": "string", "description": "選填，排序欄位：foreign_5d、trust_5d、dividend_yield、rev_yoy、change_pct、pe（預設 foreign_5d）"},
        "limit": {"type": "integer", "description": "選填，回傳筆數上限（預設 15，最大 40）"},
    }),
    _fn("site_attention", "本站上市櫃處置股與注意股名單（含處置期間、分盤撮合分鐘數、注意原因與觸發條款）。",
        {"code": {"type": "string", "description": "選填，指定股票代號查詢"}}),
    _fn("site_us_stocks", "本站美股觀察（科技巨頭、AI／半導體、台灣 ADR 報價與本益比）與近期美股財報日曆。",
        {"symbol": {"type": "string", "description": "選填，指定美股代號如 NVDA、TSM"}}),
    _fn("site_watchlist", "使用者的自選股清單與最近報價。"),
    _fn("site_portfolio", "使用者手動輸入的持股（股數、每股成本）與最近收盤。"),
    _fn("site_calendar", "本站投資行事曆：除權息、法說會、法定公布期限（今天前 7 天到後 60 天）。可指定代號只看該股。",
        {"code": {"type": "string", "description": "選填，股票代號"}}),
]


def _trim(obj) -> str:
    text = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, default=str)
    return text if len(text) <= MAX_RESULT_CHARS else text[:MAX_RESULT_CHARS] + "…（已截斷）"


async def run_site_tool(app, name: str, args: dict) -> str:
    s = app.state
    req = SimpleNamespace(app=app)
    if name == "site_market_overview":
        raw = await s.redis.get("overview:latest")
        if not raw:
            return "市場總覽尚未準備好"
        d = json.loads(raw)
        d.pop("index_series", None)
        return _trim(d)
    if name == "site_stock":
        code = str(args.get("code", "")).strip().upper()
        try:
            page = await loader.load_page(s.store, s.finmind, s.redis, code)
        except loader.StockNotFound:
            return f"找不到股票 {code}"
        live = await s.redis.get(f"q:last:{code}")
        if live:
            page["live_quote"] = json.loads(live)
        return _trim(page)
    if name == "site_stock_fundamentals":
        code = str(args.get("code", "")).strip().upper()
        try:
            data = await loader.load_fundamentals(s.store, s.finmind, s.redis, code)
        except loader.StockNotFound:
            return f"找不到股票 {code}"
        return _trim(data)
    if name == "site_screener":
        raw = await s.redis.get("screener:base")
        if not raw:
            return "選股總表尚未準備好"
        base = json.loads(raw)
        rows = base.get("rows", [])
        sig = str(args.get("signal") or "").strip()
        ind = str(args.get("industry") or "").strip()
        if args.get("top50_only"):
            rows = [r for r in rows if r.get("is_top50")]
        if ind:
            rows = [r for r in rows if r.get("industry") == ind]
        if sig:
            rows = [r for r in rows if sig in (r.get("tech_signals") or [])]
        sort_k = str(args.get("sort") or "foreign_5d").strip()
        if sort_k not in ("foreign_5d", "trust_5d", "dividend_yield", "rev_yoy", "change_pct", "pe"):
            sort_k = "foreign_5d"
        rows = sorted(rows, key=lambda r: (r.get(sort_k) is not None, r.get(sort_k) or 0), reverse=(sort_k != "pe"))
        lim = min(max(int(args.get("limit") or 15), 1), 40)
        return _trim({"asof": base.get("asof"), "matched": len(rows), "rows": rows[:lim]})
    if name == "site_attention":
        raw = await s.redis.get("attention:latest")
        if not raw:
            return "處置與注意股資料尚未準備好"
        d = json.loads(raw)
        code = str(args.get("code") or "").strip().upper()
        if code:
            d["active_dispositions"] = [r for r in d.get("active_dispositions", []) if r.get("code") == code]
            d["notices"] = [r for r in d.get("notices", []) if r.get("code") == code]
        return _trim(d)
    if name == "site_us_stocks":
        raw = await s.redis.get("us:latest")
        if not raw:
            return "美股資料尚未準備好"
        d = json.loads(raw)
        sym = str(args.get("symbol") or "").strip().upper()
        if sym:
            d["rows"] = [r for r in d.get("rows", []) if r.get("symbol") == sym]
            d["earnings"] = [r for r in d.get("earnings", []) if r.get("symbol") == sym]
        return _trim(d)
    if name == "site_watchlist":
        return _trim(await get_watchlist(req))
    if name == "site_portfolio":
        return _trim(await get_portfolio(req))
    if name == "site_calendar":
        raw = await s.redis.get("calendar:latest")
        if not raw:
            return "行事曆尚未準備好"
        d = json.loads(raw)
        code = str(args.get("code") or "").strip().upper()
        events = [e for e in d["events"] if not code or e.get("code") in (code, None)]
        return _trim({"today": d["today"], "events": events})
    raise KeyError(name)


class Toolbox:
    """一次對話用的工具集合；MCP 連不上時只用本站工具（並在 note 說明）。"""

    def __init__(self, app, mcp: McpClient | None):
        self.app, self.mcp, self.schemas, self.mcp_names, self.note = app, mcp, list(SITE_TOOLS), set(), ""

    async def load(self) -> None:
        if not self.mcp:
            self.note = "外部資料工具未設定"
            return
        try:
            await self.mcp.initialize()
            for t in await self.mcp.list_tools():
                if t["name"] in MCP_ALLOW:
                    self.mcp_names.add(t["name"])
                    self.schemas.append(_fn(t["name"], (t.get("description") or "")[:600],
                                            (t.get("inputSchema") or {}).get("properties", {}),
                                            (t.get("inputSchema") or {}).get("required", [])))
        except Exception as e:  # noqa: BLE001
            self.note = f"外部資料工具暫時無法使用（{type(e).__name__}），只用本站資料回答"

    async def call(self, name: str, args: dict) -> str:
        if name.startswith("site_"):
            return await run_site_tool(self.app, name, args)
        if name in self.mcp_names and self.mcp:
            return _trim(await self.mcp.call_tool(name, args))
        return f"沒有這個工具：{name}"
