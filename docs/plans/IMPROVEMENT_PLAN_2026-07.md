# 專案改進計劃書（2026-07-07）

> 依據：三路審查（架構、安全、運維）實際掃描結果，非印象式建議。
> 證據標註：【驗證】= 實測/實讀；【推測】= 待確認。
> 完整審查報告：架構與運維原始報告存於 session scratchpad（本檔已吸收全部結論）。

---

## 總評

專案基本盤比預期健康：
- ✅ 現行程式碼**無硬編碼秘密**（全 repo grep 查無）；`get_secret` 順序（env → st.secrets → config.json）設計正確
- ✅ CI 有跑 pytest + ruff（push/PR 觸發）
- ✅ daily_job 防禦性設計良好：空 DataFrame 不覆寫 CSV、PG 失敗完全旁路、單一 endpoint 失敗不連坐
- ✅ tabs/ 25 個頁面無孤兒；print/DataFrame 分層已解決（print 集中 cli.py）
- ✅ pg_db.py SQL 全參數化；verify=False 僅限 TWSE 舊版 API 必要的 3 個檔案

主要問題集中在四塊：**金鑰歷史外洩（唯一高風險）**、**文件地圖嚴重過時**、**query_wrapper 樣板膨脹**、**雙寫/多套並存的重複邏輯**。

---

## 執行進度（2026-07-07 更新）

已完成並驗證：
- ✅ **P0.2/P0.3 合併處理**：真正根因不是「screener 常態無命中」，是 **daily.yml 的
  `git add disposition_cache.json data/` 被 `.gitignore` 的 `*.json` 規則擋下，
  導致 GitHub Actions 自 2026-05-18 起連續失敗、100% 失敗率、持續 50 天沒有
  任何資料進 repo**。已修 `.gitignore`（加 `!disposition_cache.json`）+
  `daily.yml`（push 前加 `git pull --rebase`），手動觸發 workflow 驗證成功，
  `data/market/2026-07-06.csv` 與 `disposition_cache.json` 已確認進 repo。
- ✅ **P1.1 文件整頓**：CLAUDE.md 檔案表重寫反映 datasources/ 分層；
  AGENTS.md、GEMINI.md（兩者皆與 CLAUDE.md 內容重複/過時且有格式錯亂）
  瘦身為指標檔。
- ✅ **P1.2 根目錄清雜**：刪 shioaji.log/.coverage/htmlcov/T4_10142(空殼)/.firecrawl，
  .gitignore 補 `.firecrawl/`。
- ✅ **P1.3 本機測試環境**：FinMind 用 `--no-deps` 裝上（原版 metadata 拉舊 pandas
  在 py3.13 編不過，過度嚴格是它自己的問題）；抓到真正 bug——
  `tests/test_dashboard_pinning.py`、`tests/test_dispatch_registry.py` 在
  **模組頂層永久替換 `sys.modules['streamlit']` 且從不還原**，污染同一 pytest
  process 內後續收集的所有測試檔案，這才是「336 全綠」本機驗不了的真因
  （不是環境缺依賴）。已修復（改用 save/restore pattern），collection 錯誤
  8→0。
- ✅ **附帶抓到並修復 3 個生產環境/測試環境真炸點**：
  1. `tabs/calendar_tab.py`：`投資行事曆→台股法說/除息` 分頁對不存在的
     「日期」欄位做比較，**每個使用者點進去必炸**（KeyError）。已修為用
     「財報公佈日」/「除息日」計算排序欄位。
  2. 🟡 `market_overview.py`/`us_calendar_tab.py` 在全套測試下才會炸的真因：
     `test_dashboard_pinning.py`/`test_dispatch_registry.py` 在 mock streamlit
     生效期間真的執行 `from app import ...`，導致 `app.py` 整條 import chain
     （`dispatch.py`、`tabs.market_overview` 等）被**永久初始化並快取進
     `sys.modules`**——這些子模組自己的 `import streamlit as st` 從此永遠
     綁定假物件，只還原 `sys.modules['streamlit']` 救不了已快取的子模組。
     **嘗試過的修法（已還原，未採用）**：在兩個測試檔案的 mock 使用結束後
     連鎖清掉所有專案自有模組的 sys.modules 快取，本機驗證 3 輪
     `test_render_smoke.py` 穩定 9/9，但推上 CI 後才發現**引入 12+ 個新
     regression**（`test_caching.py`/`test_tw_calendar.py`/`test_us_calendar.py`/
     `test_us_screener.py`/`test_shioaji_market.py`/`test_market_history.py`
     等）——因為連鎖清除破壞了同一測試檔案內 `@patch(...)` 裝飾器與已匯入
     函式物件之間的模組實例一致性（已匯入的函式仍綁定「清除前」的舊模組，
     但 `@patch` 卻對「清除後重新匯入」的新模組生效，兩者對不上）。
     **已退回為僅還原 `sys.modules['streamlit']`（不連鎖清除）**，本機驗證
     退回後測試套件回到修復前的基準（僅 `test_render_smoke.py` 3 個既有
     失敗，無新增 regression）。這 3 個失敗本身**已確認是測試環境限定**
     （AppTest 不像正式部署那樣讓 `st.cache_resource` 跨執行個體持久），
     不影響真實使用者，留待下次用更謹慎的隔離手法（例如把這兩個測試檔案
     強制丟進獨立 subprocess 執行）處理。
  3. 順手發現 `sqlite_cache.py` 的快取路徑（`~/.app_config/cache.db`）
     沒有測試隔離，所有測試都讀寫正式環境同一個快取檔案。已在
     `tests/conftest.py` 頂層加上 session 級隔離（`APP_CACHE_DIR` 指向臨時
     目錄，必須在任何模組 import 之前設定才有效）。
- 🟡 **新發現、屬既有問題非本次引入**：`test_us_calendar.py`/
  `test_us_screener.py`/`test_us_stock.py` 偶發失敗，根因是 yfinance API
  rate limit（"Too Many Requests"）——測試直接打真實網路 API 沒有 mock，
  本質上就是 flaky。未修，建議歸入 P3.1（補測試 mock）一併處理。
- ✅ **P2.1 啟動（第一批，query_wrapper.py 瘦身）**：因 test_query_wrapper.py
  安全網比預期薄弱（`TestRankingQuery` 整組斷言被註解掉，等於沒在驗證行為），
  改用「小批次 + 瀏覽器實測」策略而非一次機械改寫全部 53 個函式。
  - 在 `query_wrapper.py` 新增 `tracked_query(name, label, history_category,
    history_payload, cache_key_fn, track_cache_hit=True)` 裝飾器，抽出
    「計時 + cache-hit 記錄 + perf_tracker + log + add_history + 統一錯誤
    處理」樣板，回傳型別維持 `pd.DataFrame`（錯誤時附「錯誤」欄位），
    與原樣板行為完全對齊。
  - 遷移 3 個代表性函式驗證裝飾器涵蓋所有已知變體：`query_ranking`
    （有輸入驗證guard，抽成 `_query_ranking_tracked` 避免驗證失敗也被
    誤記錄 history/perf）、`query_snapshot`（標準樣板）、`query_dividend`
    （`track_cache_hit=False` 變體，原本就沒有手動 cache-hit 追蹤層）。
  - 驗證：`pytest tests/test_query_wrapper.py` 24 過；獨立 Python 腳本比對
    無效輸入/正常路徑的 side effect 呼叫次數與原邏輯一致；**啟動真實
    Streamlit app 用瀏覽器實際點擊「台股市場→漲幅排行+個股即時快照」**，
    確認結果正確渲染、無崩潰，console log 顯示 cache-hit/miss 與計時正常
    （cache hit 時 0.8ms、miss 時 374ms，數字合理）。全套 pytest + ruff
    lint 通過。
  - **第二批**：FinMind 籌碼/基本面群組 9 個函式一次遷移（`query_institutional_investors`/
    `query_institutional_summary`/`query_day_trading_volume`/`query_margin_short`/
    `query_foreign_shareholding`/`query_securities_lending`/`query_month_revenue`/
    `query_financial_statement`/`query_balance_sheet`），與 `query_dividend`
    完全同款式（`track_cache_hit=False`），驗證方式相同：獨立腳本比對全部
    9 個函式的正常/錯誤路徑（用不同代號避開 SQLite 快取干擾）+ 全套
    pytest/ruff 過。瀏覽器實測時發現這個文字輸入框的 fill 有 React 狀態
    同步的工具限制（非本次程式碼改動造成，未觸及輸入處理邏輯），改用
    UI checkbox 標籤渲染正確作為輔助驗證證據。
  - **第三批（TWSE 擴充查詢群組，20 函式）**：新增 `simple_tracked_query(
    history_category, history_payload)` 裝飾器，對應 TWSE 擴充查詢群組
    最簡化樣板（原本就沒有計時/perf_tracker/log，只有 try/except+add_history）。
    遷移 19 個函式（`query_twse_mi_index`/`query_twse_stock_day_avg`/
    `query_twse_monthly`/`query_twse_annual`/`query_twse_qfiis_cat`/
    `query_twse_qfiis_top20`/`query_twse_newlisting`/`query_twse_suspend_listing`/
    `query_twse_apply_listing_local`/`query_twse_apply_listing_foreign`/
    `query_twse_news_list`/`query_twse_event_list`/`query_twse_dividend_policy`/
    `query_twse_fund_basic`/`query_twse_monthly_revenue`/`query_twse_income_statement`/
    `query_twse_balance_sheet_openapi`/`query_twse_etf_rank`/`query_twse_esg`）
    + `query_twse_company`（標準 `tracked_query`，`track_cache_hit=False`）。
    - **意外抓到一個預先存在、與本次改動無關的生產 bug**：驗證腳本發現
      `sinopac_query.query_twse_mi_index` 等 20 個函式**完全不存在**——
      根因是 `datasources/__init__.py` 的 TWSE 顯式 re-export 清單只列了
      7 個舊函式，從沒同步更新過 `twse_client.py` 早就存在的 20 個新函式。
      這代表**這 20 種 TWSE 查詢（大盤指數/外資持股前20/股利分派/處置股外
      的擴充查詢等）從一開始就必定 `AttributeError` 進 except，一直悄悄
      回傳「查詢失敗」**，跟架構審查點出的「TWSE 抓取邏輯雙寫、修一邊忘
      一邊」是同一類問題的新案例。已修：`datasources/__init__.py` 補齊
      20 個函式的 import（純新增，低風險）。
    - 驗證：獨立腳本用獨立 `APP_CACHE_DIR` + 先測錯誤路徑再測成功路徑
      （避開 `st.cache_data` 記憶體快取與 SQLite 快取的干擾），全部 20 個
      函式的正常/錯誤路徑與 `add_history` payload 逐一比對過關；全套
      pytest + ruff lint 通過；**瀏覽器實測 TWSE 分頁**勾選「大盤指數、
      外資持股前20、股利分派」（3 個原本必壞的函式）並確認查詢，
      3 個結果面板都成功顯示「📊 查詢結果」而非錯誤訊息，證實這個
      預先存在的 bug 真的被修好了。
  - **剩餘 21 個函式（本地快取優先群組）決策：保留原樣，不遷移**——
    深入檢查後發現 `daily_all`/`valuation`/`institutional`/`margin` 這 4 個
    函式的 `{"error":...}` dict 回傳**不是意外不一致，是刻意設計**：
    `ui_components.py:display_result()` 明確對 `dict` 且含 `"error"` 鍵的
    情況呼叫 `st.error()` 顯示醒目紅色警示框，而 `DataFrame({"錯誤":...})`
    只會安靜地變成表格裡的一列資料，遠不如紅框醒目。若真的「統一」成一律
    回傳 DataFrame，會實質**降級這 4 個查詢的錯誤顯示醒目度**——這是
    UX 決策而非單純技術債，已詢問使用者，決定**保留 dict 契約**。
    這 6 個函式（含 `disposition`/`notice`，同樣有「本地 CSV 快取優先」
    的早退分支）的控制流程本身也與裝飾器結構不符（本地快取命中時要在
    計時/perf_tracker 之前就提早 return），勉強套用裝飾器只會增加風險
    换不到明確收益，故全數維持原樣不動。
  - **P2.1 最終進度：32/53 函式遷移完成，且已是本次可安全遷移的上限**
    （剩餘 21 個因上述 UX/控制流程原因主動排除，非遺留待辦）。裝飾器
    設計驗證涵蓋 4 種樣板變體（標準、帶輸入驗證、無 cache-hit 追蹤、
    最簡化無計時），`query_wrapper.py` 從原本 1,424 行的重複樣板中
    抽出共用邏輯，可讀性與未來新增查詢的一致性明顯改善。附帶修復 2 個
    生產環境真炸點（`calendar_tab.py` 必炸 + TWSE 20 函式匯出遺漏）。

---

## P0 — 緊急（本週內，半天工作量）

### 0.1 輪換外洩金鑰 🔴 高風險【驗證】
Shioaji API_KEY/SECRET_KEY 與 FINMIND_TOKEN 存在於 **4 個歷史 commit**
（`6935c93`、`127b705`、`e261331`、`b37fee6`），repo 已推 GitHub。
即使現行檔案已清除，任何人 clone 後 `git log -S` 就能撈出。

- [ ] 永豐金後台重發 API KEY（目前是模擬環境金鑰，風險較低但仍應換）
- [ ] FinMind 重新登入取得新 token
- [ ] 新金鑰只放 `.env` / Streamlit Secrets / config.json（皆已 gitignore）
- [ ] （選做）`git filter-repo` 清歷史 + force push——因 NAS hook 依賴 main，
      需同步重設 NAS bare repo，工程不小；**輪換即可消除實際風險，清歷史可緩辦**

### 0.2 查明 `data/screener/` 目錄消失【驗證異常，原因未明】
目錄完全不存在（0 檔案）。可能是「外資+投信雙買超」近期真的無命中，
也可能 `run_screener()`（daily_job.py:215-270）資料源壞了默默回空。
- [ ] 手動跑一次 `python daily_job.py` 看 Step 3/4 輸出
- [ ] 若邏輯正常但常態無命中 → 在 log 明確印出「篩選 0 檔」而非無聲跳過

### 0.3 daily.yml 加 push 衝突保護【驗證】
daily.yml:39-45 只有 add→commit→push，無 pull/rebase。NAS（20:00）與
Actions 備援（20:05）同日都成功時，後者必因 non-fast-forward 紅燈。
- [ ] push 前加 `git pull --rebase origin main`
- [ ] 同理檢查 NAS `run_daily.sh` 的 pull/push 順序（防 disposition_cache.json
      兩端競態 →「重複通知/漏通知」）

---

## P1 — 文件與環境整頓（1 天）

### 1.1 重寫 CLAUDE.md + 合併三胞胎手冊【驗證】
- CLAUDE.md 稱 sinopac_query.py 是「主工具含全部函式」——實際只剩 **12 行墊片**，
  邏輯已拆到 `datasources/`（5 client、1,716 行）+ `cli.py`（414 行）。
  檔案表缺 datasources/、cli.py、dispatch.py、caching.py、pg_db.py 等。
  **錯誤地圖持續誤導所有接力開發的 AI（Claude/Gemini/Codex）。**
- AGENTS.md 與 CLAUDE.md 各 57KB，diff 僅 68 行（純 Claude↔Codex 字樣替換），
  加 GEMINI.md 三份必然漂移。
- [ ] 建單一 `PROJECT.md` 作事實來源，重寫檔案表反映 datasources 分層現況
- [ ] CLAUDE.md / AGENTS.md / GEMINI.md 改為 3 行指標檔指向 PROJECT.md
- [ ] 歷史 session 紀錄（佔 CLAUDE.md 大半篇幅）搬到 `docs/history/`

### 1.2 根目錄清雜【驗證】
| 項目 | 處置 |
|---|---|
| `shioaji.log`、`.coverage`、`htmlcov/` | 刪除 + 補 .gitignore |
| `T4_10142/`（無關 VBA 目錄） | 移出專案 |
| `.firecrawl/` | 加 .gitignore |
| `disposition_cache.json`（執行期狀態檔在根目錄） | 移到 `data/` |

### 1.3 本機測試環境修復【驗證】
本機 pytest collection 失敗 8 errors：缺 `FinMind` 套件 + `streamlit` 安裝殘破
（`'streamlit' is not a package`）。「336 全綠」目前只有 CI 能證明。
- [ ] `pip install -r requirements.txt` 重建本機環境（或建 venv）
- [ ] 修好後本機跑一次全綠存證

---

## P2 — 核心重構（2-4 天，分批做）

### 2.1 query_wrapper.py 瘦身 + 統一錯誤契約【驗證】（最高技術收益）
1,424 行 = ~50 組複製貼上的 `_cached_X` + `query_X` 雙函式樣板；
錯誤契約三態混用（8 處回 `{"error":...}` dict、其餘拋例外或空 DataFrame），
所有呼叫端被迫逐處 isinstance 防守。
- [ ] 把「計時 + add_history + 錯誤包裝」抽成裝飾器（併入 `caching.cached_query` 參數）
- [ ] 錯誤契約統一：一律回 DataFrame，錯誤拋自訂 `QueryError`
- [ ] 對齊全部 tabs/dispatch 的錯誤處理路徑（有 test_query_wrapper.py 保護）
- [ ] 預期 1,424 → ~500-600 行；可再按資料源拆 `query_wrapper/` 套件與 datasources 鏡像

### 2.2 daily_job 改用 datasources/twse_client【已完成 2026-07-09】

TWSE 端點表雙寫：twse_client.py 與 daily_job.py:404 各一份，
`fetch_market()`（daily_job.py:147，Step 1 大盤快照用）還在呼叫**已知廢棄**
的 openapi T86 端點；`fetch_twse_daily_cache()`（daily_job.py:404，Step 6
CSV 快取用）**已經修好**，用的是 rwd 版正確端點。

**原以為是簡單換 URL，深入調查後發現需要精確欄位對映＋有一個獨立的單位
不一致 bug，暫緩不做**：

1. **欄位對映（已查證 TWSE 官方文件，可直接用）**：rwd T86
   （`https://www.twse.com.tw/rwd/zh/fund/T86?date=YYYYMMDD&selectType=ALL`）
   回傳 19 欄，依序為：
   ```
   0 證券代號  1 證券名稱
   2 外陸資買進股數(不含外資自營商)  3 外陸資賣出股數(不含外資自營商)
   4 外陸資買賣超股數(不含外資自營商)          ← 一般認定的「外資買賣超」
   5 外資自營商買進股數  6 外資自營商賣出股數  7 外資自營商買賣超股數
   8 投信買進股數  9 投信賣出股數  10 投信買賣超股數
   11 自營商買賣超股數（合計）
   12-14 自營商買賣超股數(自行買賣) 買進/賣出/買賣超
   15-17 自營商買賣超股數(避險) 買進/賣出/買賣超
   18 三大法人買賣超股數（合計）
   ```
   對應 `run_screener()`/`fetch_market()` 需要的英文欄位：
   `Code`=欄0、`Name`=欄1、`ForeignInvestmentNetBuySell`=欄4、
   `InvestmentTrustNetBuySell`=欄10、`DealerNetBuySell`=欄11。
   rwd 回傳值為**原始股數**（字串含千分位逗號，需 `str.replace(",","")` 轉數字）。

2. **獨立發現的單位不一致 bug（跟本項無關，但會被本項的修復觸發）**：
   `fetch_market()` 的彙總印出 `f"外資 {...} 億股"`（`sum()/10000`），
   代表原始（已死）openapi 欄位假設是**股數**；但 `run_screener()`
   （daily_job.py ~Step 3）逐股顯示卻直接 `int(r["ForeignInvestmentNetBuySell"])`
   標成「外資買賣超**(張)**」（張=1000股）未除以 1000。
   因為 `t86_df` 從 2026-05-18 起就一直是空的（Step 0 大洞，本次已修好
   pipeline 斷線），`run_screener()` 這段程式碼**從沒真的用真資料跑過**，
   這個潛在的股/張標示錯誤一直是休眠狀態。若現在只接欄位對映不修這個，
   彙總數字會對，但選股信件的逐股表格數字會差 1000 倍。

3. **執行結果（2026-07-09，R4 第一刀）**：
   - `datasources/twse_client.py` 新增 `query_twse_institutional_numeric()`：
     用已驗證正確的 rwd T86 端點，依上表對映輸出英文欄位＋數值型別
     （原始股數）。既有 `query_twse_institutional()`（中文欄位、給頁面
     顯示用）完全不動，避免動到 5 個既有呼叫端。
   - `daily_job.py` `fetch_market()` 改呼叫這個新函式，取代恆死的
     `openapi.twse.com.tw/v1/fund/T86`。
   - **意外發現第二個 bug（比 P2.2 原判斷更嚴重）**：`fetch_market()`
     彙總原本 `sum()/10000` 標「億股」，先前判斷「已經正確」是錯的——
     實測 2026-07-08 真實資料，外資買賣超合計 /10000 算出
     `-29827.82 億股`（荒謬，超過全市場實際流通股數），改成 `/1e8`
     才是合理量級（`-2.98 億股`）。**t86_df 從 2026-05-18 起就是空的，
     這段彙總邏輯從沒被真資料跑過，之前的「正確」判斷只是沒機會被戳破。**
   - `run_screener()` 個股顯示欄位改標「外資買賣超(股)」「投信買賣超(股)」，
     不除 1000（原始股數，不是張）。
   - **單位換算下沉到外部系統邊界，不動外部 schema**：Notion 資料庫既有
     屬性名叫「外資買賣超(張)」、PostgreSQL `screener_daily` 表欄位叫
     `foreign_net_k`/`trust_net_k`（`_k`＝張）——兩處都不改外部 schema，
     改成在 `write_screener()`／`pg_db.upsert_screener()` 寫入前
     `/1000` 換算回「張」，欄位語意與資料庫內既有假設一致。
   - **驗算（真實資料）**：monkeypatch 抓 2026-07-08 T86，
     `run_screener()` 篩出 63 檔外資+投信雙買超（如 2892第一金外資買超
     2,128萬股、2303聯電2,308萬股），彙總「外資 -2.98 投信 +0.42
     自營 -9.61 億股」與當日大盤跌 2.31% 方向一致，數字來源就是
     TWSE 官方 rwd 端點本身（非第三方轉載，無需再找「官網」交叉比對）。
   - pytest 全綠、ruff 全綠。
   - `_TWSE_DAILY_ENDPOINTS`（Step 6 CSV 快取用）維持不變——那段本來就
     用 rwd 正確端點，只是跟 Step 1 這段各自維護，之後有空再合併成
     共用函式（非本次範圍，不影響正確性）。

### 2.3 快取收斂【部分完成 2026-07-07】
四種快取路徑並存：sqlite_cache 手寫呼叫、`@cached_query` 裝飾器、
裸 `@st.cache_data`（query_wrapper.py:219）、`_read_twse_local()` CSV 讀取。
- [ ] 全數收斂到 `@cached_query`（暫緩，中工程，未做）
- [ ] CSV fallback 移入 twse_client 作為 fetch 層邏輯（暫緩，未做）
- [x] `daily_job.py` Step 7 加呼叫 `sqlite_cache.clear_expired_cache()`
      （每日執行一次，避免 cache.db 無多人呼叫、無限緩慢增長；
      驗證：獨立呼叫確認清理正常執行，全套 pytest + ruff 過）

### 2.4 ui_components.py 拆檔（機械搬移，低風險）【已完成 2026-07-07】
1,156 行三種職責：通用顯示 / 側邊欄設定 / 美股+Shioaji 專屬渲染。
- [x] 拆 `ui/display.py`(366行)、`ui/sidebar.py`(374行)、`ui/us.py`(176行)、
      `ui/shioaji.py`(267行)
- [x] `ui_components.py` 瘦身為 41 行 re-export 墊片，全部 13 個既有呼叫端
      （app.py、dispatch.py、tabs/* 等）零改動維持相容
- 驗證：全套 pytest（含 test_ui_components.py/test_ui_integration.py 61 項）
  + ruff lint 通過；瀏覽器實測「台股市場→個股日K」勾選+查詢，結果面板正常
  出現、server log 無 traceback（僅既有無關的 yfinance ^TPEX 錯誤）。

### 2.5 yfinance 統一封裝【部分完成 2026-07-08，重新盤點】
重新盤點實測為 **18 個檔案**（原估 15 個），且各檔呼叫模式差異大
（`.info`/`.history()`/`.calendar`/`download()`），沒有像 P2.1 那樣能一次
套用的公版，每檔需個別判斷，跟原計畫「建 yfinance_client.py 統一封裝」
的單次工程假設不同，已詢問使用者改成小批次逐一評估：

- [x] `tabs/technical_scanner.py`：檢查後發現**已有合理設計**——
  `_fetch_kbar()` 先試 `query_wrapper.query_daily_kbar()`（有快取），
  失敗才 fallback 到直呼 yfinance，不是真正「繞過快取」，不需要修。
- ✅ **附帶抓到並修復一個真炸點**：`tabs/watchlist_monitor.py` 三處
  `yf.T(...)` 打錯字（yfinance 沒有 `T` 屬性，跟 `market_overview.py`/
  `stock_page.py` 已修過的同一個字打錯，這檔案漏改）。影響：
  `_compute_extra_metrics()` 的 AttributeError 被外層 try/except 靜默吞掉，
  「距52週高%」「量比」兩欄一直是空的；`_fetch_yfinance_watchlist()`
  （Shioaji 快照為空時的 fallback）完全沒有防護，觸發就會讓整個自選股
  監控分頁崩潰。已修正並用獨立腳本驗證兩個函式都能正確算出數字。
- [x] `tabs/market_overview.py` 指數卡片加快取（大盤指數/櫃買指數/
  台指期基差/費半，共 5 處呼叫）：在 `query_wrapper.py` 新增
  `query_yfinance_index(symbol, period="5d")`，套用既有 `@cached_query`
  （ttl=300 記憶體快取，5分鐘），取代原本每次頁面 rerun 都直接
  `yf.Ticker(...).history()` 無快取重打 API 的作法。這是首頁常駐頁面，
  效益最明顯。順手移除變成沒用到的 `import yfinance as yf` 與過時的
  「Bug 1 修復」註解。
  驗證：全套 pytest + ruff lint 過；瀏覽器實測市場總覽指數卡片顯示
  正確即時數字（加權指數 45,734、費城半導體 12,426.4）。
  （`^TPEx` 卡片空白是**既有行為**，`if not data.empty` 沒有 else
  fallback，跟這次加的快取包裝無關，不在本次範圍內修。）
- [x] **第二批評估（2026-07-08）**：
  - `tabs/us_stocks.py`「大盤指數快照」（S&P500/那斯達克/道瓊，無快取）
    改用 `qw.query_yfinance_index()`；「個股歷史K線」已有「先試
    query_wrapper 快取再 fallback」的合理設計，不動。
  - `tabs/stock_page.py` 個股報價卡（單一股票 `.history(period="5d")`
    無快取）同樣改用 `qw.query_yfinance_index()`，移除變成沒用到的
    `import yfinance as yf`。
  - `adr_query.py`：`get_adr_snapshots()`/`get_usd_twd_rate()` 本身已有
    60秒/5分鐘 SQLite 快取包住整個函式，不是繞過問題，不用動。
  - **意外抓到一個影響面很廣的真炸點**：瀏覽器實測「大盤指數快照」時
    整頁崩潰——`AttributeError: 'Styler' object has no attribute
    'applymap'`。根因是 pandas 3.0（`requirements.txt` 鎖定
    `pandas>=3.0.2,<4`）**徹底移除**了 `Styler.applymap`（2.1版就已
    deprecated，3.0正式砍掉），但 `ui/display.py`（R2.4 從
    ui_components.py 原封不動搬過來的舊 code）與 `theme.py` 都還在用
    `.applymap(...)`。**這代表任何頁面顯示含漲跌/change欄位的表格、
    走 `display_table()` 或 `theme.py` 樣式函式，都會整頁崩潰**——
    影響面遠比這次要測的美股快照大，是本輪目前為止波及最廣的一個
    潛在炸點。已改 `.applymap(` → `.map(`（pandas 官方指定替代寫法，
    行為完全一致）。`tabs/dashboard.py` 也有一處相同寫法，但該檔已在
    R1 標記為孤兒待刪，未修（修了也是死碼）。
    驗證：獨立腳本確認 `Styler.map()` 在 pandas 3.0.3 產生一致的
    HTML 樣式輸出；全套 pytest + ruff lint 過；瀏覽器實測「大盤指數
    快照」查詢從崩潰變成正確顯示「📊 查詢結果」表格。
- **剩餘檔案（us_screener.py 等約 11 個）未評估**，留待後續 session
  逐一判斷。不建議直接建 `datasources/yfinance_client.py` 統一封裝——
  各檔呼叫模式差異大，統一封裝的抽象成本可能高於效益，下次先個別
  盤點再決定要不要抽公版。

---

## P3 — 測試與資料層（1-2 天）

### 3.1 補關鍵模組測試【驗證缺口】
- [ ] `tests/test_pg_db.py`——新 PG 模組零覆蓋（upsert 邏輯、NaN 處理、連線失敗 fallback）
- [ ] `tests/test_daily_job.py`——每日管線核心零專屬測試（至少測 save_csv 空檔保護、
      disposition 去重、screener 空結果路徑）

### 3.2 依賴可重現性【驗證】
全部 `>=X,<Y` 範圍鎖，`pandas>=3.0.2,<4` 允許 3.x 全系列浮動；
NAS daily 每次 `docker run` 現裝依賴，可能拿到不同版本。
- [ ] `pip freeze > requirements.lock`，daily job 與 CI 用 lock 檔安裝
- [ ] requirements.daily.txt 改 `-r` 分層引用消除人工同步

### 3.3 data/twse/ 長期膨脹規劃【推測性估算】
逐日全量快照推估 ~59 MB/年，3-5 年逼近 GitHub 建議上限。
- [ ] 中期：twse 七大類寫入 PG（pg_db 已有基礎，現只涵蓋 3 表）
- [ ] 或改 Parquet（同結構通常小 5-10 倍）
- [ ] `data/market/`（124KB/1301 檔）維持現狀即可

---

## P4 — 掃尾（半天，可零碎做）

- [ ] 刪 `deepseek_engine.py` 墊片（先 grep 確認無人 import）
- [ ] 遷移 47 個舊測試後刪 `config.py` 的 ConfigManager 相容類
- [ ] TAB_COMPAT_MAP 刪 8 組恆等映射條目；書籤載入時就地改寫舊鍵，數月後刪整個 map
- [ ] news_client.py 殘餘 8 處 print 改 logger
- [ ] dispatch.py QUERY_DISPATCH 只覆蓋 5 種查詢型別——用實際書籤驗證
      歷史重放覆蓋率【推測，待驗證】
- [ ] （環境面，非本 repo）repo 位於 Google Drive 同步夾，`.git` 有損壞風險，
      建議搬 `C:\dev\` 用 remote 備份

---

## 執行順序建議

```
第 1 週：P0 全部（金鑰輪換最優先）→ P1 全部
第 2 週：P2.1（錯誤契約，其他重構的地基）→ P2.2 → P2.3
第 3 週：P2.4 → P2.5 → P3.1 → P3.2
之後：P3.3（資料量到 20MB 再動手即可）+ P4 零碎掃尾
```

每個 P2 項目完成後跑全套 pytest + 實跑 streamlit 入口驗證，再進下一項。
