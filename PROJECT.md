# PROJECT.md — 專案進度與說明（唯一進度來源）

> **所有 AI（Claude、Gemini、Codex、Antigravity…）與人類協作者都適用。**
> 本檔記錄「專案現在在哪裡、接下來要做什麼、誰做了什麼」。
> 操作細節（部署指令、函式對照、API 設定）在 `CLAUDE.md`，本檔不重複。

---

## 0. 協作規則（必讀，每次都要做）

1. **動手前**：先讀本檔第 2～5 節（目前狀態、進行中專案、待辦、已知問題）。
2. **做完任何改動後**（程式、設定、文件、部署、資料修補都算），**在第 7 節「工作日誌」最上方追加一筆**，格式：
   ```
   ### YYYY-MM-DD｜執行者（例：Claude Opus 5.5 / Gemini / 使用者）
   - 做了什麼：一兩句話
   - 改了哪些檔：路徑清單
   - 怎麼驗證：指令與結果（例：pytest 全綠 352 passed、瀏覽器實測 XX 頁正常）
   - 沒做完／新發現：沒有就寫「無」
   ```
3. **同步更新**第 2 節「目前狀態」、第 4 節「待辦」、第 5 節「已知問題」中受影響的條目。做完的待辦打勾並註明日期，不要直接刪掉。
4. **不准**：刪改別人的舊日誌、把 token／密碼／API key 寫進本檔、沒驗證就寫「完成」。
5. 只動了本檔以外的文件也要記；只是讀檔、回答問題、沒有改任何東西則不用記。

---

## 1. 專案是什麼

個人用的台股（含港美股）查詢與看盤工具。整合永豐金 Shioaji、證交所 TWSE、FinMind、富途 Futu、Yahoo Finance 等資料源，提供：

- **網站**（目前是 Streamlit，部署在家中 NAS，port 8502）：市場總覽、個股全景、自選股、選股、全球市場、行事曆、AI 助理、投資組合。
- **每日排程**（`daily_job.py`，NAS 20:00 主力＋GitHub Actions 20:05 備援）：抓盤後資料存 CSV、法人選股、處置股郵件通知、寫 Notion／PostgreSQL。
- **命令列選單**（`cli.py`，47 項）：已凍結，不再加新功能。

---

## 2. 目前狀態（最後更新：2026-10-16）

| 項目 | 狀態 |
|---|---|
| 正式網站 | Streamlit 版運作中（NAS `sinopac-web` 容器）。功能可用但**市場總覽載入超過 1.5 分鐘**，視覺不夠專業 |
| 每日排程 | 運作中。2026-07-09 修好三大法人資料源（原端點已失效 50 天） |
| 前端改版 | **已決定放棄 Streamlit，改走 B 方案（前後端分離）**。home server `http://100.100.245.93:8600`（僅 Tailscale）。**P0 地基、P1 市場總覽（盤後）已上線**，其餘頁面仍為骨架。下一步 P2 即時行情，見第 3 節 |
| 資料路由層 | `datasources/router.py` 已有法人／估值／融資融券三個主題函式；K 線路由未做（待決策） |
| 本機環境 | 固定使用 **Python 3.13**（`py -3.13`）。系統預設 3.14 沒裝套件，不要用 |
| Git | 工作分支 `local`，發布分支 `main`。2026-10-16 的改動（Python 3.13 啟動設定、PROJECT.md 與指標檔）**尚未 commit**（見工作日誌） |

---

## 3. 進行中的重大專案：前端改版（B 方案）

**決策紀錄**
- 2026-10-16：使用者決定放棄 Streamlit。原因：太慢、版面受限、看起來不專業。
- 架構方向：資料層保留 Python（`datasources/` + `router.py` 包成 API）；畫面改用網頁前端，K 線用 TradingView Lightweight Charts。
- 2026-10-16：使用者決定**只透過 Tailscale 存取**（不對公網開放、不做登入）、**盤中逐筆即時推播**、**直接切換**（新站完整後才取代舊站，開發期間舊站不動）、**新站部署在 home server（shoyulinux）**而非 NAS。
- **技術架構草案**：`docs/plans/FRONTEND_REWRITE_ARCH_2026-10.md`（FastAPI＋React＋Redis＋行情服務，分 P0–P6 期）。**待使用者確認後開工**。
- 2026-10-16：使用者要求**雙模式**——**盤中用專業終端機風格（設計稿 A），盤後用研究報告風格（設計稿 B）**，兩者可手動切換。建議預設：08:30–13:45 自動進盤中模式，其餘時間進盤後模式；手動切換後記住使用者選擇。

**設計稿**（只有使用者本人能開）：https://claude.ai/artifact/SnQBAF4Ez4KvGaRsPqX4TW
- A 盤中模式（深色終端機）／B 盤後模式（研究報告）／C 現代儀表板（備選）
- 皆使用 2026-10-15 收盤真實資料；A、B 右上角可互相切換

**共同設計原則**（已在設計稿落實，實作時沿用）
- 紅漲綠跌，另加 ▲▼ 與正負號，不只靠顏色
- 不用表情符號；數字用等寬字、右對齊
- 法人買賣超個股與大盤一律用「張」
- 同一頁所有數字必須是同一個資料日期，並在頁面標示
- 手機寬度可用（版面自動改成上下排列）

- 個股頁（盤中／盤後）設計稿已完成（2026-10-16），在同一張畫布第二排

**下一步**
1. ~~使用者確認雙模式方向 → 用同樣風格畫「個股」頁~~（2026-10-16 完成，待使用者回饋）
2. ~~定技術架構，寫成 `docs/plans/` 規格~~（2026-10-16 草案完成，待使用者確認）
3. ~~依架構文件 P0（地基）開工~~（2026-10-16 完成）
4. ~~P1 市場總覽（盤後）~~（2026-10-17 完成）
6. ~~P3 個股頁~~（2026-10-17 完成）
7. ~~P4 自選股與警示~~（2026-10-17 完成；Telegram 待使用者建立機器人後執行 `deploy/set-telegram.sh`；手機 ntfy 待使用者安裝 App 訂閱 `http://100.100.245.93:8601` 主題 `twstock`）
8. P5 其餘頁面：~~選股~~、~~全球市場~~、~~行事曆~~、~~投資組合~~（2026-10-17 完成）；~~AI 助理~~（2026-10-17 實測通過，模型 agnes-2.5-pro-alpha）→ P5 全部完成
9. **P6 切換**（使用者決定補四項後停用舊站、不寫 Notion、舊碼搬 legacy/）：~~P6a 處置／注意股＋通知~~（2026-10-17）→ P6b 個股基本面 → P6c 美股選股＋財報日曆 → P6d 技術掃描與多因子選股 → P6e 搬 legacy、CI、文件、開 NAS 停舊站
5. **P2 即時行情：程式已部署、金鑰已設定、休市自我檢查全部通過**。剩 2026-10-19（一）開盤實測：推播延遲 < 1 秒、指數漲跌家數是否含漲跌停（與證交所收盤統計比對）、成交量差異（見已知問題）。自我檢查指令：`cd ~/apps/twstock && docker compose -f deploy/compose.yml run --rm --no-deps -T quote python -m app.quote.selftest`；重設金鑰：`ssh -t home "bash ~/apps/twstock/deploy/set-shioaji-keys.sh"`

**新網站開發須知**（P0 起適用）
- 程式碼：`backend/`（FastAPI）、`frontend/`（React）、`deploy/`（compose、hook）
- 部署：`git push home local:main` → home server 自動建置並重啟（hook 原始檔 `deploy/post-receive.sh`，伺服器上 `deploy/.env` 不進 git）
- 本機測試：後端 venv 在 `C:\Users\shoyu\.venvs\twstock-backend`；前端在 `C:\Users\shoyu\dev\twstock-fe` 鏡像執行 npm（**不要在雲端硬碟資料夾裡建 venv 或 node_modules**，數萬個小檔會拖慢並被同步）

---

## 4. 待辦（依優先順序）

- [ ] **前端改版**：見第 3 節（P0 ✅ 2026-10-16、P1 ✅ 2026-10-17，下一步 P2）
- [ ] 新後端 `backend/app/services/overview.py` 與舊站 `datasources/twse_client.py` 各有一份 T86 欄位對照（新後端為避免載入 shioaji/FinMind 而獨立實作）。P6 舊站停用時刪舊的那份
- [x] ~~home server 開機時序~~：改用 `tailnet-proxy` 容器等 Tailscale IP 出現再轉發，不需改主機設定（2026-10-16）
- [ ] 在 Uptime Kuma 新增監控 `http://100.100.245.93:8600/api/health`（需使用者登入 Uptime Kuma 設定）
- [ ] 建議把 repo 搬離 Google 雲端硬碟（例如 `C:\dev\`）：2026-10-16 已出現 `.git` 孤立索引檔警告、venv 建置卡住，都是同步軟體干擾的徵兆
- [x] ~~K 線路由待決策~~（2026-10-17 使用者決定：日 K 歷史全用 FinMind、當日與分時用永豐推播、預設不還原可切換；富途留待 P5）
- [ ] 上櫃股與櫃買指數比較、修正櫃買指數卡（參考 TWStockMCPServer 的 TPEx 端點，見架構文件 §9.5）
- [ ] 個股頁籌碼區加「集保大戶／散戶持股比例」（集保免費資料，見 §9.5）
- [ ] **台股「AI 個股健檢」按鈕永遠報錯**：`tabs/stock_page.py` 呼叫的 `ai_engine.generate_tw_stock_report` 從未實作。2026-07 曾分派任務，但留下的 worktree（`.claude/worktrees/elastic-rosalind-06694a`）沒有任何新 commit，等於沒做
- [ ] 清掉上述殘留 worktree
- [ ] 2026-10-16 的本機改動待 commit 與推送（使用者說先不推）
- [ ] `config.py` 舊的 `ConfigManager` 相容類別移除（需改寫約 80 處測試呼叫，工程大，暫緩）
- [ ] `daily_job.py` Step 6 的 `_TWSE_DAILY_ENDPOINTS` 與 `twse_client.py` 端點定義重複，日後合併（不影響正確性）

---

## 5. 已知問題

| 問題 | 影響 | 狀態 |
|---|---|---|
| 櫃買指數 Yahoo 代號 `^TWOII` 又抓不到資料 | 市場總覽櫃買卡片空白 | 未修（2026-10-16 發現） |
| TWSE 全市場行情（STOCK_DAY_ALL）更新比指數、法人慢一天 | 舊站同一頁混用不同日期的數字 | 新站已解決（改用可指定日期的 rwd MI_INDEX，整頁同一日）；舊站不修 |
| 市場總覽首次載入超過 1.5 分鐘 | 體驗差 | 新站已解決（資料 0.19 秒內顯示）；舊站不修 |
| 台指期卡片顯示「—」 | 資料缺漏 | 未查 |
| **舊站升級 shioaji 會壞**：`datasources/shioaji_client.py` 用了 `login(fetch_contract=...)`，1.7.8 已移除此參數；舊站 `requirements.txt` 允許裝到最新版 | NAS 下次重建舊站映像時永豐金功能失效 | 未修（新站已鎖 `shioaji==1.7.8`）；舊站若要重建，先把 requirements 鎖在 `shioaji==1.7.2` |
| 永豐金模擬環境快照的總量與官方不同：2330 於 10/16 快照 33,389 張，證交所 43,046 張（價格完全一致） | 量相關數字可能偏低 | 待 10/19 開盤實測，推測快照未計收盤集合競價 |

---

## 6. 文件地圖

| 文件 | 內容 |
|---|---|
| `PROJECT.md`（本檔） | 進度、待辦、已知問題、工作日誌 |
| `CLAUDE.md` | 操作手冊：部署流程、API 設定、選單對照、歷史代理人紀錄（2026-06 以前） |
| `AGENTS.md` / `GEMINI.md` | 指標檔，指向本檔與 CLAUDE.md |
| `docs/plans/REDESIGN_PLAN_2026-07.md` | 2026-07 重構計畫 R1–R6 與執行結果 |
| `docs/plans/IMPROVEMENT_PLAN_2026-07.md` | 2026-07 修 bug 計畫 P0–P4 與執行結果 |

---

## 7. 工作日誌（新的寫在最上面）

### 2026-10-17｜Claude Opus 5.5
- 做了什麼：**P6 開始：盤點與決定，並完成 P6a 處置股／注意股**。
  1. 盤點舊站（報告見工作日誌本筆；子代理逐檔對照）：舊每日排程**已停擺**——GitHub 上 `data/` 最後更新 2026-07-08；`daily.yml` 自 9 月起因缺 `FinMind` 套件每天失敗，已被 GitHub 以 inactivity 自動停用；NAS 關機中。新站不讀任何 `data/` CSV
  2. 使用者決定：停用前補四項（處置／注意股＋通知、個股基本面、美股選股＋財報日曆、技術掃描與多因子選股）；**不再寫 Notion**；舊程式碼搬到 `legacy/`。分段 P6a–P6e，P6e 才需要開 NAS 停 `sinopac-web` 與 cron
  3. P6a：證交所 `announcement/punish`（公布日期區間）、`announcement/notice`（單日），櫃買 OpenAPI `tpex_disposal_information`、`tpex_trading_warning_information`；只留普通股；處置取「今天仍有效或即將開始」且同檔取最新公告；撮合頻率由公告內文擷取（證交所寫國字「約每十分鐘」，已轉換）。worker 每 10 分鐘寫 `attention:latest`，`/api/market/attention`
  4. 通知（取代舊 Gmail）：API 的收盤迴圈（平日 14:30 後每 15 分鐘）比對，新處置股彙整一則（自選股／持股標 ★）、自選股或持股被列注意每檔每天一則，走網頁＋ntfy＋Telegram，並記入自選股頁觸發紀錄；**第一次執行只記錄現況不通知**
  5. 前端：市場總覽新增「處置股與注意股」區塊；個股頁（盤中與盤後版）顯示「處置 期間」「注意股」標籤
- 改了哪些檔：`backend/app/services/attention.py`、`attention_notify.py`（新）、`sources/tpex.py`（新）、`sources/twse.py`、`worker.py`、`main.py`、`store.py`（`add_event`）、`services/alert_runner.py`、`tests/test_attention.py`、fixtures 4 個；`frontend/src/lib/attention.ts`、`components/AttentionPanel.*`（新）、`pages/Overview.tsx`、`pages/StockPage.*`
- 怎麼驗證：後端 pytest 76 passed、ruff 通過；前端 40 passed、build 通過；線上 `/api/market/attention` 處置 17 檔、注意 32 檔（asof 10/16）；抽查隴華「約每十分鐘」、巨虹「約每25分鐘」與公告原文一致；瀏覽器看到總覽區塊與 4979 華星光的兩個標籤
- 沒做完／新發現：通知要到平日 14:30 後才第一次執行（初始化）；git 又出現 Drive 造成的 `packed-refs.lock` 殘留（確認無 git 程序後刪除）

### 2026-10-17｜Claude Opus 5.5
- 做了什麼：**P5e AI 助理實測通過**。使用者以 `deploy/set-agnes.sh` 自行設定金鑰，選用模型 `agnes-2.5-pro-alpha`。
- 改了哪些檔：無（伺服器 `deploy/.env` 由使用者設定，不進 git）
- 怎麼驗證：
  1. 問 2330 收盤、外資 5 日、本益比位置 → 呼叫 site_stock、get_realtime_quote；收盤 2,420、5 日外資 −97,973 張、連賣 8 天、10 月累計約 −10.6 萬張、本益比 28.05 倍／79.1 百分位，與 `/api/stock/2330` 逐項核對一致
  2. 在 `/ai` 頁問「自選股兩週內除權息／法說會＋景氣燈號」→ 查 7 項資料；鴻海 10/20、台達電 10/29、聯發科 10/30 法說會與 `/api/calendar` 一致，星期正確；景氣燈號來自 TWStockMCPServer（國發會）
- 沒做完／新發現：區間型法說會（鴻海 10/15～10/20）被 AI 說成「已過」，屬小瑕疵，之後可在行事曆資料加 end_date 欄位讓模型判斷

### 2026-10-17｜Claude Opus 5.5
- 做了什麼：**P5e AI 助理程式完成並部署，待使用者設定 Agnes 金鑰**（`/ai`）。
  1. 供應商 Agnes（OpenAI 相容，預設 `https://apihub.agnes-ai.com/v1`）；金鑰與模型由使用者執行 `ssh -t home "bash ~/apps/twstock/deploy/set-agnes.sh"` 自行輸入（畫面不顯示，腳本會列出帳號可用模型讓使用者選），存在伺服器 `deploy/.env` 的 `AGNES_API_KEY`／`AGNES_MODEL`
  2. 資料工具：compose 新增 `twse-mcp`（自架 TWStockMCPServer，MIT，鎖映像 digest，只在內網）；後端自寫最小 MCP 客戶端（Streamable HTTP）。176 個工具只開放 32 個精選（個股基本面、價格技術、籌碼、上櫃、大盤總經、事件、ETF），另加 5 個本站工具（市場總覽、個股、自選股、投資組合、行事曆）
  3. 對話：工具呼叫迴圈最多 6 輪；MCP 連不上時只用本站工具並告知；瀏覽器送來的 system 訊息會被丟棄；系統提示要求數字只能來自工具、註明日期來源、不給買賣指令
  4. `/api/ai/chat` 以 SSE 串流「查了哪些資料」與答案；nginx 對 `/api/ai/` 關閉緩衝；前端 AI 頁延遲載入（Markdown 套件不進主程式包）
- 改了哪些檔：`backend/app/ai/`（新：`mcp_client.py`、`tools.py`、`agent.py`）、`api_ai.py`（新）、`main.py`、`tests/test_ai.py`、`deploy/compose.yml`、`deploy/.env.example`、`deploy/set-agnes.sh`（新）、`frontend/nginx.conf`、`package.json`（react-markdown、remark-gfm）、`src/lib/aiChat.*`、`src/pages/AiPage.*`、`App.tsx`
- 怎麼驗證：後端 pytest 73 passed（假 MCP＋假模型跑完整工具迴圈、白名單、MCP 斷線降級、未設定回 503）、ruff 通過；前端 vitest 40 passed、build 通過；部署後在 api 容器內實連 twse-mcp：tools/list 176 個、白名單 32 個全部存在、`get_company_profile 2330` 回正確資料；`/api/ai/status` 回 configured=false，`/ai` 頁顯示設定指令
- 沒做完／新發現：**尚未用真實 Agnes 模型對話**（等使用者設定金鑰後實測：工具呼叫是否正常、回答數字是否與網站一致）；主程式包 544 kB（K 線圖套件），之後可再拆

### 2026-10-17｜Claude Opus 5.5
- 做了什麼：**P5d 投資組合完成並上線**（`/portfolio`，選單在「全球市場」後）。
  1. 手動輸入持股（使用者決定，不接券商帳務）：每筆一次買進（代號、股數、每股成本、選填日期與備註），可編輯、刪除；存 SQLite `holdings` 表（volume 保留）
  2. 同代號多筆合併為一個部位（加權平均成本）；價格盤中用永豐即時成交、否則用最近收盤；顯示市值、未實現損益、報酬率、今日損益、占比
  3. 「扣除賣出費稅後」：手續費 0.1425%（未計折扣）＋證交稅（股票 0.3%、ETF 0.1%、債券 ETF 停徵至 2026 年底）
  4. 前端 `json()` 改為能顯示 FastAPI 422 欄位驗證錯誤（原本會顯示 [object Object]）
- 改了哪些檔：`backend/app/api_portfolio.py`（新）、`store.py`、`main.py`、`tests/test_portfolio.py`、`frontend/src/lib/portfolio.ts`（新）、`portfolio.test.ts`、`lib/api.ts`、`pages/PortfolioPage.*`、`App.tsx`、`components/AppShell.tsx`
- 怎麼驗證：後端 pytest 70 passed、ruff 通過；前端 vitest 37 passed、typecheck、build 通過；部署後用瀏覽器實際填表新增 2330 1,000 股成本 1,100 → 市值 2,420,000、損益 +1,320,000、費稅 3,449＋7,260 與手算一致；編輯為 2,000 股正確更新；測試紀錄已刪除，`/api/portfolio` 回空
- 沒做完／新發現：未計股利與已實現損益（賣出紀錄）；盤中即時價待 10/19 開盤實測

### 2026-10-17｜Claude Opus 5.5
- 做了什麼：**P5c 投資行事曆完成並上線**（`/calendar`）。
  1. 資料源：證交所除權除息預告表 `exRight/TWT48U`（上市股票與 ETF）；公開資訊觀測站法人說明會（舊站 `mopsov…/ajax_t100sb02_1`，上市＋上櫃，當月與次月；做法參考 TWStockMCPServer，MIT 授權）；法定公布期限（月營收每月 10 日、Q1 5/15、Q2 8/14、Q3 11/14、年報 3/31）
  2. worker 每 6 小時更新一次 Redis `calendar:latest`（MOPS 有防爬限制，每次呼叫間隔 2 秒），`/api/calendar` 只讀快取；範圍為今天前 7 天到後 60 天
  3. 前端：依日期分組、類型篩選、只看自選股（公布期限仍保留）、自選股以左側色線標示、可顯示過去 7 天
  4. 修正：`.gitignore` 的 `*.json` 讓**所有後端測試 fixture 從未進版控**（CI 會缺檔），加例外 `!backend/tests/fixtures/*.json` 並補提交（已確認內容皆為公開行情資料，無金鑰）
- 改了哪些檔：`backend/app/sources/mops.py`（新）、`services/calendar.py`（新）、`sources/twse.py`、`worker.py`、`main.py`、`tests/test_calendar.py`、`tests/fixtures/*`、`frontend/src/lib/calendar.ts`、`calendar.test.ts`、`pages/CalendarPage.*`、`App.tsx`、`.gitignore`
- 怎麼驗證：後端 pytest 69 passed、ruff 通過；前端 vitest 34 passed、typecheck、build 通過；部署後 `/api/calendar` 回 200，162 筆（法說會 103、除權息 55、期限 4），worker log「行事曆已更新：162 筆」；瀏覽器開 `/calendar` 顯示正常
- 沒做完／新發現：上櫃除權息（櫃買中心）尚未納入；法說會日期為區間時排在起日；除權息清單 ETF 佔多數（官方資料如此）

### 2026-10-17｜Claude Opus 5.5
- 做了什麼：**P5b 全球市場頁完成並上線**（`/global`）。主要指數、原物料與匯率、台灣 ADR 溢價、港美股日 K 查詢；依使用者決定只用 Yahoo，不接富途。ADR 換算比例以實價驗算：日月光投控 ASX 為 1:2（舊站 `adr_query.py` 一律 1:5，會算出假的 −60% 折價），台積電、聯電 1:5。worker 每 10 分鐘預先計算，港美股 K 線走 `/api/global/kbar`（快取 30 分鐘）
- 改了哪些檔：`backend/app/api_global.py`、`services/global_mkt.py`、`sources/yahoo.py`、`worker.py`、`main.py`、`tests/test_global.py`、`frontend/src/pages/GlobalPage.*`、`components/Sparkline.tsx`、`App.tsx`（commit `53616e8`）
- 怎麼驗證：後端 64 passed、前端 30 passed；ADR 溢價以 2026-10-15/16 實價驗算寫成測試
- 沒做完／新發現：本筆日誌於 P5c 時補記

### 2026-10-17｜Claude Opus 5.5
- 做了什麼：**P5a 選股頁完成並上線**（`/screener`）。上市普通股官方單日資料（MI_INDEX、T86、BWIBBU_d）＋最近 10 個交易日法人連續天數＋FinMind 產業；worker 同步產出選股總表；過去日期 T86 快取 30 天；五個常用策略＋11 個數值條件＋產業可疊加、欄位排序、一鍵加入自選
- 改了哪些檔：`backend/app/services/screener.py`、`sources/twse.py`、`worker.py`、`main.py`、`tests/test_screener.py`、`frontend/src/lib/screener.*`、`pages/ScreenerPage.*`、`App.tsx`（commit `ace6c24`）
- 怎麼驗證：後端 62 passed、前端 30 passed
- 沒做完／新發現：上櫃股票未納入；本筆日誌於 P5c 時補記

### 2026-10-17｜Claude Opus 5.5
- 做了什麼：**P4 自選股與警示完成並上線**（`/watchlist`）。
  1. 使用者選定通知方式：網頁內提示＋ntfy＋Telegram
  2. 自選股存 SQLite（預設 5 檔，加入／移除／排序）；報價牆盤中即時、盤後顯示收盤
  3. 警示重寫（舊 `alert_engine.py` 的 pct_move 誤用漲跌金額、ma20_break 未實作）：盤中 price_above／price_below／pct_move 由永豐推播即時判斷；收盤 ma20_break／ma20_reclaim／外資連續買賣超 N 天；同一規則每天最多通知一次
  4. 自選股與盤中警示代號寫入 Redis `quote:pinned`，行情服務改為依此常駐訂閱
  5. 通知：網頁內提示（任何頁面右下角）、自架 ntfy 容器（`binwiederhier/ntfy:v2.17.0`，只綁 Tailscale 8601；upstream 設 ntfy.sh 供 iPhone 即時推播，只轉送訊息 ID）、Telegram（`deploy/set-telegram.sh` 讓使用者自行輸入 token、自動找聊天 ID）；httpx log 降為 WARNING 避免 token 進 log
  6. 修正：自選股報價牆最後兩根 K 棒順序對調（顯示成前一天）；`ALERTS`／`SCANNER` 偽代號不再登記給行情服務；收到警示時立即更新觸發紀錄
- 改了哪些檔：`backend/app/store.py`、`services/alerts.py`、`notify.py`、`alert_runner.py`、`api_watchlist.py`、`main.py`、`ws.py`、`quote/service.py`、`tests/test_alerts.py`、`test_ws.py`、`conftest.py`、`frontend/src/pages/WatchlistPage.*`、`components/AlertToast.*`、`lib/watchlistOps.ts`、`lib/api.ts`、`deploy/compose.yml`（ntfy、轉發 8601）、`deploy/set-telegram.sh`、`deploy/.env.example`
- 怎麼驗證：後端 pytest 59 passed、前端 vitest 26 passed；**端到端實測**（週六無真實推播，改向行情頻道送標為今日的模擬報價）：用頁面表單建立規則 → 觸發並寫入紀錄 → ntfy 收到推播（點擊連到個股頁）→ 網頁右下角跳出提示 → 第二筆報價不重複通知；自選股報價與市場總覽數字一致；測完已刪除測試規則與紀錄（ntfy 快取的 2 則測試通知 72 小時後自動清除）
- 沒做完／新發現：Telegram 未設定（需使用者先建立機器人）；手機尚未安裝 ntfy；真實盤中觸發待 10/19 開盤驗證；收盤規則依賴 FinMind 當晚更新時間

### 2026-10-17｜Claude Opus 5.5
- 做了什麼：**P3 個股頁完成並上線**（`/stock/{代號}`，盤中終端機版與盤後報告版）。
  1. 依提醒先請使用者決定 K 線來源：日 K 歷史全用 FinMind（1994 起），當日 K 棒與五檔用永豐推播；預設不還原、可切換還原權值
  2. 後端：FinMind 抓取層、SQLite 快取（Docker volume `/data`，日 K 增量更新；未動 home server 共用的 PostgreSQL）、法人／融資券／月營收（直接用 FinMind 的 `revenue_year/revenue_month`）／本益比五年位置／還原權值／摘要句、`/api/stock/{code}`、`/kbar`、`/api/search`
  3. 前端：TradingView Lightweight Charts v5 日 K＋MA5/20/60＋成交量（盤中只更新最後一根）、五檔、外資 15 日、融資券、營收、本益比位置、搜尋
  4. 評估使用者提供的 TWStockMCPServer：MIT 授權；AI 助理（P5）直接接、網站資料層只參考其官方端點（寫入架構文件 §9.5）
  5. 修正：搜尋結果排除權證並讓一般股票優先；上櫃股不再拿加權指數比較；切換深淺模式時 K 線圖顏色錯誤（子元件 effect 先於父元件執行，改為渲染時即套用模式）
- 改了哪些檔：`backend/app/sources/finmind.py`、`backend/app/store.py`、`backend/app/services/stock.py`、`stock_loader.py`、`backend/app/api_stock.py`、`main.py`、`settings.py`、`backend/Dockerfile`、`deploy/compose.yml`（volume、FINMIND_TOKEN）、`frontend/src/pages/StockPage.*`、`components/KChart.tsx`、`lib/indicators.ts`、`lib/api.ts`、`lib/useMarketMode.ts`、`backend/tests/test_stock.py` 與 fixtures、架構文件、記憶檔
- 怎麼驗證：後端 pytest 47 passed、前端 vitest 23 passed、ruff 與建置通過。**跨來源核對**：FinMind 算出的外資買賣超 10/16 −22,046、10/15 −34,111 張與證交所 T86 完全一致；10/16 收盤 2,420、成交 43,046,982 股與證交所一致；10 月外資累計 −10.6 萬張與另一套資料推算一致；還原權值逐日驗算（9/15 還原後 = 官方參考價 2,377.99）。速度：首次載入台積電（含 30 年歷史）1.05 秒、快取後 0.02 秒、上櫃 0.24 秒、ETF 0.55 秒。瀏覽器實測盤後／盤中、還原切換、手機 375 寬無溢出
- 沒做完／新發現：上櫃股的大盤比較待接櫃買指數；FINMIND_TOKEN 未設定（目前用免登入額度，有快取所以夠用）

### 2026-10-17｜Claude Opus 5.5
- 做了什麼：P2 金鑰設定與休市實測。
  1. 使用者要求代寫金鑰；依規則不代填金鑰，改寫 `deploy/set-shioaji-keys.sh`（使用者自行貼上、畫面不顯示、自動 `chmod 600` 並重啟 quote），由我在使用者終端機開好 SSH 分頁讓使用者輸入。設定完成，`.env` 權限 600
  2. 新增 `app/quote/selftest.py`（登入→合約→訂閱→用量→登出，快照與排行各一次）
  3. 實測抓到 **shioaji 1.7.8 的 `login()` 已無 `fetch_contract` 參數**，改為 `subscribe_trade=False` 並鎖定 `shioaji==1.7.8`；同時發現舊站有同樣問題（列入已知問題）
  4. **事故**：SDK 預設會印出連線事件原文，其中含使用者的身分證字號，第一次自我檢查時出現在 Claude 的工具輸出（對話紀錄）中。已改為自訂事件回呼只記錄代碼、自我檢查只保留訂閱頻道資訊；之後以伺服器端遮蔽＋計數驗證未遮蔽輸出中身分證格式字串為 0 行
  5. 排行回傳的名稱尾端有補空白，已去除
- 改了哪些檔：`backend/app/quote/service.py`、`normalize.py`、`selftest.py`（新增）、`backend/requirements-quote.txt`、`deploy/set-shioaji-keys.sh`（新增）
- 怎麼驗證：home server 上自我檢查全部通過（登入 0.5 秒、連線數 1、流量 0.1/500 MB、IX0001 與 2330 訂閱皆回 200）；**模擬環境資料為真實行情**——2330 快照收 2,420、跌 20 與證交所 10/16 一致，成交金額排行前三（台積電、南亞、聯發科）收盤價皆一致；後端 pytest 34 passed
- 沒做完／新發現：快照總量與官方差 22%（列入已知問題）；即時推播延遲與漲跌家數定義待 10/19 開盤驗證

### 2026-10-17｜Claude Opus 5.5
- 做了什麼：**P2 即時行情：程式完成並部署，待金鑰與開盤實測**。
  1. 查證（永豐金官方文件）：模擬環境支援 `quote.subscribe`；同一身分證最多 5 條連線（不會互踢）；訂閱推播不計流量；**盤中禁止輪詢 snapshots／ticks／kbars，違規會暫停 IP 與帳號**——因此刪除架構中兩處快照輪詢設計
  2. 確認本機 `~/.app_config/config.json` 沒有永豐金金鑰（舊站的永豐金功能在本機其實不能用）；NAS 休眠未查
  3. 行情服務 `backend/app/quote/`：唯一的 Shioaji 連線、只在 08:25–13:50 登入、`QuoteType.Quote`（成交＋五檔）、指數 `IX0001`（含漲跌家數與累計成交金額）、排行每分鐘一次、訂閱上限 190、登入失敗退避；推播 `pct_chg` 單位為萬分之一，改由 `price_chg` 自算
  4. `/ws` WebSocket 轉送；健康檢查新增 quote；前端盤中模式顯示即時指數、寬度、成交金額與排行（只採用今天的推播）
  5. 使用者要提供金鑰檔（`P:\API文件\永豐金API.txt`）時，**沒有開啟該檔**，改請使用者自行寫入 home server 的 `.env`，金鑰不經過對話紀錄
- 改了哪些檔：`backend/app/quote/`、`backend/app/ws.py`、`backend/app/main.py`、`backend/Dockerfile.quote`（新增）、`backend/requirements-quote.txt`（新增）、`backend/tests/test_quote.py`、`test_ws.py`、`frontend/src/lib/useLiveQuotes.ts`、`frontend/src/components/LivePanel.*`、`deploy/compose.yml`、`deploy/.env.example`、架構文件 §5、§9
- 怎麼驗證：後端 pytest 34 passed（假 SDK＋fakeredis，含 WebSocket 端到端）、前端 vitest 19 passed、建置成功、ruff 通過；部署後 quote 容器內 shioaji 1.7.8 可載入，健康檢查回 `quote: no_credentials`（無金鑰時正確待命）
- 沒做完／新發現：
  1. **未經真實行情驗證**（週六休市、無金鑰）。開盤後要驗：推播是否真實、延遲 < 1 秒、`raise_count` 是否含漲停
  2. 本機 `.git/packed-refs.lock` 殘留（雲端硬碟干擾，3 小時前留下），確認無 git 程序後已刪除
  3. 國定假日仍未處理（休市日會白白登入一次，無害）

### 2026-10-17｜Claude Opus 5.5
- 做了什麼：**P1 市場總覽（盤後）完成並上線**。發現證交所 rwd `MI_INDEX?type=ALLBUT0999` 可**指定日期**一次取得官方加權指數、成交金額、漲跌家數與全部個股收盤行情，搭配同日 T86、月份 FMTQIK，整頁保證同一資料日期（取「MI_INDEX 與 T86 都已公布」的最近交易日）。worker 每 10 分鐘預先計算寫入 Redis，API 只讀 Redis；標題與導言由資料以規則產生；國際市場（Yahoo）美股取台股該日開盤前最後一個收盤日並標示日期。健康檢查新增 worker 狀態（失敗或逾 30 分鐘未更新回 503）。前端依設計稿 B 實作，盤中模式暫顯示收盤資料並標註 P2 才有即時。
- 改了哪些檔：`backend/app/sources/`、`backend/app/services/overview.py`、`backend/app/worker.py`、`backend/app/main.py`、`backend/tests/`（含 2026-10-16 真實官方回應 fixtures）、`frontend/src/`（Overview 頁、IndexChart、format、chartScale、api）、`deploy/compose.yml`（新增 worker）
- 怎麼驗證：後端 pytest 25 passed、ruff 通過；前端 typecheck、vitest 16 passed、建置成功；部署後 worker 實際產出 asof=2026-10-16；API 回應 17～32 ms，瀏覽器量測資料在頁面開啟後 0.19 秒顯示（目標 < 2 秒）；數字交叉核對：加權指數 47,111.26（+141.39）與 Yahoo ^TWII 一致、成交金額 9,938 億與 FMTQIK 一致、台積電 10/16 收 2,420（−0.82%）與 FinMind 10/15 收盤 2,440 推算一致；瀏覽器實測 1100／1280 寬、手機 375 寬無溢出、盤中（深色）模式正常；修掉兩個版面問題（漲平跌字太小、窄螢幕換行）
- 沒做完／新發現：
  1. 預覽瀏覽器在窗格偏窄時截圖會裁掉右側，改以 DOM 量測驗證寬版版面（無溢出）
  2. 國定假日判斷仍未做（P2）
  3. T86 欄位對照在新舊兩處各一份（列入待辦）

### 2026-10-16｜Claude Opus 5.5
- 做了什麼：解決 home server 開機時序風險。原本 web 容器直接綁 Tailscale IP，Docker 若比 tailscaled 先啟動就綁不到、網站起不來。改成 web 只綁 127.0.0.1:8600，另加 `tailnet-proxy`（socat，host 網路）輪詢等待 `BIND_IP` 出現在網卡上才監聽並轉發。沒有採用 P0 日誌提議的 `sysctl net.ipv4.ip_nonlocal_bind`，因為那是主機系統設定。
- 改了哪些檔：`deploy/compose.yml`
- 怎麼驗證：以不存在的 IP 單獨啟動轉發容器，確認持續等待、不崩潰；部署後 `/api/health` 經 Tailscale 回 200（版本 `55b6a83`）；伺服器上 8600 只監聽 100.100.245.93 與 127.0.0.1，區網 IP 連線被拒
- 沒做完／新發現：真正重開機的情境未實測（會中斷目前經 Tailscale 的連線），下次 home server 重開機後確認網站自動恢復即可

### 2026-10-16｜Claude Opus 5.5
- 做了什麼：**P0 地基完成並部署到 home server**。後端 FastAPI（`/api/health`，Redis 異常回 503）、前端 React 19＋Vite 8＋TypeScript 7＋React Router 8（盤中／盤後依台北時間自動切換、手動切換存到下一個切換點、首次繪製前套用模式避免閃爍）、設計 token、頁面骨架；compose（web／api／redis）只綁 Tailscale IP；home server 建 `~/git/twstock.git` 與部署 hook、`~/apps/twstock/deploy/.env`；CI 新增 backend、frontend 兩個 job。
- 改了哪些檔：`backend/`、`frontend/`、`deploy/`（皆新增）、`.github/workflows/ci.yml`、`.gitignore`（放行前端 json）、`.gitattributes`（新增）；本機新增 git remote `home`
- 怎麼驗證：後端 pytest 2 passed；前端 typecheck 通過、vitest 9 passed、正式建置成功；ruff 通過；部署後經 Tailscale `curl /api/health` 回 200 且版本為 `fd386f4`；深層連結 `/stock/2330` 回 200；伺服器上 8600 只監聽 100.100.245.93，用區網 IP 192.168.0.247 連線被拒；瀏覽器實測盤後（白）／盤中（深色）切換、重新整理後保持、手機 375 寬無橫向捲動
- 沒做完／新發現：
  1. 開機時序：Docker 未排在 tailscaled 之後。建議使用者執行（允許綁定尚未出現的 IP）：`echo 'net.ipv4.ip_nonlocal_bind=1' | sudo tee /etc/sysctl.d/99-twstock.conf && sudo sysctl --system`
  2. Uptime Kuma 監控項待使用者新增
  3. 新增的 CI job 要等推到 GitHub 才會跑（本次未推 GitHub／NAS）
  4. 雲端硬碟干擾 git：`git count-objects` 出現「no corresponding .pack」孤立索引檔警告
  5. 國定假日尚未納入盤中判斷（P2 接證交所休市日）

### 2026-10-16｜Claude Opus 5.5
- 做了什麼：新網站技術架構草案。實測 NAS（J4125、8GB）與 home server（i7-7700、14GB、已有 pg17／Uptime Kuma／Dozzle、Tailscale 100.100.245.93、8600 埠空著）；確認 `datasources/`、`router.py` 不依賴 Streamlit，`query_wrapper.py`、`caching.py`、`screener.py` 依賴 Streamlit 快取不能直接沿用。依使用者四項決定（Tailscale、逐筆推播、直接切換、部署 home server）寫成架構文件。
- 改了哪些檔：`docs/plans/FRONTEND_REWRITE_ARCH_2026-10.md`（新增）、`PROJECT.md`
- 怎麼驗證：主機規格、埠、Shioaji 設定皆以指令實測；文件中未查證項目已列在 §9 風險表
- 沒做完／新發現：模擬環境能否訂閱逐筆行情、多處登入是否互踢，**未查證**，是逐筆推播能否實現的關鍵（P2 第一件事）

### 2026-10-16｜Claude Opus 5.5
- 做了什麼：個股頁設計稿（台積電 2330，2026-10-15 真實資料），分盤中模式（K 線＋均線＋成交量、五檔、外資 15 日、融資券、月營收、本益比五年位置）與盤後報告模式（摘要標題、走勢、法人與融資表、營收、估值），兩者可互相切換。
- 改了哪些檔：無（設計稿在線上 Artifact）
- 怎麼驗證：K 線、成交量數列以程式比對 FinMind 原始資料，三組完全一致；摘要中的每個敘述（連 7 日賣超、10 月累計約 −8.4 萬張、融資連增 5 日等）逐一對照資料計算
- 沒做完／新發現：FinMind 月營收的「日期」欄是公告月份，不是營收月份（2026-10-01 那筆是 9 月營收），新前端顯示時要往前推一個月

### 2026-10-16｜Claude Opus 5.5
- 做了什麼：建立本檔（PROJECT.md），並在 CLAUDE.md、AGENTS.md、GEMINI.md 開頭加上「先讀本檔、做完要記錄」的規定。設計稿加上盤中／盤後模式切換。
- 改了哪些檔：`PROJECT.md`（新增）、`CLAUDE.md`、`AGENTS.md`、`GEMINI.md`；設計稿（線上 Artifact，不在 repo）
- 怎麼驗證：文件，無程式改動
- 沒做完／新發現：無

### 2026-10-16｜Claude Opus 5.5
- 做了什麼：前端改版設計稿。實測現有網站問題（載入 >1.5 分鐘、空白卡片、漲跌配色矛盾、裝飾過多）；使用者選 B 方案（放棄 Streamlit）；以 10/15 真實資料做出 A／B／C 三種市場總覽設計稿。
- 改了哪些檔：無（設計稿在線上 Artifact）
- 怎麼驗證：資料由 `datasources/` 實際抓取，數字前後一致（統一用 10/15）
- 沒做完／新發現：`^TWOII` 失效、STOCK_DAY_ALL 晚一天（已列入第 5 節）

### 2026-10-16｜Claude Opus 5.5
- 做了什麼：系統預設 Python 變成 3.14 且沒裝任何套件，導致網站與選單都打不開。依使用者決定固定用 3.13；補上漏列的 `futu-api`；確認富途 FutuOpenD 可連線、能抓港股 K 線。
- 改了哪些檔：`run_app.bat`（改 `py -3.13`，並修正 `> /dev/null` 為 `>nul`）、`查詢工具.bat`（改 `py -3.13`）、`.claude/launch.json`、`requirements.txt`
- 怎麼驗證：3.13 下 CLI 可 import；網站實際啟動，市場總覽顯示加權指數；`pip install --dry-run -r requirements.txt` 可解析
- 沒做完／新發現：**未 commit、未推送**（使用者指示先不推）

### 2026-07-09｜Claude
- 做了什麼：R4 資料路由層第一階段。修好 `daily_job.py` 三大法人（原 openapi 端點失效，選股自 2026-05-18 起從未用真資料跑過），並抓到億股換算錯誤（/10000 → /1e8）；建立 `datasources/router.py` 的 `get_institutional()`、`get_valuation()`、`get_margin()`，三者皆以 TWSE 與 FinMind 兩個獨立來源交叉驗證，數字完全一致。
- 改了哪些檔：`daily_job.py`、`pg_db.py`、`datasources/twse_client.py`、`datasources/router.py`（新增）、`tests/test_router.py`（新增）、`docs/plans/*`
- 怎麼驗證：pytest 全綠、ruff 全綠、GitHub CI 綠燈、已推 GitHub 與 NAS
- 沒做完／新發現：`get_kbar()` 待使用者決策（見第 4 節）

### 2026-07-08｜Claude
- 做了什麼：全案重構計畫（`REDESIGN_PLAN_2026-07.md`）。完成 R1 刪孤兒檔 `tabs/dashboard.py` 與死 import；R2 行事曆引擎合併（`calendar_engine.py`）；R3 股票池統一（`stock_pools.py`，台灣50 依實際成分股校正）；R6 刪 `deepseek_engine.py` 墊片。修好多個「一直靜默失敗」的 bug：pandas 3.0 移除 `Styler.applymap` 導致全站表格崩潰、櫃買指數代號錯誤、今日除息區塊 AttributeError。
- 改了哪些檔：見 git log `204d343` 之前約 10 筆 commit
- 怎麼驗證：每批 pytest＋ruff＋瀏覽器實測＋CI 綠燈
- 沒做完／新發現：台股 AI 健檢按鈕缺函式（見第 4 節）

### 2026-07-07｜Claude
- 做了什麼：修好每日排程斷線 50 天、CI lint 卡關、TWSE 20 個函式匯出遺漏等；建立 `IMPROVEMENT_PLAN_2026-07.md`。
- 改了哪些檔：見 git log
- 怎麼驗證：CI 綠燈、NAS 部署確認
- 沒做完／新發現：見該計畫文件

> 2026-06 以前的紀錄見 `CLAUDE.md`「代理人互動紀錄」章節。
