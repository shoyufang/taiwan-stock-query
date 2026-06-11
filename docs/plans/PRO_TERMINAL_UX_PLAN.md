# 專業看盤終端改造計劃（PRO_TERMINAL_UX_PLAN）

> 本文件是給 AI 代理（Antigravity / Gemini）執行的 UI/UX 重組計劃。
> 目標：把目前「按 API 來源分類的查詢工具集」改造成「按交易者工作流程組織的專業看盤終端」。
> **原則：不新增資料來源、不重寫查詢邏輯**——所有功能都已存在（query_wrapper.py / datasources/ / tabs/），本計劃 95% 的工作是「重新組裝與呈現」。
> 按 Phase 順序執行，每個 Phase 完成後跑 `pytest` 全綠 + `streamlit run app.py` 手動驗證，再 commit 進下一個。

---

## 0. 設計理念：為什麼現在「不像看盤軟體」

### 0.1 現況問題（財經專業視角）

目前側邊欄 17 個導航項：
```
儀表板 / 台股市場 / 技術分析 / TWSE / DeepSeek AI / 🇺🇸 美股專區 / 📅 美股日曆 & 共識 /
FinMind / 期貨匯率 / 選股 / 新聞 / 📈 技術掃描器 / 👁️ 自選股監控 / 💼 投資組合 /
📄 PDF 報告 / 工具 / ⚡ 效能監控
```

問題：
1. **按資料來源分類**：「TWSE」「FinMind」是 API 名稱，不是交易決策的概念。交易者想看「2330 的籌碼」，不會去想「這要去 FinMind 頁還是 TWSE 頁」。同一檔股票的資訊散在 6 個分頁。
2. **沒有「個股」這個一級概念**：所有專業看盤軟體（Bloomberg、TradingView、XQ、券商 App）的核心都是「輸入一個代號 → 一頁看完報價、線圖、籌碼、基本面、新聞」。本專案的工具齊全卻沒有這一頁。
3. **缺少盤勢儀表**：專業終端打開第一眼是「大盤現在如何」——指數、漲跌家數、成交金額、台指期、國際市場。目前儀表板只有 ADR 和關注名單。
4. **重複功能未合併**：「選股」「技術掃描器」是同一件事（條件篩選）；「美股專區」「美股日曆」「期貨/匯率」「港股」都是「非台股市場」；「PDF 報告」「效能監控」「工具」是後台功能卻佔一級導航。

### 0.2 專業交易者的一天（目標資訊架構的依據）

| 時段 | 需求 | 對應功能（全部已存在） |
|---|---|---|
| **盤前 07:00–09:00** | 美股收盤、ADR 溢折價、國際市場、今日新聞、處置/注意股、今日除息與法說 | adr_query、query_futu_market_state、新聞、query_twse_disposition/notice、tw_calendar |
| **盤中 09:00–13:30** | 大盤指數、自選股報價牆、漲跌幅/量排行、個股五檔、即時 K 線、大單分析 | query_snapshot、query_ranking、query_shioaji_snapshot、query_shioaji_kbars、analyze_shioaji_big_orders |
| **盤後 14:00–** | 三大法人、融資券、當沖比、選股掃描、個股深度研究 | query_twse_institutional、query_twse_margin、screener、FinMind 全系列 |
| **深度研究（隨時）** | 單一個股的完整面貌＋AI 解讀 | 技術分析、FinMind 基本面、deepseek_engine |

### 0.3 新資訊架構：17 項 → 8 項

```
🏠 市場總覽      ← 大盤儀表 + 國際 + ADR + 排行 + 盤前警示（重做儀表板）
🔍 個股全景      ← ★ 本計劃核心新頁面：一個代號看完所有面向
👁️ 自選股        ← 報價牆（升級現有自選股監控）
🎯 選股中心      ← 台股選股 + 美股選股 + 技術掃描器（三合一）
🌐 全球市場      ← 美股專區 + 港股 + 期貨/匯率（三合一）
📅 投資行事曆    ← 台股法說/除息 + 美股財報 + 華爾街共識（二合一）
🤖 AI 助理       ← DeepSeek Chat（保留）
💼 投資組合      ← 保留
```

降級進「⚙️ 設定與工具」（側邊欄底部 popover 或 expander，不佔一級導航）：
- 工具（書籤管理/歷史/對比/設定）、PDF 報告、效能監控、新聞（新聞改為嵌入市場總覽與個股全景，不需獨立頁）

舊版查詢頁（台股市場 / TWSE / FinMind / 技術分析）**不刪除**，收進一個「🗂️ 進階查詢」摺疊群組（見 Phase A.4），確保既有書籤/歷史 100% 可用，過渡期後再評估是否移除。

---

## Phase A：導航重組（純搬移，零新功能，先建骨架）

### A.1 改寫側邊欄導航（app.py）

把現有平鋪式 17 顆按鈕改為**分組導航**：

```python
NAV_GROUPS = {
    "看盤": ["市場總覽", "個股全景", "自選股"],
    "決策": ["選股中心", "全球市場", "投資行事曆"],
    "管理": ["AI 助理", "投資組合"],
}
ADVANCED_TABS = ["台股市場", "TWSE", "FinMind", "技術分析", "期貨/匯率", "新聞"]   # 收進「進階查詢」expander
UTILITY_TABS  = ["工具", "PDF 報告", "效能監控"]                                  # 收進「設定與工具」expander
```

側邊欄結構（由上而下）：
1. 主題切換器（現狀保留）
2. 三個分組（組名用小型大寫標籤字，沿用現有 `--claude-text-2` 樣式）
3. `st.expander("🗂️ 進階查詢")` → 舊分頁按鈕
4. `st.expander("⚙️ 設定與工具")` → 工具/PDF/效能監控 + 現有系統設定 popover 移入
5. 釘選/最近查詢/健康檢查（現狀保留，但「健康檢查」移入設定 expander）

### A.2 路由與相容性

- `TAB_RENDERERS` 新增鍵：`"市場總覽"`、`"個股全景"`、`"自選股"`、`"選股中心"`、`"全球市場"`、`"投資行事曆"`、`"AI 助理"`。
- **舊鍵全部保留**（`"儀表板"` → 指向新的市場總覽、`"DeepSeek AI"` → AI 助理、`"👁️ 自選股監控"` → 自選股、`"選股"`/`"📈 技術掃描器"` → 選股中心、`"🇺🇸 美股專區"`/`"📅 美股日曆 & 共識"` → 全球市場），這樣舊書籤與歷史記錄點擊後仍能落到正確頁面。
- 預設首頁：`st.session_state.selected_tab` 預設值從 `"DeepSeek AI"` 改為 `"市場總覽"`。

### A.3 新 tabs 檔案（本 Phase 先建殼，內容後續 Phase 填）

```
tabs/market_overview.py   ← Phase B 實作（先放現有 render_dashboard 內容）
tabs/stock_page.py        ← Phase C 實作（先放「輸入代號」+ 暫時導向技術分析）
tabs/global_markets.py    ← Phase D 實作（先用 st.tabs 包現有三個 render）
tabs/calendar_tab.py      ← Phase D 實作（先用 st.tabs 包現有兩個 render）
tabs/screener_hub.py      ← Phase D 實作（先用 st.tabs 包現有三個 render）
```

**驗收標準**：8+2 組導航可切換；所有舊書籤/歷史可執行；`pytest` 全綠。

---

## Phase B：市場總覽（看盤首頁重做）

> 設計參考：券商看盤軟體首頁 + TradingView 市場頁。原則：**一屏掌握大盤，10 秒判斷今天是什麼盤**。

### B.1 版面設計（由上而下）

```
┌─────────────────────────────────────────────────────────────┐
│ ① 指數行情條（Ticker Strip）— st.fragment 每 30 秒刷新       │
│  加權指數 21,530 ▲125 (+0.58%) ｜櫃買 245 ▲1.2 ｜台指期 21,560 │
│  (價差+30) ｜ USD/TWD 32.21 ｜ 費半 ▲1.2% ｜ 那指期 ▲0.4%      │
├──────────────────────────────┬──────────────────────────────┤
│ ② 市場寬度（漲跌家數）        │ ③ 三大法人今日買賣超(億)      │
│  上漲 612 ↑ / 下跌 388 ↓     │  外資 +152 投信 +18 自營 -23   │
│  漲停 12 / 跌停 3            │  （橫向 bar，紅買綠賣）        │
│  成交金額 3,850 億           │                               │
├──────────────────────────────┴──────────────────────────────┤
│ ④ 台美 ADR 溢折價卡片（現有，保留）                           │
├─────────────────────────────────────────────────────────────┤
│ ⑤ 今日排行（st.tabs：漲幅｜跌幅｜成交量｜成交額）             │
│   每列附「→ 個股全景」跳轉按鈕                                │
├──────────────────────────────┬──────────────────────────────┤
│ ⑥ 盤前警示區                  │ ⑦ 大盤新聞（前 5 則卡片）      │
│  ⚠️ 新增處置股 N 檔 (列代號)  │                               │
│  📢 注意股票 N 檔             │                               │
│  💰 今日除息：代號列表        │                               │
└──────────────────────────────┴──────────────────────────────┘
```

### B.2 各區塊資料來源（全部是既有函數，只做組裝）

| 區塊 | 函數 | 備註 |
|---|---|---|
| ① 加權/櫃買指數 | `query_twse_mi_index()`（盤後）+ yfinance `^TWII` 即時（盤中） | 已有儀表板 yfinance 大盤快照邏輯可沿用 |
| ① 台指期與價差 | `query_futures_daily("TX",...)` 最近一筆 vs 加權指數 | 價差 = 期貨 - 現貨，正逆價差標色 |
| ① 匯率 | `adr_query.get_usd_twd_rate()` | 已存在 |
| ① 美股期貨/費半 | yfinance `NQ=F`、`^SOX` | 新增一個小函數進 `datasources/news_client.py` 或新建 `datasources/global_quotes.py`，套 `@cached_query(ttl=60)` |
| ② 漲跌家數 | 由 `query_twse_daily_all()` 全市場 DataFrame 計算（漲跌>0 計數、漲跌停判斷） | 純 pandas 計算，寫成 `market_breadth(df) -> dict` 放 `tabs/_shared.py` |
| ③ 法人買賣超 | `query_twse_institutional()` 彙總三類別金額 | 已有，億元化 + Plotly 橫向 bar |
| ④ ADR | `adr_query.get_adr_snapshots()` | 現有卡片直接搬 |
| ⑤ 排行 | `query_ranking(type, limit=10)` | Shioaji 不可用時 fallback：用 `query_twse_daily_all()` 排序 |
| ⑥ 處置/注意 | `query_twse_disposition()`、`query_twse_notice()` | 只顯示筆數+代號徽章，點開 expander 看全表 |
| ⑥ 今日除息 | `tw_calendar.get_tw_calendar_consensus_data()` 過濾除息日=今日 | 已存在 |
| ⑦ 新聞 | `print_news` 對應的 wrapper（大盤 ^TWII） | 沿用 tabs/news.py 的卡片渲染函數，抽成共用 |

### B.3 指標卡規格（建立統一元件，後續頁面重用）

在 `ui_components.py` 新增：

```python
def metric_tile(label: str, value: str, delta: float | None = None,
                delta_suffix: str = "%", size: str = "md"):
    """看盤指標磚：深色底、tabular-nums 數字字體、台股慣例紅漲綠跌。
    delta > 0 → 紅 (--up-color)；delta < 0 → 綠 (--down-color)；0/None → 灰。"""
```

**重要：漲跌配色全站統一**（見 Phase E 色彩規範），不准再 hard-code `#e63946` / `#2a9d8f`（目前 tabs/dashboard.py:114-116 有，要改）。

### B.4 刷新策略

- 區塊①②整體包進 `@st.fragment(run_every=30)`（沿用 Phase 7 已驗證的 fragment 模式）。
- ③–⑦ 屬於低頻資料，用既有快取 TTL，不自動刷新；右上角放一顆「🔄 重新整理」按鈕清 `st.cache_data`。
- 盤中/盤後判斷：寫 `is_market_open() -> bool`（週一–五 09:00–13:30 台北時間）放 `tabs/_shared.py`；收盤後 fragment 改 `run_every=None` 省資源。

**驗收標準**：開啟市場總覽 3 秒內首屏完成（快取命中時）；盤中 30 秒自動更新指數條；所有區塊在 API 失敗時顯示灰色「資料暫不可用」磚而非 traceback。

---

## Phase C：個股全景頁（本計劃核心，最高價值）

> 設計參考：TradingView Symbol Page / XQ 個股總覽 / 富途牛牛個股頁。
> 概念：**代號是入口，頁內分頁是面向**。輸入 2330 之後不用再切換任何側邊欄導航。

### C.1 版面設計

```
┌─────────────────────────────────────────────────────────────┐
│ [搜尋框：代號/中文名（resolve_code 已支援）]  [🔍]  [⭐加自選]  │
├─────────────────────────────────────────────────────────────┤
│ 個股表頭（st.fragment 30 秒刷新）                              │
│  台積電 2330.TW ｜ 1,085 ▲15 (+1.40%) ｜ 成交量 32,150 張      │
│  今開 1,075 高 1,090 低 1,072 ｜ 昨收 1,070 ｜ 振幅 1.68%      │
│  漲停 1,177 跌停 963（query_shioaji_contract）                 │
├─────────────────────────────────────────────────────────────┤
│ st.tabs：📈 技術 ｜ 📊 籌碼 ｜ 💰 基本面 ｜ 🏛️ 五檔大單 ｜ 📰 新聞AI │
└─────────────────────────────────────────────────────────────┘
```

### C.2 五個頁內分頁的內容（全部呼叫既有函數）

**📈 技術**（搬自 tabs/technical.py 的核心，預設參數簡化）
- 預設載入近 6 個月日 K + MA5/20/60 + 成交量（`plot_kbar_with_indicators`）
- 指標多選與日期區間放 expander「進階設定」內，預設收合——看盤軟體先給圖再給設定
- 下方一列統計磚：區間漲跌幅、區間高低、年化波動（ATR 已有）

**📊 籌碼**（彙整 FinMind + TWSE 六個查詢）
- 預設區間近 60 個交易日，頂部一個日期區間選擇器**共用於本分頁所有圖**
- 區塊1：三大法人買賣超柱狀圖 + 外資累計買超折線（`query_institutional_summary`，Plotly 雙軸）
- 區塊2：融資融券餘額雙線圖（`query_margin_short`）
- 區塊3：外資持股比例折線（`query_foreign_shareholding`）+ 借券餘額（`query_securities_lending`）
- 區塊4：當沖比率（`query_day_trading_volume`）
- 每個區塊：圖在上、expander 內放原始表格 + 下載按鈕（沿用 `display_result` 的下載能力）

**💰 基本面**（彙整 FinMind 四查詢 + TWSE 估值）
- 頂部估值磚列：本益比 / 股價淨值比 / 殖利率（`query_twse_valuation` 今日值）+ 該股 5 年 PE 區間百分位（`query_per_pbr` 歷史，算當前 PE 在 5 年分布的位置——這是專業估值視角，純 pandas 計算）
- 區塊1：月營收柱狀圖 + YoY 折線（`query_month_revenue`，YoY 已可由資料計算）
- 區塊2：EPS / 毛利率 / 營益率季度趨勢（`query_financial_statement` 取關鍵科目）
- 區塊3：股利政策表（`query_dividend`）+ 近 5 年平均殖利率
- 區塊4：公司基本資料卡（`query_twse_company`）

**🏛️ 五檔大單**（搬自 tabs/taistock.py 的 Shioaji 區塊）
- 五檔報價盤（ui_components.py 既有高質感卡片直接重用）
- 大單分析圓餅圖 + 淨流入指標（`analyze_shioaji_big_orders`，門檻參數放 expander）
- 無 Shioaji 金鑰時：顯示引導卡「此區需券商 API，請至設定填寫金鑰」，**不報錯**

**📰 新聞 AI**
- 個股新聞卡片（既有新聞渲染，code 帶入）
- 一顆「🤖 AI 個股健檢」按鈕：台股走 deepseek_engine 既有 chat（帶入個股 prompt 模板），美股代號走 `generate_us_stock_report`（已存在）；結果存 `st.session_state[f"stock_ai_{code}"]` 防重整消失（沿用美股報告的既有模式）

### C.3 跨頁跳轉機制（讓整個 App 串起來）

在 `tabs/_shared.py` 新增：

```python
def goto_stock_page(code: str):
    """全站通用：跳轉到個股全景頁並帶入代號"""
    st.session_state["stock_page_code"] = code
    st.session_state["selected_tab"] = "個股全景"
    st.rerun()
```

接入點（本 Phase 一併完成）：
1. 市場總覽的排行榜每列加「📈」小按鈕 → `goto_stock_page`
2. 自選股報價牆每列加同款按鈕
3. 選股中心結果表加同款按鈕（取代目前「請複製代號到技術分析」的文字提示）
4. 全域快速搜尋（app.py 既有 global_search）：解析成功後改為直接 `goto_stock_page`，取代目前只顯示快照

### C.4 美股/港股代號的處理

`stock_page` 偵測代號型態（沿用 `_cached_kbar` 的「非純數字=非台股」判斷）：
- 美股/港股：技術分頁正常（yfinance 已支援）；籌碼分頁改顯示機構持股（us_stock_query 既有）；五檔大單分頁隱藏；基本面分頁顯示 yfinance info 關鍵指標（PE/ROE/市值，us_screener._fetch_ticker_metrics 已有解析邏輯可重用）
- 此為加分項，若工作量過大可先只支援台股、非台股代號提示「請至全球市場頁查詢」

**驗收標準**：輸入「台積電」→ 5 個分頁全部有資料；從市場總覽排行點按鈕能跳轉；無 Shioaji 金鑰環境五檔分頁顯示引導卡；`pytest` 全綠（新增 `tests/test_stock_page.py`：mock query 函數，驗證五分頁渲染不拋例外 + goto_stock_page 的 session state 行為）。

---

## Phase D：合併頁（選股中心 / 全球市場 / 投資行事曆 / 自選股升級）

### D.1 選股中心（tabs/screener_hub.py）

`st.tabs(["🇹🇼 台股選股", "🇺🇸 美股選股", "📡 技術掃描"])` 分別呼叫既有 `render_screener` 台股部分、`render_us_screener`、`render_technical_scanner`。
- 移除原「選擇選股市場」radio（被 tabs 取代）
- 三個結果表統一加「→ 個股全景」跳轉按鈕
- 加一個共同的「💾 儲存此篩選條件」（存成書籤，params 帶 filters dict——書籤系統已支援任意 params）

### D.2 全球市場（tabs/global_markets.py）

`st.tabs(["🇺🇸 美股", "🇭🇰 港股", "📊 期貨/匯率"])` 包既有三個 render。
- 頁面頂部加一條「全球市場狀態」橫條（`query_futu_market_state()` 已有，FutuOpenD 不在線時顯示 yfinance 主要指數替代）

### D.3 投資行事曆（tabs/calendar_tab.py）

`st.tabs(["🇹🇼 台股法說/除息", "🇺🇸 美股財報", "🎯 華爾街共識"])`：
- 台股：既有 `tw_calendar` 數據，但改成**時間軸視覺**：依日期分組、今日高亮、過期灰字
- 美股財報/共識：搬 `render_us_calendar_consensus` 的兩個內部 tab
- 頂部加「未來 7 天重點」摘要列（兩市場合併、按日期排序前 10 筆）

### D.4 自選股升級（tabs/watchlist_monitor.py 強化）

- 報價牆改用 Phase B 的 `metric_tile` / 統一漲跌色 styler
- 加欄位：距 52 週高點 %（kbar 可算）、今日量比（今量/5 日均量）
- 每列「→ 個股全景」按鈕
- 編輯名單的 UI 從設定搬到本頁右上 popover（watchlist 讀寫函數已存在 config.py）

**驗收標準**：四頁可用；舊導航鍵（美股專區等）跳轉到合併頁對應 tab；`pytest` 全綠。

---

## Phase E：專業看盤視覺規範（全站統一）

### E.1 漲跌色彩系統（最重要的一條）

台股慣例：**紅漲綠跌**。在 `theme.py` 的 `:root` 增加語義變數，五個主題都要定義：

```css
--up-color:        #d6453d;   /* 漲（各主題可微調，但必須是紅系） */
--up-bg:           rgba(214,69,61,.10);
--down-color:      #1a9c6b;   /* 跌（綠系） */
--down-bg:         rgba(26,156,107,.10);
--flat-color:      var(--claude-text-2);
```

執行：
1. 全域搜尋既有 hard-code 漲跌色（`#e63946`、`#2a9d8f`、`#1976d2`、`red`、`green` 等用於漲跌語義的），全部改 CSS 變數或集中常數 `UP_COLOR/DOWN_COLOR`（Python 端 Plotly 用，從 `theme.py` 提供 `get_updown_colors()` 讀當前主題）。
2. `technical_analysis.py` 的台股紅漲/美股綠漲自動切換邏輯保留，但色值改從 `get_updown_colors()` 取得。
3. DataFrame 漲跌欄位上色統一用一個 styler 函數 `style_updown(df, columns)` 放 `ui_components.py`，刪除各 tab 自己寫的 `highlight_change`。

### E.2 新增第 6 主題：「🌙 看盤深色」（設為交易情境推薦）

專業終端幾乎都是深色（長時間盯盤護眼、數字對比度高）。在 `THEMES` 加：

```
bg: #12141A / sidebar: #181B22 / surface: #1E222B / primary: #E8A04C（琥珀）
text: #E5E9F0 / text2: #8B93A3 / border: #2A2F3A
up: #FF5252 / down: #26C281
```

注意既有 `_inject_theme_css` 機制直接支援新增主題（CLAUDE.md 記載的 f-string 規則要遵守）；另外深色下 Plotly 圖表要跟著切 template：`get_plotly_template()` 回傳 `plotly_dark` 或 `plotly_white`，technical_analysis 與所有 Plotly 圖套用。

### E.3 數字排版

- 所有價格/漲跌數字套 `font-variant-numeric: tabular-nums`（等寬數字，跳動時不位移——看盤軟體必備），加進 theme.py 全域 CSS：對 `[data-testid="stMetricValue"]`、自訂磚、dataframe 生效。
- 千分位：建立 `fmt_price(v)` / `fmt_amount_yi(v)`（億元）/ `fmt_pct(v)` 三個格式化函數放 `tabs/_shared.py`，全站統一（目前各頁 `:.2f`、`:.1f` 不一致）。

### E.4 版面密度

- 看盤頁（市場總覽/個股全景/自選股）使用緊湊間距：theme.py 加 `.block-container { padding-top: 1.2rem; }`、縮小 `st.divider` 上下 margin。
- 表格列高調密（CSS 覆蓋 dataframe cell padding）。

**驗收標準**：切換 6 個主題（含新深色），市場總覽/個股全景/技術圖的漲跌色、Plotly 背景全部正確跟隨；無殘留 hard-code 色。

---

## Phase F：收尾

1. **新聞頁退役**：確認市場總覽⑦與個股全景📰已覆蓋後，把「新聞」從進階查詢群組移除（render 函數保留，書籤相容靠 TAB_RENDERERS 舊鍵）。
2. **預設自選股**：首次使用（watchlist 空）時預載 `["2330","2317","2454","2308","2382"]` 並提示可編輯，避免新用戶看到空白報價牆。
3. **CLAUDE.md / GEMINI.md 更新**：新導航結構、新 tabs 檔案表、跳轉機制 `goto_stock_page`、色彩規範（語義變數清單）。
4. **測試**：`tests/test_nav_compat.py`（舊 tab 鍵 → 新頁面 mapping 全覆蓋）、`tests/test_shared_helpers.py`（market_breadth / is_market_open / fmt_* / get_updown_colors）。目標總測試 ≥ 290。
5. 依 CLAUDE.md 標準流程 merge main → push GitHub + NAS，NAS 上抽查市場總覽、個股全景（2330）、自選股三頁。

---

## 執行紅線（給 AI 代理）

1. **不改 query 層**：query_wrapper.py / datasources/ 的函數簽名與行為一律不動（Phase B 允許新增 `global_quotes.py` 一個小模組）。
2. **書籤/歷史相容**：TAB_RENDERERS 的所有舊鍵必須保留並導向新頁面；session state 既有 key 不改名。
3. **HTML/CSS 規則**：自訂 HTML 磚一律用 CSS 變數取色；f-string CSS 注意 `{{}}` 轉義（CLAUDE.md 已記載教訓）。
4. **API 失敗不白屏**:每個資料區塊獨立 try/except，失敗顯示灰色佔位磚；Shioaji 未設金鑰是常態場景（公開版），所有依賴 Shioaji 的區塊必須有 TWSE/yfinance fallback 或引導卡。
5. **效能**：自動刷新只允許用 `st.fragment`，且只在指數條與個股表頭兩處；其餘靠快取。任何新查詢必須套 `@cached_query`。
6. **每 Phase 一個以上 commit**（`feat(terminal-X): ...`），在 `local` 分支開發，全部完成才走 merge → main → NAS 流程。
7. 每 Phase 完成必跑 `pytest` 全綠 + 手動 `streamlit run app.py` 驗證該 Phase 驗收標準。

## 優先順序（若分批執行）

| 優先 | Phase | 價值 |
|---|---|---|
| ★★★ | A + B | 一進門就是專業終端的樣子，投入產出比最高 |
| ★★★ | C | 殺手級功能：個股全景，把散落 6 頁的工具變成一頁 |
| ★★ | E | 漲跌色統一 + 深色主題，「看起來專業」的關鍵 |
| ★★ | D | 導航瘦身的完成式 |
| ★ | F | 收尾打磨 |
