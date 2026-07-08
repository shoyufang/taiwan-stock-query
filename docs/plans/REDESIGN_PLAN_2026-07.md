# 全案重構設計計劃書 — 消滅重複功能（2026-07-08）

> 性質：**大刀闊斧的結構重設計**，不是漸進式微調。每一塊都包含
> 「現況證據 → 重設計方案 → 要殺掉的東西 → 驗算（驗收條件）」。
> 所有現況皆本日實測驗證（grep/wc/讀碼），非印象。
> 執行前提：現有 CI 綠燈（已達成）+ 每塊獨立分支、獨立驗收、可獨立回退。

---

## 診斷總覽：這個專案的病根

多個 AI（Claude/Gemini/Antigravity）接力開發，每人各蓋一層，從不拆舊的。
結果是**同一功能平均存在 2.4 個入口、同一資料平均有 2.7 個來源**：

| 病 | 症狀 |
|---|---|
| 頁面按「誰寫的/什麼資料源」分，不是按「使用者要做什麼」分 | TWSE 頁、FinMind 頁、台股市場頁三頁查的是同一批東西 |
| 舊頁不拆，新頁疊上去 | dashboard.py 整檔孤兒；期貨/匯率、新聞既在合成頁內又留獨立入口 |
| 近攣生模組複製貼上 | us_calendar.py 與 tw_calendar.py 142:137 行同構 |
| 常數各自硬編碼 | 台股 50 檔池存在兩份不同版本、美股池一份，共三份 |
| 資料層無路由 | K 線 4 個來源、法人 3 個來源、估值 2 個來源，呼叫端各自挑 |

---

## R1. 導航收斂：17 頁 → 9 頁（最大刀）

### 現況證據【已驗證】
`app.py:190` TAB_RENDERERS 共 17 個入口 + 1 個相容鍵。其中：

- **`tabs/dashboard.py`（131 行）是孤兒**：`app.py:29` import 了
  `render_dashboard` 但 TAB_RENDERERS 沒有任何鍵指向它（「儀表板」鍵
  映射到 `render_market_overview`）。其內容（ADR 溢折價 + 關注名單）
  **完全**被市場總覽（含 ADR 區塊）與自選股頁覆蓋。死 import + 死檔案。
- **「期貨/匯率」雙入口**：獨立導航項 + 全球市場頁內建 tab
  （global_markets.py:17 三 tab 之一），同一 `render_futures_forex`。
- **「新聞」獨立頁**與市場總覽的大盤新聞區、個股全景的個股新聞區重疊。
- **「台股市場」「TWSE」「FinMind」三頁**都是「勾選項目 → 批次查詢」
  的同型頁，只按資料源切分：法人買賣超同時出現在台股市場（Shioaji 路徑
  不涉）、TWSE 頁（當日）、FinMind 頁（歷史）；估值同時在 TWSE
  （BWIBBU 當日）與 FinMind（per_pbr 歷史）。使用者要「查 2330 法人」
  得先知道「當日去 TWSE 頁、歷史去 FinMind 頁」——按實作分頁，
  不是按需求分頁。
- **「技術分析」獨立頁**與個股全景內的技術 tab、選股中心內的技術掃描
  三處重疊。
- `app.py:39-40` 的 `render_us_calendar_consensus`、`render_screener`
  是死 import（實際使用處都在子模組內 lazy import）。

### 重設計
新導航（9 頁）：

```
看盤     市場總覽 | 個股全景 | 自選股
決策     選股中心 | 全球市場 | 投資行事曆
管理     AI 助理 | 投資組合
進階     資料查詢（合併台股市場+TWSE+FinMind+技術分析+新聞查詢）
```

**「資料查詢」頁的設計**（本計劃核心新頁）：
- 按**資料主題**分組勾選：行情/K線、籌碼法人、估值、財報基本面、
  公司資料、公告警示、新聞、期貨匯率。
- 每主題內用「日期範圍」自動決定資料源：查今日 → TWSE 快取/API；
  查歷史區間 → FinMind；即時盤中 → Shioaji。**使用者不再需要知道
  資料源存在**。來源選擇邏輯下沉到 R4 的資料路由層。
- 既有三頁的 dispatch 函式（`_taistock_dispatch`/`_twse_dispatch`/
  `_finmind_dispatch`）合併為單一 dispatch，項目鍵全部保留
  （書籤/歷史重放相容），TAB_COMPAT_MAP 把「台股市場」「TWSE」
  「FinMind」「技術分析」「新聞」「期貨/匯率」六個舊鍵映射到「資料查詢」。

**要殺掉的東西**：
- [ ] `tabs/dashboard.py` 整檔刪除 + `app.py:29` 死 import
- [ ] `app.py:39-40` 死 import
- [ ] 「期貨/匯率」「新聞」「技術分析」「TWSE」「FinMind」「台股市場」
      六個獨立導航入口（功能全數併入「資料查詢」與既有合成頁）
- [ ] 「工具」「PDF 報告」「效能監控」從導航移到設定齒輪彈窗內
      （低頻功能不佔導航）

### 驗算（驗收條件）
1. `pytest tests/` 全綠（`test_nav_compat.py` 更新後所有舊鍵可解析到新頁）。
2. **書籤重放測試**：用改版前建立的書籤 JSON（含台股市場/TWSE/FinMind
   類型各一）在改版後點擊執行，結果正常渲染——寫成新測試
   `test_bookmark_migration.py` 固定住。
3. **render smoke**：`test_render_smoke.py` 的頁面清單改成新 9 頁，逐頁
   AppTest 渲染無例外。
4. 瀏覽器實測：9 頁逐一點開截圖；舊書籤/歷史點擊跳轉正確。
5. `grep -rn "render_dashboard" --include="*.py" .` 回傳 0 筆（tests 除外）。
6. 導航按鈕數 `grep -c "_nav_btn" app.py` 相對現版減少且與新設計一致。

---

## R2. 行事曆引擎合併：兩個近攣生模組 → 一個參數化引擎【已完成 2026-07-08】

### 現況證據【已驗證】
`us_calendar.py`（142 行）與 `tw_calendar.py`（137 行）結構完全同構：
50 檔硬編碼池 → `ThreadPoolExecutor(10)` 平行抓 yfinance
`.calendar`/`.info` → 24h SQLite 快取 → 回傳 DataFrame。差異只有：
池內容、台股加 `.TW` 後綴與中文名對照、美股多分析師評等欄位。

### 重設計（比原計畫更保守：只抽共用樣板，不硬統一 schema）
原計畫想建一個 `get_calendar_consensus(market)` 把兩市場的抓取邏輯也
合併，但深入看測試後發現 `@patch("tw_calendar.get_cache")` 這類測試
直接 patch 模組內部的 `get_cache`/`set_cache`——若把抓取邏輯整個搬進
新引擎，兩市場輸出欄位本來就不同（美股多分析師評等/目標價），沒有
必要硬湊統一 schema，改用更保守的做法：

只抽出**共用的「平行抓取 + 24h SQLite 快取 + log」樣板**到
`calendar_engine.py` 的 `fetch_consensus_pool()`；各市場專屬的
`_fetch_single_*` 抓取函式與欄位定義**留在原檔不動**，
`get_tw_calendar_consensus_data()`/`get_us_calendar_consensus_data()`
改成呼叫共用函式的一行式包裝。

**要殺掉的東西**：兩份重複的 ThreadPoolExecutor/快取/log 樣板
（淨刪約 75 行：兩檔各自的 ~35 行重複邏輯併成 1 份 ~50 行共用函式）。

**附帶修復**：`tabs/market_overview.py:391` 的
`qw.tw_calendar.get_tw_calendar_consensus_data()` 恆定
`AttributeError`（`query_wrapper` 模組沒有 `tw_calendar` 屬性，本輪
瀏覽器測試時就抓到這個警告 log），導致「今日除息」區塊一直安靜地
查詢失敗。已改為直接 `import tw_calendar`。

### 驗算（全數通過）
1. ✅ `_fetch_single_tw_calendar_consensus`/`_fetch_single_calendar_consensus`
   完全不動，schema 保證不變（沒有另建 fixture 測試的必要，因為抓欄位
   的程式碼本身沒有被觸碰）。
2. ✅ `test_us_calendar.py`/`test_tw_calendar.py` 既有測試的
   `@patch("tw_calendar.get_cache")`/`@patch("us_calendar.get_cache")`
   改指 `@patch("calendar_engine.get_cache")`（快取邏輯搬去哪裡就 patch
   哪裡），6 項全綠；全套 pytest + ruff lint 過。
3. ✅ 瀏覽器實測：市場總覽「今日除息」區塊改好後正確顯示「4 檔今日
   除息」附代號與預估 EPS（先前恆定 AttributeError 靜默失敗）。

---

## R3. 股票池統一：三份硬編碼 → 單一來源【已完成 2026-07-08】

### 現況證據【已驗證】
- `tw_calendar.py:17` `TW_SCREENER_POOL`（50 檔）
- `tabs/technical_scanner.py:12` `TW_BLUE_CHIPS`（50 檔，**內容與上者
  不同**——technical_scanner 版含 2888/2889/2890 等金融股序列，
  tw_calendar 版含 3008/3045/4938 等電子股，兩份「台灣50」根本不一樣）
- `us_screener.py:16` `US_SCREENER_POOL`（50 檔，us_calendar 也用它）

### 重設計
建 `stock_pools.py`：

```python
TW_TOP50: list[str]   # 以臺灣50指數實際成分股為準（成分股用 TWSE
                      # 官方資料校正一次，寫入時附資料日期註解）
US_TOP50: list[str]   # 現行 US_SCREENER_POOL 遷入
```

三個使用端全部改 import `stock_pools`，舊常數刪除。
**加一個守門測試**：`test_stock_pools.py` 斷言全案 grep 不到第二份
50 檔硬編碼清單（防止未來 AI 接力時又複製一份）。

### 驗算（全數通過）
1. ✅ 派 subagent 查證台灣50官方名單（MoneyDJ 0050 ETF 實際持股，
   2026-07-08 查閱，權重加總≈99.3%），與兩份舊清單逐一核對：
   `TW_SCREENER_POOL` 命中 30/50（60%），`TW_BLUE_CHIPS` 命中僅
   19/50（38%，混入 2888-2897/2801-2851 區段已過時的金控代號）。
   採用查證後的正確50檔名單建 `stock_pools.py`。
2. ✅ `pytest tests/` 全綠（含新增 `test_stock_pools.py` 3 項守門測試）；
   ruff lint 過。
3. ✅ `grep -rn "TW_BLUE_CHIPS\|TW_SCREENER_POOL\|US_SCREENER_POOL"`
   只剩 alias import（`from stock_pools import TW_TOP50 as
   TW_SCREENER_POOL` 等），無第二份清單定義。
4. ✅ 瀏覽器實測選股中心→技術掃描，log 確認掃描迭代新股票池代號
   （3008/2880/3443/7769/3665 等新名單特有代號）並正常回傳 K 線資料。

---

## R4. 資料路由層：同主題多來源 → 單一入口自動選源

### 現況證據【已驗證】
| 資料主題 | 現有來源 | 呼叫端自己挑 |
|---|---|---|
| K 線 | Shioaji 分K重採樣 / FinMind 日K / yfinance / Futu | `_cached_kbar` 只處理台美分流，FinMind 日K另一條路（cli.py:285），Futu 又一條 |
| 三大法人 | TWSE T86（當日）/ FinMind（歷史）/ 本地 CSV 快取 | 三頁各接各的 |
| 估值 PE/PB/殖利率 | TWSE BWIBBU（當日）/ FinMind per_pbr（歷史） | 同上 |
| 融資融券 | TWSE MI_MARGN（當日）/ FinMind margin_short（歷史） | 同上 |

`daily_job.py` 另外自帶第 4 套 TWSE 端點表（P2.2 已查證記錄）。

### 重設計
建 `datasources/router.py`，對外只暴露主題函式：

```python
def get_kbar(code, start, end) -> pd.DataFrame
    # 台股數字代號：日期含今日→Shioaji；純歷史→FinMind；
    # 美股/港股：yfinance；HK.xxxxx 格式：Futu
def get_institutional(code=None, start=None, end=None) -> pd.DataFrame
    # start/end 皆空或=今日→TWSE（本地CSV優先）；否則→FinMind
def get_valuation(code=None, start=None, end=None) -> pd.DataFrame
def get_margin(code=None, start=None, end=None) -> pd.DataFrame
```

- 回傳欄位**在 router 層統一命名**（中文欄位，一份對照表），
  呼叫端不再看到來源差異。
- R1 的「資料查詢」頁與個股全景/市場總覽全部改走 router。
- `daily_job.py` 的 `fetch_market()` 改呼叫
  `router.get_institutional()`（吸收 P2.2 已查好的 T86 19 欄位官方對映
  + 一併修正股/張單位不一致 bug：統一原始股數，顯示標籤標「股」）。
- P2.5 剩餘的 13 個 yfinance 直呼檔案，屬 K 線/報價類的一併收進
  `get_kbar`/`query_yfinance_index`，收不進的（`.info`/`.calendar`
  特殊呼叫）明文標註豁免原因。

**要殺掉的東西**：
- [ ] `daily_job.py` 的 `_TWSE_DAILY_ENDPOINTS` 私有端點表（改引 router/
      twse_client 共用定義）
- [ ] `fetch_market()` 直呼已死的 openapi T86（P0 遺留的最後一塊）
- [ ] 各 tabs 內按資料源 if/else 挑來源的散裝邏輯

### 驗算（本塊涉財務數字，驗收最嚴）
1. **數字對帳**：改版後選一個真實交易日，`router.get_institutional()`
   輸出的外資/投信/自營買賣超合計，與 TWSE 官網當日 T86 頁面人工核對
   **逐項相等**（±0）。核對截圖存 docs/。單位（股）明確標示。
2. **來源切換測試**：`test_router.py` 用 mock 驗證「今日→TWSE、
   歷史→FinMind、美股→yfinance、HK.→Futu」四條路由規則各自命中，
   且欄位名輸出一致（schema 斷言）。
3. `python daily_job.py` 本機實跑一次全綠（Step 1-7），輸出的
   `data/market/*.csv` 與 PG 寫入數字與舊版同日輸出一致（法人欄位
   因舊版本來就是壞的，以 TWSE 官網為準）。
4. 全套 pytest + render smoke + 瀏覽器實測法人/估值/K線三種查詢。
5. NAS 部署後隔日檢查 GitHub Actions 綠燈 + 選股郵件數字抽查一檔
   與 TWSE 官網一致。

---

## R5. CLI 凍結：停止雙軌維護

### 現況證據【已驗證】
`cli.py`（414 行，47 選單）與 Web UI 功能完全平行——每加一個查詢
要改兩處。本輪 session 修的 bug 全部只在 Web 側，CLI 側同款壞點
（如 TWSE 匯出遺漏影響的 20 函式）沒人發現，證明 CLI 實際上已無人日常使用。

### 重設計
- CLI **凍結**：檔頭加註「維護凍結，新功能一律只進 Web/router；
  CLI 僅保證現有 47 項可跑」。
- R4 完成後，cli.py 的查詢呼叫改指 router（一次機械替換），此後
  CLI 自動繼承 router 修復，不再需要獨立維護。
- 不刪除（`查詢工具.bat` 使用者仍可能雙擊），但從 CLAUDE.md 的
  「主要檔案」表降級標註。

### 驗算
1. 凍結註記後抽測 5 個代表選單（1/16/28/41/46）實跑正常。
2. R4 接上後同 5 項重測，輸出欄位不變。

---

## R6. 掃尾（合併原 P4 + 新發現）【本輪 2026-07-08 大部分完成】

- [x] **刪 `deepseek_engine.py` 墊片**——原計畫假設「只剩 stock_page.py:561
      一處呼叫」是錯的，實測有 **8 個檔案、9 處** import
      （stock_lookup.py、tabs/news.py、tabs/ai_chat.py、tabs/us_stocks.py、
      tabs/market_overview.py、tabs/stock_page.py×3、
      scripts/verify_non_tw_features.py、tests/test_ai_report.py）。
      全數改為 `from ai_engine import ...` 後刪除墊片檔案。
    - **意外抓到一個真正的功能缺口**：`tabs/stock_page.py:536` 對台股
      呼叫 `generate_tw_stock_report`，但這個函式**從沒被實作過**
      （`ai_engine.py` 只有 `generate_us_stock_report`），代表**台股的
      「AI 個股健檢」按鈕點下去必定顯示錯誤**，美股那顆是正常的。
      這不是簡單改名可解，是要新寫一段 AI 報告邏輯，已用
      `spawn_task` 分出去（task_225ba935）交給獨立 session 處理，
      現場只加 TODO 註解標註已知缺口，不倉促用猜的補上去。
- [ ] **`config.py` ConfigManager 相容類——暫緩，工程量遠超預期**：
      grep 實測發現被 **5 個測試檔案、80+ 處**呼叫
      （test_config.py/test_bookmark_flow.py/test_history_flow.py/
      test_error_handling.py/conftest.py），要拔掉它等於要把這 80+ 處
      測試改寫成 function-based API（`load_config()`/`save_config()`），
      這已經是獨立量級的任務，不是掃尾範圍，留給專門 session。
- [x] **TAB_COMPAT_MAP 清恆等映射**：刪除 6 組 key==value 的無效映射
      （台股市場/技術分析/TWSE/FinMind/新聞/工具），`_resolve_tab()` 用
      `.get(key, key)` 保底，行為不變。「新增 R1 的六個新映射」待 R1
      實際執行時再做（現在做是無的放矢，R1 還沒發生）。
- [x] **`^TPEx` 櫃買指數卡片修好**：正確 Yahoo 代號是 `^TWOII`（原代號
      `^TPEx` 打錯字，yfinance 一律 404，市場總覽永遠空白的第二張卡）。
      瀏覽器實測確認顯示「445.4 ▲5.9」等真實數字。
- [x] **`render_alerts` 的 `module 'query_wrapper' has no attribute
      'tw_calendar'` 警告**：已在 R2 commit 一併修掉
      （`tabs/market_overview.py:391` 的 `qw.tw_calendar.xxx()` 恆定
      AttributeError，改為直接 `import tw_calendar`）。

### 驗算（已完成項目）
逐項：grep 證明引用歸零 → pytest 全綠 → 瀏覽器抽測受影響頁面。全數通過。

---

## 執行順序與工程量

| 順序 | 塊 | 工程量 | 風險 | 依賴 |
|---|---|---|---|---|
| 1 | R3 股票池統一 | 半天 | 低 | 無 |
| 2 | R2 行事曆引擎合併 | 半天 | 低 | R3 |
| 3 | R6 掃尾 | 半天 | 低 | 無 |
| 4 | R4 資料路由層 | 2-3 天 | **高**（財務數字） | 無 |
| 5 | R1 導航收斂 + 資料查詢頁 | 2-3 天 | 中（UX 大改） | R4 |
| 6 | R5 CLI 接 router | 半天 | 低 | R4 |

原則：低風險先行熱身並淨刪代碼；R4 是地基、必須在 R1 之前；
R1 是使用者可見的最大改變，放在資料層穩定之後。
每塊獨立 commit 串 + 獨立 CI 綠燈 + 獨立瀏覽器驗收，出問題單塊回退。

## 全程通用驗收（每塊完成都要過）

1. `ruff check . --select E9,F63,F7,F82` 零錯誤
2. `pytest tests/` 全綠（xfail 之外零失敗）
3. CI（GitHub Actions）綠燈
4. 瀏覽器實測受影響頁面，截圖留證
5. 淨行數變化為**負**或持平（本計劃是刪減型重構；若某塊淨增行數，
   需在 commit message 說明原因）
6. 推 NAS 後容器重啟正常、網站可開

## 預期總成果

- 導航 17 → 9 頁；使用者不再需要知道「資料源」概念
- 淨刪除 ≥ 800 行重複代碼（dashboard 131 + 行事曆 ~200 + 池 ~100 +
  散裝來源挑選邏輯 + 死 import/舊墊片）
- 同一資料主題單一入口、單一欄位契約；daily_job 與 Web 共用資料層，
  「修一邊忘一邊」類 bug（本輪抓到 3 起）結構性絕跡
- P2.2 遺留的 T86 死端點 + 股/張單位 bug 在 R4 一併根治
