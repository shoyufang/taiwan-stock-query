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

個人用的台股（含港美股與全球市場）查詢與看盤工具。整合永豐金 Shioaji、證交所 TWSE、櫃買 TPEx、公開資訊觀測站 MOPS、FinMind、Yahoo Finance 與自架 TWStockMCPServer，提供：

- **新網站**（FastAPI＋React 前後端分離，部署在 home server `http://100.100.245.93:8600`，僅 Tailscale）：市場總覽（含處置／注意股）、個股頁（含 K 線、籌碼、基本面與 PE 河流圖）、自選股與警示、選股與技術掃描（含多因子漏斗）、全球市場（含美股選股與財報日曆）、投資行事曆、投資組合、AI 助理。
- **背景排程與即時推播**：`worker` 容器定時預先計算全站盤後資料寫入 Redis；`api` 收盤迴圈執行處置／注意股與警示推播（網頁＋自架 ntfy＋Telegram）；`quote` 容器於交易時段透過永豐金 Shioaji WebSocket 逐筆推播。
- **舊版封存（`legacy/`）**：舊 Streamlit 網站（NAS `sinopac-web`）、`daily_job.py` 與命令列選單（`cli.py`）已退役並歸檔至 `legacy/`。

---

## 2. 目前狀態（最後更新：2026-10-17）

| 項目 | 狀態 |
|---|---|
| 正式網站 | **新站已全面上線**：home server `http://100.100.245.93:8600`（僅 Tailscale）。舊 NAS Streamlit 網站已退役（2026-10-17 確認 `sinopac-web` 容器已不存在、NAS 舊 cron 已註解停用） |
| 每日排程 | 新站 `worker` 與 `api` 收盤迴圈全面接手；舊 `daily.yml` 與 `daily_job.py` 已移入 `legacy/` |
| 前端改版 | **P0～P6（含 P6a～P6e）全數完成並上線**；剩 P2 待 2026-10-19（一）開盤實測即時推播延遲與漲跌家數 |
| 資料層 | `backend/app/sources/`（TWSE、TPEx、MOPS、FinMind、Yahoo）與 `backend/app/services/` 純函式；舊 `datasources/` 已歸檔至 `legacy/datasources/` |
| 本機環境 | 固定使用 **Python 3.13**（`py -3.13`）。系統預設 3.14 沒裝套件，不要用 |
| Git | 工作分支 `local`，發布分支 `main` |

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
9. **P6 切換**（使用者決定補四項後停用舊站、不寫 Notion、舊碼搬 legacy/）：~~P6a 處置／注意股＋通知~~（2026-10-17）→ ~~P6b 個股基本面~~（2026-10-17）→ ~~P6c 美股選股＋財報日曆~~（2026-10-17）→ ~~P6d 技術掃描與多因子選股~~（2026-10-17）→ ~~P6e 搬 legacy、CI、文件~~（2026-10-17 完成；NAS 端已確認無舊容器、舊 cron 已註解停用）
5. **P2 即時行情：程式已部署、金鑰已設定、休市自我檢查全部通過**。剩 2026-10-19（一）開盤實測：推播延遲 < 1 秒、指數漲跌家數是否含漲跌停（與證交所收盤統計比對）、成交量差異（見已知問題）。自我檢查指令：`cd ~/apps/twstock && docker compose -f deploy/compose.yml run --rm --no-deps -T quote python -m app.quote.selftest`；重設金鑰：`ssh -t home "bash ~/apps/twstock/deploy/set-shioaji-keys.sh"`

**新網站開發須知**（P0 起適用）
- 程式碼：`backend/`（FastAPI）、`frontend/`（React）、`deploy/`（compose、hook）、`legacy/`（舊版封存）
- 部署：`git push home local:main` → home server 自動建置並重啟（hook 原始檔 `deploy/post-receive.sh`，伺服器上 `deploy/.env` 不進 git）
- **repo 位置：`C:\dev\taiwan-stock-query`**（2026-10-18 從 `G:\我的雲端硬碟\Claude專區\永豐金API` 搬出；舊資料夾不再使用）
- 本機測試：後端 venv 在 `C:\Users\shoyu\.venvs\twstock-backend`；前端直接在 `frontend/` 執行 `npm ci`、`npm test`、`npm run build`

---

## 4. 待辦（依優先順序）

- [x] ~~**前端改版（P0～P6）**~~：見第 3 節，P0～P5 與 P6a～P6e 全數完成上線（2026-10-17）；剩 2026-10-19（一）P2 開盤實測（NAS 舊站與 cron 已於 2026-10-17 停用）
- [ ] **`xq_quote` 預設欄位擴充**：目前只取 10 個基本欄位，可考慮加入五檔（`BestBid1–5`／`BestAsk1–5`／`BestBidSize1–5`／`BestAskSize1–5`）、`PriceChangeRatio`、`VolumeRatio`、`InSize`／`OutSize`。改 `tools/xq_mcp/server.py`，欄位清單見第 7 節 2026-10-18 日誌（2026-10-18 新增）
- [ ] **分點資料程式化取得**：DDE 讀不到，XQ 只有畫面可看（個股「主力進出」）。待評估：XQ 表格是否有匯出、computer-use 讀畫面、FinMind Sponsor 付費版（2026-10-18 新增）
- [ ] **XQ 與 Shioaji 總量是否漏計收盤集合競價**：兩者 2330 同為 33,389 張，證交所 43,046；10/19 開盤實測，結果同步更新第 5 節對應列（2026-10-18 新增）
- [x] ~~新後端 `backend/app/services/overview.py` 與舊站 `datasources/twse_client.py` 各有一份 T86 欄位對照~~：舊站已封存至 `legacy/`（2026-10-17）
- [x] ~~home server 開機時序~~：改用 `tailnet-proxy` 容器等 Tailscale IP 出現再轉發，不需改主機設定（2026-10-16）
- [x] ~~在 Uptime Kuma（`http://100.100.245.93:3001`）新增監控~~：已建立「台股看盤網站 (twstock)」監控（URL `http://twstock-web-1/api/health`、JSON 查詢 `status` == `ok`），並將 `uptime-kuma` 掛入 `twstock_default` 內網與 `post-receive.sh`，實測 `200 - OK`（7 ms，100% 綠燈）（2026-10-17）
- [x] ~~建議把 repo 搬離 Google 雲端硬碟~~：已搬到 `C:\dev\taiwan-stock-query`（2026-10-18）
- [x] ~~K 線路由待決策~~（2026-10-17 使用者決定：日 K 歷史全用 FinMind、當日與分時用永豐推播、預設不還原可切換；富途留待 P5）
- [x] ~~上櫃股與櫃買指數比較、修正櫃買指數卡~~：已串接櫃買中心 OpenAPI `tpex_index`，市場總覽與上櫃個股頁報告均已納入（2026-10-17）
- [x] ~~個股頁籌碼區加「集保大戶／散戶持股比例」~~：已串接集保結算所公開資料 `getOD.ashx?id=1-5`（散戶 ≤50 張、中實戶 50–400 張、大戶 >400 張與千張大戶），個股頁盤中與盤後模式皆已顯示（2026-10-17）
- [x] ~~**台股「AI 個股健檢」按鈕永遠報錯**~~：舊站已封存至 `legacy/`，新站改由 `/ai` 頁接 Agnes＋TWStockMCPServer＋站內工具（2026-10-17）
- [x] ~~清掉上述殘留 worktree~~：已移除 `.claude/worktrees/elastic-rosalind-06694a`（2026-10-17）
- [x] ~~2026-10-16 的本機改動待 commit 與推送~~：已隨 P6 整理提交並推送至 home server（2026-10-17）
- [x] ~~`config.py` 舊的 `ConfigManager` 相容類別移除 / `daily_job.py` 端點重複~~：舊碼已歸檔至 `legacy/`，不再維護（2026-10-17）

---

## 5. 已知問題

| 問題 | 影響 | 狀態 |
|---|---|---|
| 櫃買指數 Yahoo 代號 `^TWOII` 又抓不到資料 | 舊站市場總覽櫃買卡片空白 | 新站已解決（改接櫃買中心官方 OpenAPI `tpex_index`，支援總覽顯示與上櫃個股比較） |
| TWSE 全市場行情（STOCK_DAY_ALL）更新比指數、法人慢一天 | 舊站同一頁混用不同日期的數字 | 新站已解決（改用可指定日期的 rwd MI_INDEX，整頁同一日） |
| 市場總覽首次載入超過 1.5 分鐘 | 體驗差 | 新站已解決（資料 0.19 秒內顯示） |
| **舊站升級 shioaji 會壞**：`datasources/shioaji_client.py` 用了 `login(fetch_contract=...)`，1.7.8 已移除此參數 | 舊站已封存 `legacy/` | 新站已鎖 `shioaji==1.7.8` 並修正參數 |
| 永豐金模擬環境快照的總量與官方不同：2330 於 10/16 快照 33,389 張，證交所 43,046 張（價格完全一致） | 量相關數字可能偏低 | 待 10/19 開盤實測，推測快照未計收盤集合競價 |

---

## 6. 文件地圖

| 文件 | 內容 |
|---|---|
| `PROJECT.md`（本檔） | 進度、待辦、已知問題、工作日誌 |
| `CLAUDE.md` | 操作手冊：部署流程、API 設定、選單對照、歷史代理人紀錄（2026-06 以前） |
| `AGENTS.md` / `GEMINI.md` | 指標檔，指向本檔與 CLAUDE.md |
| `docs/plans/FRONTEND_REWRITE_ARCH_2026-10.md` | 2026-10 新網站前後端分離架構與 P0–P6 分期紀錄 |
| `docs/plans/REDESIGN_PLAN_2026-07.md` | 2026-07 重構計畫 R1–R6 與執行結果（歷史） |
| `docs/plans/IMPROVEMENT_PLAN_2026-07.md` | 2026-07 修 bug 計畫 P0–P4 與執行結果（歷史） |

---

## 7. 工作日誌（新的寫在最上面）

### 2026-10-20｜Claude Opus 5.5（全球市場：代號網址＋指數可點）
- 做了什麼：全球市場頁「港美股查詢」的代號改放網址（`/global?s=AAPL`），可分享、加書籤、上一頁回前一檔；從網址帶代號進來會自動捲到查詢區。指數、期貨、匯率四組表格的名稱改成可點，點了在查詢區看該商品日 K（Yahoo 代號如 `^GSPC`、`GC=F`、`TWD=X` 皆實測有 K 線）。
- 更正：先前回覆使用者「全球 K 線沒有成交量與均線」是錯的——`GlobalPage` 與個股頁共用 `KChart`，本來就有 MA 與量；本次未動 K 線圖本身。
- 改了哪些檔：`frontend/src/pages/GlobalPage.tsx`
- 怎麼驗證：`tsc --noEmit` 無錯誤、vitest 45 passed；本機 vite（暫時 proxy 到線上後端，暫存設定已刪）實測：`?s=TSM` 載入後查詢區在視窗頂端（top 16px）、點「費城半導體」網址變 `?s=%5ESOX` 且顯示 PHLX Semiconductor、`history.back()` 回到 TSM；重新整理後點「道瓊」，console 無錯誤
- 沒做完／新發現：**尚未 commit／部署**；捲動要等下方美股區載入（頁面不夠高時 `scrollIntoView` 會被捲動上限卡住）；第 2 步（港美股基本面：財報、本益比、股利）未做，Yahoo 能取得哪些欄位待查

### 2026-10-20｜Claude Sonnet 5.5（ETF 股利）
- 做了什麼：修好個股頁「基本面 → 歷年股利政策」對 ETF 永遠空白。根因：`TaiwanStockDividend` 的 `year` 欄個股是 `112年第3季`、ETF 只有 `112`（沒有「年」字），`fundamentals._ROC_YEAR` 只認 `(\d{2,3})年`，ETF 全部列被略過（FinMind 其實有 ETF 股利，先前推測「FinMind 沒有」是錯的，已更正）。正則改為 `\s*(\d{2,3})(?!\d)`，兩種格式都吃。
- 改了哪些檔：`backend/app/services/fundamentals.py`、`backend/tests/test_fundamentals.py`（新增 `test_etf_dividends_year_without_suffix`）
- 怎麼驗證：`pytest backend/tests` 90 passed、ruff 通過；用 FinMind 即時資料跑 0056，`dividend_years` 回 2017–2026 共 10 年（例：2022 年 2.1 元、2024 年 3.63 元）；前端對 `eps`／`payout` 為 null 已顯示「—」，不需改
- 部署與線上驗證：已 `git push home local:main` 部署（`584d8fd..a8136a6`，`/api/health` 回 `version: a8136a6`）；線上 `/api/stock/0056/fundamentals` 的 `dividends` 10 筆（最新 2026：3.216 元、3 次）、`/0050` 10 筆（2026：1.6 元、2 次）、`/2330` 仍 10 筆（無退步）；瀏覽器開 `/stock/0056` 展開「財務基本面」，「歷年股利政策」顯示 2017–2026 十年，現金股利有值，EPS 與配發率為「—」
- 沒做完／新發現：ETF 的損益、資產負債、本益比河流圖、同業比較仍為空（ETF 本來就沒有，前端已有提示）；0056 的 2024 年「5 次」與 2025 年「3 次」來自 FinMind 的所屬年度歸屬，未逐筆對照證交所公告，若要精確再查

### 2026-10-20｜Claude Sonnet 5.5（ETF 個股頁白屏）
- 做了什麼：修好個股頁查 ETF（0050、0056）整頁白屏。根因：ETF 無月營收，API 回 `revenue: []`，`RevenueBars` 直接讀 `rows[rows.length-1].year` 而 `last` 為 undefined → React 拋 `Cannot read properties of undefined (reading 'year')`。加空陣列防呆，改顯示「無月營收資料（ETF 不公布營收）」。
- 改了哪些檔：`frontend/src/pages/StockPage.tsx`（`RevenueBars` 開頭加 `if (!rows.length) return ...`）
- 怎麼驗證：先在線上站 `/stock/0050` 重現白屏與 console 錯誤；修後以本機 vite（暫時 proxy 到線上後端，已刪暫存設定）開 `/stock/0050`、`/stock/0056`，頁面正常、console 無錯誤；`tsc --noEmit` 無錯誤、vitest 45 passed
- 沒做完／新發現：**尚未 commit／部署**（線上站仍是舊版，ETF 仍白屏）；（後續更正：ETF 股利 FinMind 其實有，只是 `year` 格式不同，已於同日另一筆日誌修好，不必改接證交所）；未加此防呆的單元測試（專案前端測試只涵蓋 `lib/`，元件無測試）

### 2026-10-18｜Claude Sonnet 5.5（XQ 欄位與分點調查）
- 做了什麼：用 `xq_raw` 探索 XQ DDE 可讀欄位，並由使用者截圖確認 XQ 軟體介面的分點資料位置。純調查，未改程式。
- 改了哪些檔：`PROJECT.md`（本筆）；Claude 專案記憶 `reference_xq_dde.md`（不在 repo 內）
- 怎麼驗證：2330 收盤後逐一實測；五檔量與 XQ 畫面一致（508/776/958/498/1996、698/394/491/604/525），`BidAskDiff` 2024 ＝ 4736−2712 驗算相符
- **DDE 可讀（2330 實測有值）**：
  - 五檔：`BestBid1`–`5`、`BestAsk1`–`5`（價）；`BestBidSize1`–`5`、`BestAskSize1`–`5`（量，張）；`BidAskDiff`（委買總量−委賣總量）
  - 內外盤：`InSize`、`OutSize`、`InOutRatio`（顯示值是外盤比，32.52%）
  - 漲跌與量能：`PriceChange`、`PriceChangeRatio`、`Amplitude`、`PreTotalVolume`（昨量）、`VolumeRatio`、`TurnoverRatio`、`AvgPrice`、`Value`（成交金額，元）、`UpLimit`／`DownLimit`
  - 基本面：`PERatio`、`ROE`、`CashDividend`、`Capital`、`MarketValue`（後兩者單位未驗證，推測為億）
  - 預設 `xq_quote` 只取 10 個基本欄位，以上需自行用 `fields` 指定
- **DDE 讀不到**：分點、三大法人買賣超、融資融券餘額（`ShortBalance`=9、`ShortSell`=4 有值但含義未驗證）、均線、52 週高低。名稱是猜的，回 `--` 不等於不存在
- **XQ 軟體介面有分點，但只在畫面上，無 DDE／匯出管道（匯出功能尚未確認）**：
  - 個股：「台股個股分析」→ 輸入代號（如 `2330.TW`）→ 下方「主力」頁籤 →「主力進出」，前十大買超／賣超券商（張數），可選期間（預設近一日）
  - 全市場：選股選單「券商進出表」→「券商分點進出金額排行」（金額，百萬元），可再進「分點明細查詢」（某分點買賣了哪些股）
  - 分點為收盤後公布，標題日期為最近交易日（實測 10/16）；盤中是否顯示當日未實測
- 沒做完／新發現：
  - 永豐金 Shioaji 官方文件導覽無分點 API（只看導覽列，未逐頁細讀）；FinMind 分點為付費版（Sponsor）
  - 若要程式化取得分點，選項：XQ 表格匯出（待查）、computer-use 讀畫面、FinMind Sponsor
  - 待辦（未做）：是否把五檔／漲跌幅／量比加進 `xq_quote` 預設欄位（會改 `tools/xq_mcp/server.py`，待使用者決定）
  - 注意：XQ 的 `TotalVolume` 33,389 與已知問題第 115 列的 Shioaji 快照同為 33,389，證交所為 43,046；XQ 與 Shioaji 數字相同，推測同樣未含收盤集合競價（未驗證，待 10/19 開盤實測）

### 2026-10-18｜Claude Opus 5.5
- 做了什麼：**repo 搬到 `C:\dev\taiwan-stock-query`**（使用者要求）。在新位置重新 clone（不直接複製，避開舊 `.git` 裡 Drive 留下的孤立 pack 索引與殘留鎖檔），補回全部 5 個本機分支、三個遠端（origin／home／nas）與分支追蹤設定，複製 `.claude/settings.local.json`；舊資料夾原封不動保留
- 改了哪些檔：`README.md`（前端改為直接在 `frontend/` 跑 npm，移除鏡像目錄步驟）、`PROJECT.md`
- 怎麼驗證：新位置 `git fsck` 無警告、`git log` 與舊位置同為 `42809f6`、`git status` 乾淨；前端 `npm ci`／typecheck／vitest 45 passed／build 通過；後端 pytest 全部通過、ruff 通過
- 沒做完／新發現：舊資料夾 `G:\我的雲端硬碟\Claude專區\永豐金API` 待使用者確認後再刪；Claude Code 的專案記憶依路徑分開，已複製到新路徑對應的記憶資料夾；之後請在 `C:\dev\taiwan-stock-query` 開新 session

### 2026-10-17｜Claude Opus 5.5
- 做了什麼：**推送到 GitHub**（使用者要求；`origin` 為公開倉庫）。依 CLAUDE.md 流程 `local` → `main`（`--no-ff`）→ `git push origin main`；**未推 NAS remote**（舊站部署管道已停用）。GitHub 上原有 2 筆舊排程資料提交（7/7、7/8）在合併時自動歸入 `legacy/data/`。推送前掃描新增內容無金鑰（範例檔皆空值）；首次公開 home server 的 Tailscale 位址與主機名（僅 tailnet 內可連）。之後 `local` 快轉到 `main` 並部署 home server
- GitHub CI 首次失敗：P6e 新增的 `ruff check` 步驟，但 `backend/requirements-dev.txt` 沒有 ruff（exit 127）→ 補上 `ruff>=0.17,<0.18`
- 改了哪些檔：`backend/requirements-dev.txt`、`PROJECT.md`；合併提交 `2a31e3e`
- 怎麼驗證：`git push origin main` 成功（`4b20f51..2a31e3e`）；合併結果與 `local` 只差 `legacy/data/` 舊資料檔；CI 修正後結果見下一次推送
- 沒做完／新發現：Google Drive 又留下 `.git/ORIG_HEAD.lock` 殘留，造成第一次合併「stash failed」，確認無 git 程序後刪除

### 2026-10-17｜Claude Opus 5.5
- 做了什麼：**舊站正式停用（NAS 端收尾）**。使用者開機 NAS 並自行輸入 sudo 密碼執行：
  1. 查證 NAS 上**已無 `sinopac-web` 容器**（現有容器：PortainerCE、postgresql、jcic-opendata、KavitaD、Ubooquity、CalibreWeb），舊網站 8502 無回應，不需再停
  2. 舊每日排程 `run_daily.sh` 其實每個平日 20:00 仍在執行，但每次失敗（git `dubious ownership`＋缺 `FinMind` 套件），未產出資料；已備份 root crontab 至 `/volume1/docker/sinopac/crontab.bak-20261017` 後把該行註解（恢復：拿掉行首 `#`）
- 改了哪些檔：NAS root crontab（非 repo）、`PROJECT.md`
- 怎麼驗證：`sudo crontab -l` 顯示 `#0 20 * * 1-5 /bin/sh /volume1/docker/sinopac/run_daily.sh …`；`docker ps -a` 無 sinopac-web；`curl 192.168.0.171:8502` 無回應
- 沒做完／新發現：NAS 上 `postgresql` 容器是舊 daily_job `PG_URL` 的寫入目標之一（推測），新站不使用，是否保留由使用者決定；NAS 上的 sudo 免密碼只開放 `docker restart sinopac-web`，該容器已不存在，該條 sudoers 規則可由使用者日後移除

### 2026-10-17｜Antigravity (Gemini)
- 做了什麼：**全專案深度檢查測試、6 項細節優化與 Uptime Kuma 內網連通完成並部署上線**。
  1. **櫃買指數（TPEx）官方串接與上櫃個股比較**：串接櫃買中心 OpenAPI `tpex_index`，市場總覽「加權指數」卡片同步顯示同日櫃買指數收盤與漲跌幅；上櫃個股頁報告（如 6488 環球晶）自動與同日櫃買指數比較強弱
  2. **集保大戶／散戶股權分散表**：串接集保結算所公開資料 `getOD.ashx?id=1-5`（worker 每 12 小時快取至 Redis `tdcc:latest`，涵蓋上市＋上櫃），彙整 `>400 張大戶`、`>1,000 張千張大戶`、`50–400 張中實戶`、`≤50 張散戶` 持股比例與總股東人數，於個股頁盤中與盤後模式呈現視覺化結構橫條與摘要
  3. **投資行事曆跨日法說會 `end_date` 修正**：`calendar.conference_events` 為跨日法說會補上 `end_date`，前後端皆以 `end_date` 判斷活動是否已結束，解決進行中的跨日法說會被隱藏或被 AI 助理誤判為已過期的問題
  4. **AI 助理補齊 P6 四大站內工具**：`backend/app/ai/tools.py` 新增 `site_stock_fundamentals`（季損益／資產負債／股利／PER 分位／同業）、`site_screener`（技術訊號＋產業＋台灣 50 多因子篩選）、`site_attention`（處置股與注意股）、`site_us_stocks`（美股權值 50 與財報日曆）
  5. **前端路由 `React.lazy` Code-Splitting**：`App.tsx` 將非首頁路由改為動態載入，主包體積由 `562 kB` 降至 `319.9 kB`（gzip `100.8 kB`），消除 Vite `> 500 kB` 打包警告
  6. **後端測試 Pytest 10 警告清除**：修正 `tests/test_overview.py` 的 class-scoped fixture 寫法並補齊上述新功能的單元測試
  7. **Uptime Kuma 監控網路連通修正**：實測發現 `uptime-kuma` 容器（位於 `frontend` 橋接網路）若直接請求主機 Tailscale IP `100.100.245.93:8600` 會被 Tailscale 的 `ts-input` 防偽規則攔截逾時；已將 `uptime-kuma` 掛入 `twstock_default` 網路並寫入 `deploy/post-receive.sh`，實測容器內 `curl http://twstock-web-1/api/health` 秒回 200 OK（同時保持 `twstock` 與 `cloudflare-tunnel` 隔離）。另查 `uptime-kuma`（`http://100.100.245.93:3001`）尚未建立初始管理員帳號（`user` 表為空），待使用者首次登入設定帳密後填入 `http://twstock-web-1/api/health` 即可
- 改了哪些檔：`backend/app/sources/tpex.py`、`backend/app/services/overview.py`、`backend/app/services/stock.py`、`backend/app/services/stock_loader.py`、`backend/app/services/calendar.py`、`backend/app/worker.py`、`backend/app/ai/tools.py`、`backend/tests/test_overview.py`、`backend/tests/test_stock.py`、`backend/tests/test_calendar.py`、`backend/tests/test_ai.py`、`frontend/src/App.tsx`、`frontend/src/lib/api.ts`、`frontend/src/lib/calendar.ts`、`frontend/src/lib/calendar.test.ts`、`frontend/src/pages/Overview.tsx`、`frontend/src/pages/StockPage.tsx`、`frontend/src/pages/StockPage.module.css`、`deploy/post-receive.sh`、`PROJECT.md`
- 怎麼驗證：後端 pytest 89 passed、ruff 通過；前端 typecheck、vitest 45 passed、build 零警告通過；部署至 home server 後實測線上 API 與 `docker exec uptime-kuma curl -s http://twstock-web-1/api/health` 全數 200 OK
- 沒做完／新發現：程式碼層面待辦已全數清空；僅剩外部環境操作（2026-10-19 盤中實測永豐推播、下次開 NAS 停舊容器、使用者首次登入 Uptime Kuma 建立管理員帳號）


### 2026-10-17｜Antigravity (Gemini)
- 做了什麼：**P6e 舊站歸檔 `legacy/`、清除殘留 worktree、更新 CI 與文件完成**。
  1. 以 `git mv` 將舊版 Streamlit 網站（`app.py`、`tabs/`、`ui/`、`datasources/`、`screener.py`、`daily_job.py`、`cli.py`、舊 `tests/`、舊 `data/` 等 51 個根目錄項目與 `.github/workflows/daily.yml`）全數歸檔至 `legacy/`，根目錄只保留 `backend/`、`frontend/`、`deploy/`、`docs/` 與說明文件
  2. 移除 2026-07 殘留的 git worktree `.claude/worktrees/elastic-rosalind-06694a`
  3. 更新 `.github/workflows/ci.yml`（移除舊版 Streamlit test job，保留 `backend` ruff+pytest 與 `frontend` typecheck+vitest+build），並同步更新 `README.md`、`CLAUDE.md`、`docs/plans/FRONTEND_REWRITE_ARCH_2026-10.md` 與 `PROJECT.md`
- 改了哪些檔：`legacy/*`（`git mv` 52 項）、`.github/workflows/ci.yml`、`README.md`、`CLAUDE.md`、`docs/plans/FRONTEND_REWRITE_ARCH_2026-10.md`、`PROJECT.md`
- 怎麼驗證：後端 pytest 86 passed、ruff 通過；前端 typecheck、vitest 44 passed、build 通過；推送部署至 home server 後 `/api/health` 回 200 OK
- 沒做完／新發現：NAS 目前關機中，待使用者下次開機 NAS 時執行 `sudo docker stop sinopac-web && sudo docker update --restart=no sinopac-web` 並停用 NAS cron 即可

### 2026-10-17｜Antigravity (Gemini)
- 做了什麼：**P6d 技術掃描與多因子選股完成並部署上線**（整合至 `/screener` 選股頁，取代舊站 `screener.py` 與 `tabs/technical_scanner.py`）。
  1. 後端：`worker` 將最近 60 個交易日的證交所 `MI_INDEX` 普通股 OHLCV 精簡快取於 Redis（`twse:ohlcv:{d}`，TTL 90 天，首次由近到遠分批回補並容錯防 307 限流，常態每 10 分鐘 0 額外請求），並串接證交所 OpenAPI `t187ap05_L` 一次取得全市場最新月營收年增率（`rev_yoy`）；純 Python 計算全市場 1,081 檔上市普通股的 MA5/10/20/60、RSI(14)、KD(9,3)、MACD(12,26,9)、布林通道(20,2)、量比與 16 項技術訊號標籤（含台灣 50 成分股標記 `in_tw50` 與三大法人合計買賣超），預先寫入 `screener:base`
  2. 前端：`/screener` 新增「全市場／台灣 50 權值股」範圍切換、即時四階段「多因子篩選漏斗」（母體 → 1. 技術面 → 2. 籌碼面 → 3. 估值與財報）、四大類 16 項技術指標掃描按鈕（即時顯示目前股票池符合檔數，支援 OR／AND 切換）、籌碼快捷條件（支援 OR／AND 切換）與月營收年增率門檻，瀏覽器端切換條件毫秒級即時回應，表格新增技術訊號標籤、量比、RSI(14)、K/D、營收 YoY% 欄位與排序
- 改了哪些檔：`backend/app/sources/twse.py`、`backend/app/services/screener.py`、`backend/app/worker.py`、`backend/tests/test_screener.py`、`frontend/src/lib/screener.ts`、`frontend/src/lib/screener.test.ts`、`frontend/src/pages/ScreenerPage.tsx`、`frontend/src/pages/ScreenerPage.module.css`、`PROJECT.md`
- 怎麼驗證：後端 pytest 86 passed、ruff 通過；前端 typecheck、vitest 44 passed、build 通過；線上 `http://100.100.245.93:8600/api/screener/base` 回 1,081 檔普通股且 `tech_days=60`（2330 台積電 `in_tw50=True`、2026-09 營收 YoY +54.65%、RSI 37.5、MA5 2476 / MA20 2491 / MA60 2421.17、量比 1.61x、觸發 `kd_oversold` 與 `ma5_death_ma20`）
- 沒做完／新發現：證交所 `MI_INDEX` 連續無間隔請求超過 ~40 次會回 `307 Temporary Redirect` 限流，已改為近到遠分批（單輪最多 25 天、間隔 0.6s）與單日 try/except 容錯，實測 60 個交易日已全數快取完成。下一步 P6e（搬移 `legacy/`、更新 CI 與文件）

### 2026-10-17｜Antigravity (Gemini)
- 做了什麼：**P6c 美股選股＋財報日曆完成並部署上線**（整合至 `/global` 全球市場頁）。
  1. 後端：`yahoo.quotes` 以 Yahoo Finance v7 批次端點（含 cookie/crumb）一次請求取得全數 50 檔美股權值股（M7、半導體、軟體、消費、金融、生技、能源工業）的收盤價、市值、本益比、前瞻本益比、殖利率、52 週高低拉回幅度、均線位置、預估 EPS、財報公布日（美東）與華爾街評等分數（耗時 ~1 秒，取代舊站逐檔呼叫 100 次 `yfinance`）；worker 每 30 分鐘更新 Redis `us:latest`，新增 `/api/global/us`
  2. 前端：全球市場頁（`/global`）新增「美股權值 50 多因子選股」（7 組快選策略＋板塊、市值、本益比、前瞻 PE、殖利率、年線篩選與欄位排序）與「美股財報日曆與華爾街共識」（可切換近期財報／全部 50 檔），點擊任一美股直接連動頁面上方日 K 線圖
- 改了哪些檔：`backend/app/sources/yahoo.py`、`backend/app/services/us_stocks.py`（新）、`backend/app/worker.py`、`backend/app/api_global.py`、`backend/tests/test_global.py`、`backend/tests/fixtures/yahoo_us_quotes.json`（新）、`frontend/src/lib/usStocks.ts`（新）、`frontend/src/lib/usStocks.test.ts`（新）、`frontend/src/pages/GlobalPage.tsx`、`frontend/src/pages/GlobalPage.module.css`、`PROJECT.md`
- 怎麼驗證：後端 pytest 82 passed、ruff 通過；前端 typecheck、vitest 42 passed、build 通過；線上 `http://100.100.245.93:8600/api/global/us` 回 50 檔美股與 49 筆近期財報（NVDA 市值 5,170.6B、財報日 2026-11-17、評等 1.3 強力買進；AAPL 收 343.46、財報日 2026-11-02）
- 沒做完／新發現：下一步 P6d（技術掃描與多因子選股）

### 2026-10-17｜Antigravity (Gemini)
- 做了什麼：**P6b 個股基本面完成並部署上線**。
  1. 後端：實作 `stock_loader.load_fundamentals`（FinMind 損益表、資產負債表、股利政策快取 12 小時；本益比沿用 `finmind:TaiwanStockPER:{code}` 快取鍵；同業比較讀取 Redis `screener:base`）與路由 `/api/stock/{code}/fundamentals`
  2. 前端：新增 `FundamentalsPanel`（個股頁盤中與盤後模式皆預設收合，點擊展開才請求 `/api/stock/{code}/fundamentals`），顯示單季損益與三率（含近四季合計 EPS）、SVG 本益比河流圖（P10/P25/P50/P75/P90 倍數帶與收盤價）、資產負債結構、歷年股利政策（依所屬年度合併季配息與配發率）、同業比較表
- 改了哪些檔：`backend/app/services/stock_loader.py`、`backend/app/api_stock.py`、`backend/tests/test_fundamentals.py`、`frontend/src/lib/fundamentals.ts`（新）、`frontend/src/components/FundamentalsPanel.tsx`（新）、`frontend/src/components/FundamentalsPanel.module.css`（新）、`frontend/src/pages/StockPage.tsx`、`PROJECT.md`
- 怎麼驗證：後端 pytest 81 passed、ruff 通過；前端 typecheck、vitest 40 passed、build 通過；部署至 home server 後實測 `http://100.100.245.93:8600/api/stock/2330/fundamentals` 回 200（近四季 EPS 86.28、2026Q2 EPS 27.25、本益比 28.05、半導體業同業 92 檔中位數本益比 28.05）
- 沒做完／新發現：下一步 P6c（美股選股＋財報日曆）

### 2026-10-17｜Claude Opus 5.5
- 做了什麼：**P6b 個股基本面進行中（未部署）**。完成純函式 `backend/app/services/fundamentals.py`：季損益（毛利率／營益率／淨利率／營收年增、近四季 EPS）、資產負債（負債比、流動比、每股淨值）、股利依所屬年度彙總與配發率、本益比河流圖（隱含 EPS × 歷史本益比 10/25/50/75/90 百分位）、同業比較（選股總表同產業）。已確認 FinMind 損益表為單季數字（2330 2026Q2 營收＝4～6 月營收合計）；金融業無毛利欄位
- 改了哪些檔：`backend/app/services/fundamentals.py`（新）、`tests/test_fundamentals.py`、fixtures（2330 損益／資產負債／股利、2881 損益）
- 怎麼驗證：`tests/test_fundamentals.py` 3 passed
- 沒做完：`stock_loader.load_fundamentals`（FinMind 快取 12 小時；PER 沿用 `finmind:TaiwanStockPER:{code}` 鍵）、`/api/stock/{code}/fundamentals`、前端個股頁基本面區塊（展開才載入）、部署驗證；之後 P6c、P6d、P6e

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

### 2026-10-18｜Claude
- 做了什麼：修全球市場頁排版——各組表格超出卡片、迷你走勢線被切、頁面出現橫向捲軸。表格外包 `tableBox`（可捲動），走勢線寬 96→72，卡片最小寬 320→360。
- 改了哪些檔：`frontend/src/pages/GlobalPage.tsx`、`GlobalPage.module.css`
- 怎麼驗證：tsc 無錯誤；尚未部署、未在瀏覽器實測
- 沒做完／新發現：待使用者確認後 commit 並 `git push home local:main` 部署

### 2026-10-18｜Claude（XQ MCP）
- 做了什麼：新增 XQ 全球贏家 DDE 報價 MCP server，讓 Claude 能直接查本機 XQ 報價。DDE 語法 `XQLITE|Quote!2330.TW-Price`；ctypes 呼叫 DDEML，免 pywin32。工具：`xq_quote`、`xq_raw`。
- 改了哪些檔：`tools/xq_mcp/server.py`（新）；Claude Code user scope 註冊 `xq`，venv 在 `C:\Users\shoyu\.venvs\xq-mcp`（mcp 2.x）
- 怎麼驗證：stdio 端對端測試取得 2330／2454 報價、6488 名稱；`claude mcp get xq` 顯示 Connected
- 沒做完／新發現：只限本機、XQ 須開著；加權指數的 XQ 代號未查出（`TSE.TW` 回 `--`）；網站（home server）用不到此資料

> 2026-06 以前的紀錄見 `CLAUDE.md`「代理人互動紀錄」章節。
