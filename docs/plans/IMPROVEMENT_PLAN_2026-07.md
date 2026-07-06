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
- ✅ **附帶抓到並修復 2 個生產環境真炸點**：
  1. `tabs/calendar_tab.py`：`投資行事曆→台股法說/除息` 分頁對不存在的
     「日期」欄位做比較，**每個使用者點進去必炸**（KeyError）。已修為用
     「財報公佈日」/「除息日」計算排序欄位。
  2. 【待修，已記錄】`tabs/market_overview.py:616` 與
     `tabs/us_calendar_tab.py:96` 在全套測試下才會炸——推測是另一種
     全域狀態污染（session_state 或快取單例跨測試殘留），在單檔隔離執行時
     100% 正常，混進全套隨機炸不同分頁。診斷需要更多時間，**未修**，
     下次處理。

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

### 2.2 daily_job 改用 datasources/twse_client【驗證】
TWSE 端點表雙寫：twse_client.py 與 daily_job.py:404 各一份，
daily_job.py:147 還在呼叫**已知廢棄**的 openapi T86 端點。
「修一邊忘另一邊」已實際發生過（T86 事件）。
- [ ] daily_job import twse_client，端點定義單一來源
- [ ] 改完在本機實跑 `python daily_job.py` 驗證，再上 NAS

### 2.3 快取收斂【驗證】
四種快取路徑並存：sqlite_cache 手寫呼叫、`@cached_query` 裝飾器、
裸 `@st.cache_data`（query_wrapper.py:219）、`_read_twse_local()` CSV 讀取。
- [ ] 全數收斂到 `@cached_query`
- [ ] CSV fallback 移入 twse_client 作為 fetch 層邏輯
- [ ] 在 daily_job 尾端或 app 啟動時呼叫 `sqlite_cache.clear_expired()`
      （函式存在但全案無人呼叫，cache.db 現 648KB 不急但會緩慢累積）

### 2.4 ui_components.py 拆檔（機械搬移，低風險）【驗證】
1,156 行三種職責：通用顯示 / 側邊欄設定 / 美股+Shioaji 專屬渲染。
- [ ] 拆 `ui/display.py`、`ui/sidebar.py`、`ui/us.py`、`ui/shioaji.py`
- [ ] ui_components.py 留 re-export 墊片維持相容

### 2.5 yfinance 統一封裝【驗證】
15 個檔案各自 import yfinance，其中 5 個 tabs 直呼 = 繞過快取層重複請求。
- [ ] 建 `datasources/yfinance_client.py`（含快取），tabs 一律走 query_wrapper

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
