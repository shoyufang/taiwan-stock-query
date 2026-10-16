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
| 前端改版 | **已決定放棄 Streamlit，改走 B 方案（前後端分離）**。**P0 地基已上線**：home server `http://100.100.245.93:8600`（僅 Tailscale），目前只有頁面骨架與系統狀態。下一步 P1，見第 3 節 |
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
3. ~~依架構文件 P0（地基）開工~~（2026-10-16 完成）→ 下一步 P1 市場總覽（盤後）

**新網站開發須知**（P0 起適用）
- 程式碼：`backend/`（FastAPI）、`frontend/`（React）、`deploy/`（compose、hook）
- 部署：`git push home local:main` → home server 自動建置並重啟（hook 原始檔 `deploy/post-receive.sh`，伺服器上 `deploy/.env` 不進 git）
- 本機測試：後端 venv 在 `C:\Users\shoyu\.venvs\twstock-backend`；前端在 `C:\Users\shoyu\dev\twstock-fe` 鏡像執行 npm（**不要在雲端硬碟資料夾裡建 venv 或 node_modules**，數萬個小檔會拖慢並被同步）

---

## 4. 待辦（依優先順序）

- [ ] **前端改版**：見第 3 節（P0 ✅ 2026-10-16，下一步 P1）
- [ ] **home server 開機時序（需使用者執行，涉及系統設定）**：Docker 未設定在 Tailscale 之後啟動，重開機時網站可能綁不到 Tailscale IP 而起不來。修法見 2026-10-16 P0 日誌
- [ ] 在 Uptime Kuma 新增監控 `http://100.100.245.93:8600/api/health`（需使用者登入 Uptime Kuma 設定）
- [ ] 建議把 repo 搬離 Google 雲端硬碟（例如 `C:\dev\`）：2026-10-16 已出現 `.git` 孤立索引檔警告、venv 建置卡住，都是同步軟體干擾的徵兆
- [ ] **K 線路由 `get_kbar()` 待決策**：Shioaji 只有 2020 年起資料、FinMind 從 1994 年起，歷史 K 線用哪個日期切換？富途港股要不要併入統一入口？（使用者交代：下次碰 router 時要先提醒他決定）
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
| TWSE 全市場行情（STOCK_DAY_ALL）更新比指數、法人慢一天 | 同一頁混用不同日期的數字 | 未修；新前端需統一資料日期 |
| 市場總覽首次載入超過 1.5 分鐘 | 體驗差 | 未修；改版時從架構上解決 |
| 台指期卡片顯示「—」 | 資料缺漏 | 未查 |

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
