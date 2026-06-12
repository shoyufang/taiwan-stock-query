# 專業看盤終端 — 第二期深化計劃（PRO_TERMINAL_PHASE2）

> 前情：PRO_TERMINAL_UX_PLAN（Phase A–F）已完成並部署。本計劃解決「架構像看盤軟體、內容深度還不夠」的問題。
> 給 AI 代理（Antigravity / Gemini）執行。按 Phase 順序，每個 Phase 完成跑 `pytest` 全綠（基準 295+）+ 本機 `streamlit run app.py` 實測，各自 commit（`local` 分支）。
> **沿用既有紅線**：不改 query 層簽名、所有新元件必加唯一 `key=`（tests/test_widget_keys.py 會擋）、新查詢必套 `@cached_query`、API 失敗顯示佔位不白屏、HTML 用 CSS 變數取色。

---

## 0. 缺口診斷（為什麼「還是不夠」）

| 缺口 | 專業視角說明 |
|---|---|
| **看盤頁沒有「圖」** | 市場總覽全是數字磚。交易者判斷盤勢靠「形」：大盤走勢、法人累計買超與指數的背離，一張圖勝過十個數字 |
| **5 年歷史資料閒置** | `data/market/` 有 1,301 個交易日的加權指數＋三大法人 CSV（2021 起），UI 完全沒用。這是現成的「市場脈絡」資料庫 |
| **沒有族群視角** | 台股是族群盤（AI 伺服器、重電、航運輪動）。目前只能看個股，看不到「今天哪個族群在動」 |
| **籌碼只有快照，沒有「連續性」** | 專業籌碼分析看的是外資/投信**連買 N 日**、累計買超趨勢，不是單日數字 |
| **沒有警示，必須主動盯** | 終端的價值一半在「它主動告訴你」：到價、跌破均線、被列處置。目前 email 基礎建設都在（daily_job），只通知處置股 |
| **估值缺「相對位置」** | 只顯示本益比數字沒有意義；專業看法是「現在 PE 在自己 5 年區間的哪裡」（PE 河流圖）與「跟同業比貴還便宜」 |
| **AI 沒接上看盤流程** | AI 助理是獨立聊天頁；專業期待是「一鍵讓 AI 讀完今天所有市場數據，給我一段盤勢解讀」 |

---

## Phase G：市場總覽加上「形」（最高 CP 值，先做）

### G.1 大盤主圖（市場總覽指數條下方新增）

- 新建 `tabs/_market_history.py`：
  - `load_market_history(days: int = 250) -> pd.DataFrame`：讀 `data/market/*.csv` 合併（欄位：date, taiex, taiex_chg, taiex_pct, foreign?, trust, dealer——**先實際讀一個檔確認欄位名**，2021 年初的檔可能缺部分欄位，需容錯）。套 `@st.cache_data(ttl=3600)`。
  - 注意 Streamlit Cloud / NAS 上 `data/` 與 repo 同步（NAS daily_job 每日 push），本機開發若無最新檔正常顯示舊資料即可。
- 圖：Plotly 雙軸圖，上=加權指數收盤線（近 250 日），下=三大法人**累計**買賣超面積圖（cumsum）。漲跌色用 `get_updown_colors()`，背景跟 `get_plotly_template()`。
- 提供 60 / 120 / 250 日切換（`st.radio` horizontal，key=`mh_range`）。
- 放在指數行情條與市場寬度之間，高度 ~320px，不搶版面。

### G.2 市場寬度歷史小圖

- 同模組加 `breadth_sparkline()`：近 60 日「漲跌家數差」或法人合計買賣超柱狀小圖（高 ~120px），放市場寬度磚旁邊。資料同樣來自 `load_market_history`。

### G.3 資料時效標示（全站慣例）

- `tabs/_shared.py` 新增 `data_asof(label: str, ts)`：統一的小字「📅 資料時間：…」元件。
- 市場總覽每個區塊（寬度/法人/排行/警示）右上角標注資料日期——專業終端永遠告訴你資料是什麼時候的。盤後資料標「收盤」、快取資料標快取時間。

**驗收**：市場總覽有大盤走勢圖且範圍切換正常；斷網時圖區顯示佔位磚；`pytest` 全綠。

---

## Phase H：族群輪動熱力圖（台股看盤的靈魂）

### H.1 產業對照表

- 新建 `sector_map.py`：
  - `get_sector_map() -> pd.DataFrame`（代號→產業別）：呼叫 TWSE OpenAPI `/opendata/t187ap03_L`（上市公司基本資料含「產業別」，`query_twse_company` 的方案 A 已在用同一端點，抽共用）。`@cached_query(ttl=86400, sqlite_ttl=604800)`。
  - 產業別代碼→中文名稱對照（半導體、電腦週邊、光電、通信網路、電子零組件、航運、金融保險、鋼鐵、生技…）寫成模組常數 dict。

### H.2 熱力圖頁區塊（加進市場總覽，排行榜上方）

- `render_sector_heatmap()`：
  1. `query_twse_daily_all()` 取全市場當日行情，merge 產業別。
  2. 聚合：各產業「成交金額加權平均漲跌幅」與「成交金額合計」。
  3. Plotly **Treemap**：方塊大小=產業成交金額、顏色=漲跌幅（紅漲綠跌 colorscale，中性灰=0，色階 ±3% 飽和）。
  4. 點擊提示顯示該產業前 5 大成交額個股。
  5. 下方一行「今日最強/最弱族群」文字摘要。
- 同時在**選股中心**加「族群」快速篩選：選一個產業 → 列出該產業全部個股當日行情（重用 sector_map + daily_all，加「→ 個股全景」按鈕）。

**驗收**：熱力圖顯示且顏色符合紅漲綠跌；點選股中心族群篩選能列出成分股並跳轉個股全景。

---

## Phase I：籌碼深化 — 連買排行與累計趨勢

### I.1 法人連買天數排行（市場總覽新區塊 or 選股中心新 tab）

- 資料來源：`data/twse/institutional/*.csv`（NAS daily_job 每日累積，目前檔少）。
- 新建 `chip_analysis.py`：
  - `load_institutional_history(days: int = 20) -> dict[str, pd.DataFrame]`：讀最近 N 個日檔。
  - `consecutive_buy_ranking(who: str = "外資", min_days: int = 3) -> pd.DataFrame`：計算每檔股票被外資/投信連續買超天數與累計張數，排序。
  - **重要——資料不足的降級策略**：若本地日檔 < `min_days`，UI 顯示「籌碼資料累積中（目前 N 天，需 ≥ 3 天）」的提示磚而不是空表。隨 NAS 每日累積自動變可用。**不要**為了補歷史去迴圈呼叫 FinMind 全市場（會被限流）。
- UI：選股中心新增第 4 個 tab「💰 籌碼選股」：外資連買排行、投信連買排行、外資投信同步買（既有 daily_job 雙買超邏輯搬上 UI），每列「→ 個股全景」。

### I.2 個股全景籌碼分頁強化

- 籌碼分頁頂部加 3 個摘要磚：「外資連買 N 天」「投信連買 N 天」「近 20 日外資累計 ±N 張」（用既有 `query_institutional_summary` 對單一個股計算，不依賴本地日檔）。
- 既有圖表不動。

**驗收**：個股籌碼摘要磚正確（拿 2330 對照證交所數字）；連買排行在資料不足時顯示累積中提示。

---

## Phase J：估值深化 — PE 河流圖與同業比較

### J.1 PE 河流圖（個股全景基本面分頁）

- `technical_analysis.py` 或新建 `valuation_chart.py`：`plot_pe_river(code)`：
  1. `query_per_pbr(code, 5年前, 今天)` 取歷史 PE 與收盤價（該資料集含股價與 PER）。
  2. 計算歷史 EPS = 價格/PE，再以 PE = [12,16,20,24,28]（或取該股 5 年 PE 的 10/30/50/70/90 百分位）畫五條價格帶，疊上實際股價線。
  3. 顏色：價格帶用主題色漸層透明填充。
- 放在基本面分頁估值磚下方，一眼看出「現在股價在歷史估值帶的哪一層」。
- 虧損股（PE 為空/負）顯示「不適用（近期 EPS 為負）」。

### J.2 同業比較表

- 基本面分頁新增「同業比較」expander：
  1. 用 Phase H 的 `get_sector_map()` 找同產業股票，取成交金額前 8 名。
  2. `query_twse_valuation()`（全市場當日 PE/PB/殖利率，一次呼叫）篩出這幾檔。
  3. 表格：代號/名稱/收盤/PE/PB/殖利率，本股高亮（用 styler 背景色 `--claude-primary` 透明版），每列可跳轉。

**驗收**：2330 的 PE 河流圖有五條帶與價格線；同業比較列出半導體同業且本股高亮。

---

## Phase K：自選股警示系統（讓終端「主動說話」）

### K.1 警示規則設定

- `config.py` 新增 `load_alerts()/save_alerts()`（`~/.app_config/alerts.json`，沿用既有 JSON 容錯模式）。規則結構：
  ```json
  [{"code": "2330", "type": "price_above", "value": 1100, "enabled": true},
   {"code": "2330", "type": "price_below", "value": 950, "enabled": true},
   {"code": "2454", "type": "pct_move", "value": 5, "enabled": true}]
  ```
  類型：`price_above` / `price_below` / `pct_move`（單日漲跌幅絕對值≥）/ `ma20_break`（跌破20日線）/ `foreign_streak`（外資連買/賣≥N日）。
- 自選股頁新增「🔔 警示」popover：對每檔自選股設定規則（key 規則照舊）。

### K.2 盤後警示引擎（掛進 NAS daily_job）

- 新建 `alert_engine.py`：`check_alerts() -> list[dict]`：讀 alerts.json + 當日收盤資料（`data/twse/daily_all` 當日檔，避免再打 API），逐條評估，回傳觸發清單。
- `daily_job.py` 新增 Step：`check_alerts()` 有觸發就用既有 `send_email(html=True)` 寄「📣 自選股警示日報」（重用 `df_to_html_table`）。無觸發不寄。
- **注意**：NAS 容器內 `~/.app_config` 與 repo 不同步。解法：alerts.json 路徑支援環境變數覆寫（沿用 `APP_CACHE_DIR` 的模式），NAS 上把它放 `/volume1/docker/sinopac/data/alerts.json`（volume 內），並讓 Web UI（同一容器）讀寫同一路徑。文件中記載此設定。

### K.3 盤中視覺警示（輕量版）

- 自選股報價牆：觸發警示規則的列加 🔔 圖示與底色高亮（讀同一份 alerts.json，純前端判斷，不另發通知）。

**驗收**：UI 能新增/停用警示；手動執行 `python -c "from alert_engine import check_alerts; print(check_alerts())"` 回傳合理結果；daily_job 在有觸發時寄出郵件（用 email_preview 模式驗證格式）。

---

## Phase L：AI 盤勢日報（把 AI 接進看盤流程)

### L.1 一鍵盤勢解讀（市場總覽頂部按鈕）

- `deepseek_engine.py` 新增 `generate_market_briefing(context: dict) -> str`：
  - context 由市場總覽現成資料組裝：指數漲跌、漲跌家數、成交金額、三大法人金額、最強/最弱族群（Phase H 產出）、漲幅前 10、處置股新增、ADR 溢折價。**全部複用已查詢的快取資料，不重打 API**。
  - Prompt 要求：繁體中文、200–300 字、結構為「盤勢一句話定調 → 資金流向（法人+族群）→ 風險提示」、禁止投資建議字眼、語氣像券商晨報。
- UI：市場總覽標題列右側「🤖 AI 盤勢解讀」按鈕（key=`mo_ai_brief`），結果存 `st.session_state["ai_brief_{日期}"]` 防重整消失，顯示在指數條下方的卡片。
- 個股全景「新聞/AI」分頁的 AI 健檢按鈕同樣補上盤勢 context（個股 vs 大盤相對強弱）。

### L.2 （選做）日報進郵件

- daily_job 警示郵件（Phase K）開頭加 AI 盤勢段落（NAS 容器需 DEEPSEEK_API_KEY 環境變數，無金鑰時優雅跳過）。

**驗收**：點按鈕 10 秒內出現盤勢卡片；無 DeepSeek 金鑰時按鈕顯示引導訊息不報錯。

---

## 優先順序與依賴

| 順序 | Phase | 理由 |
|---|---|---|
| 1 | **G** | 把閒置 5 年資料變成看盤主圖，工作量最小、體感提升最大 |
| 2 | **H** | 族群熱力圖是台股看盤靈魂，且 J、L 依賴它的 sector_map |
| 3 | **I** | 籌碼連續性=台股專業度的分水嶺（注意資料累積降級策略） |
| 4 | **J** | 估值深化，依賴 H |
| 5 | **K** | 警示系統，獨立可後做，但價值極高 |
| 6 | **L** | AI 整合，依賴 G/H 的資料組裝 |

## 測試要求

- 每個新模組對應測試：`test_market_history.py`（CSV 容錯/欄位缺失）、`test_sector_map.py`（聚合計算）、`test_chip_analysis.py`（連買天數計算用合成資料驗證）、`test_alert_engine.py`（每種規則型態觸發/不觸發各一例）。
- 所有新元件 key 唯一（`test_widget_keys.py` 自動把關）。
- 完成全部後依 CLAUDE.md 流程 merge → push GitHub + NAS。
