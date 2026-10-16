# 新網站技術架構（B 方案）— 2026-10-16

> 狀態：**草案，待使用者確認**。確認後依第 10 節分期實作，每期完成都要更新 `PROJECT.md`。
> 設計稿：https://claude.ai/artifact/SnQBAF4Ez4KvGaRsPqX4TW（市場總覽 A/B/C、個股盤中／盤後）

---

## 1. 已確定的決策

| # | 決策 | 日期 | 決定者 |
|---|---|---|---|
| D1 | 放棄 Streamlit，前後端分離 | 2026-10-16 | 使用者 |
| D2 | 雙模式：盤中＝深色終端機（設計稿 A），盤後＝研究報告（設計稿 B），可手動切換 | 2026-10-16 | 使用者 |
| D3 | 只透過 **Tailscale** 存取（家裡與外出皆可），網站不對公網開放，不做登入 | 2026-10-16 | 使用者 |
| D4 | 盤中行情**逐筆即時推播**（不是定時輪詢） | 2026-10-16 | 使用者 |
| D5 | **直接切換**：新站完整取代舊站後才上線；開發期間舊 Streamlit 站維持原樣 | 2026-10-16 | 使用者 |
| D6 | 新站部署在 **home server（shoyulinux）**，不放 NAS | 2026-10-16 | 使用者 |

---

## 2. 部署環境：home server

實測（2026-10-16）：

| 項目 | 規格／現況 |
|---|---|
| 主機 | `shoyulinux`，Ubuntu 26.04 LTS，SSH 別名 `home`（Tailscale 100.100.245.93） |
| CPU / 記憶體 | Intel i7-7700（4 核 8 緒）／14 GB（約 8.6 GB 可用） |
| 磁碟 | 根分割區 115 GB，**剩 43 GB**（逐筆資料不可無限累積，見 §5.4） |
| Docker | 29.6.2，Compose v5.3.1 |
| 可重用的現有服務 | `postgres`（pgvector/pg17，5432）、`uptime-kuma`（監控）、`dozzle`（log） |
| 不可碰的現有服務 | `firecrawl-redis`（別人的 Redis，不共用）、`nginx-proxy-manager` 與 `cloudflare-tunnel`（公網入口，本站**不得**掛上去，違反 D3） |
| 已佔用的埠 | 80、81、443、3001、3002、5000、5432、8081、8088、8090、8501、8765、38083 |
| 區網 | 可連到 NAS（192.168.0.171） |

**本站使用的埠**：`8600`（網頁＋API，單一入口）。只綁定 Tailscale 介面 IP（`100.100.245.93:8600`），不綁 `0.0.0.0`，所以區網與公網都看不到，只有 Tailscale 裝置能開。

---

## 3. 整體架構

```
  瀏覽器（手機／電腦，經 Tailscale）
        │  http://100.100.245.93:8600
        ▼
┌────────────────────── home server（docker compose：twstock）──────────────────────┐
│                                                                                   │
│  web（nginx）──── /        → 前端靜態檔（React 建置產物）                         │
│        │      └── /api/*   → api                                                  │
│        │      └── /ws      → api（WebSocket）                                     │
│        ▼                                                                          │
│  api（FastAPI, Python 3.13）── 讀 redis 熱資料 ── 讀 postgres ── 呼叫 datasources/router │
│        ▲  WebSocket 轉送                                                          │
│        │                                                                          │
│  redis（本站專用）── pub/sub 即時行情、最新報價、預先算好的頁面資料                 │
│        ▲                                                                          │
│  quote（行情服務）── 唯一的 Shioaji 長連線，訂閱逐筆／五檔，寫入 redis              │
│  worker（排程）──── 盤後預先計算市場總覽、個股摘要；日後接手 daily_job             │
│                                                                                   │
│  postgres（沿用現有 pg17 容器，新建資料庫 twstock）                                 │
└───────────────────────────────────────────────────────────────────────────────────┘
        │ 區網
        ▼
  NAS：舊 Streamlit 站（切換前照常運作）、data/ CSV 歷史檔、備份
```

**為什麼拆成這幾個容器**
- `quote` 獨立：永豐金同一帳號只該維持一條行情連線；API 重啟、改版部署時，行情連線不中斷。
- `redis`：行情服務一秒可能收到上百筆成交，用 pub/sub 分發給所有開著的瀏覽器；「最新報價」「市場總覽」放記憶體，頁面打開即回，解決現在 1.5 分鐘的載入問題。
- `worker`：慢的計算（全市場排行、法人彙總、個股摘要句子）事先算好存起來，不在使用者打開頁面時才算。

---

## 4. 後端

### 4.1 技術選型
| 用途 | 選擇 | 理由 |
|---|---|---|
| Web 框架 | FastAPI＋uvicorn | 原生支援 async 與 WebSocket；自動產生 API 文件 |
| 資料驗證 | Pydantic v2 | 每個 API 回傳都有明確欄位定義，前端可自動產生型別 |
| 快取／推播 | Redis 7（本站專用容器） | pub/sub＋TTL 快取 |
| 資料庫 | PostgreSQL 17（沿用現有容器，新資料庫） | 自選股、警示、設定、日線歷史 |
| 排程 | APScheduler（在 worker 內） | 不必另裝 cron 容器 |
| Python 版本 | **3.13**（Docker 與本機一致） | 解決目前 NAS 3.11、本機 3.13 不一致 |

### 4.2 程式碼結構（新增，不動既有檔案）
```
backend/
  app/
    main.py            # FastAPI 入口、掛載路由與 WebSocket
    settings.py        # 從環境變數讀設定（不讀 st.secrets）
    api/               # 路由：market.py、stock.py、watchlist.py、ws.py …
    schemas/           # Pydantic 回傳格式
    services/          # 商業邏輯：overview.py、stock_report.py（摘要句子產生）…
    cache.py           # Redis 存取
  quote/main.py        # 行情服務
  worker/main.py       # 排程與預先計算
  tests/
frontend/              # 見第 6 節
deploy/
  compose.yml
  nginx.conf
  .env.example         # 只放欄位名稱，不放值
```
- **沿用**：`datasources/`、`datasources/router.py`、`stock_pools.py`、`calendar_engine.py`、`sector_map.py`、`chip_analysis.py`、`ai_engine.py`。
- **2026-10-17 修訂（P1 實作時）**：`datasources/` 套件的 `__init__.py` 會連帶載入 shioaji、FinMind，
  新後端的證交所與 Yahoo 抓取改在 `backend/app/sources/` 獨立實作（輕量、可指定日期）。
  需要永豐金或 FinMind 的功能（P2、P3）再評估是直接 import 對應模組或同樣獨立實作。
- **不能直接用**（綁 Streamlit 快取）：`query_wrapper.py`、`caching.py`、`screener.py`。新後端不 import 它們；選股邏輯要從 `screener.py` 抽出純函式（P5 處理）。
- `config.py` 的 `get_secret()` 會嘗試讀 Streamlit secrets；新後端一律用 `backend/app/settings.py` 讀環境變數，啟動時檢查必要變數並明確報錯。

### 4.3 API 草案
| 方法 | 路徑 | 說明 |
|---|---|---|
| GET | `/api/health` | 健康檢查（Uptime Kuma 監控用） |
| GET | `/api/market/overview?mode=live\|close` | 市場總覽（指數、寬度、法人、排行）；盤後版另含摘要句 |
| GET | `/api/market/index-series?symbol=TAIEX&range=6m` | 指數走勢 |
| GET | `/api/stock/{code}/quote` | 個股報價卡 |
| GET | `/api/stock/{code}/kbar?freq=D\|W\|M&range=6m` | K 線（依賴 get_kbar 決策） |
| GET | `/api/stock/{code}/chips?days=15` | 法人＋融資券 |
| GET | `/api/stock/{code}/fundamentals` | 月營收、估值五年位置 |
| GET | `/api/stock/{code}/report` | 盤後報告（摘要句＋各段結論） |
| GET/PUT | `/api/watchlist` | 自選股 |
| WS | `/ws` | 即時推播：客戶端送 `subscribe`／`unsubscribe`，伺服器推 `tick`、`bidask`、`index` |

### 4.4 資料日期契約（修正現有站「同頁混不同日期」）
每個回傳都帶 `asof`（資料日期）與 `source`。市場總覽由 worker 在同一個 `asof` 下組裝：若某來源（例如 TWSE 全市場行情）尚未更新到當日，整頁退回到「所有來源都齊全的最近一個交易日」，並在頁面標示；不得把今天的指數和昨天的排行放在同一頁。

---

## 5. 即時行情設計（D4）

### 5.1 流程
```
永豐金 Shioaji ──(tick / bidask callback)──▶ quote 服務
   ─▶ redis：PUBLISH tick:2330、bidask:2330；SET last:2330（最新報價）
   ─▶ api 的 WebSocket 連線訂閱對應 channel ─▶ 瀏覽器
```

### 5.0 2026-10-17 修訂（依永豐金官方「使用限制」文件）
- 官方明文：盤中**不得輪詢** snapshots／ticks／kbars 當即時報價，違規會暫停 IP 與帳號使用權。
  因此**刪除**原設計的兩處輪詢：「行情中斷時改每 5 秒輪詢快照」「盤中每 10 秒抓全市場快照算排行」。
- 改為：個股用 `QuoteType.Quote` 訂閱（成交＋五檔一次取得，每檔只佔 1 個名額）；
  加權指數 `IX0001` 的指數推播本身含漲跌家數與累計成交金額，盤中寬度不必另外查詢；
  排行用 `api.scanners` **每分鐘最多一次**（3 種排行），遠低於限制。
- 行情中斷時前端顯示「尚未收到今日即時行情」並退回收盤資料，不做任何輪詢。
- 同一帳號最多 5 條連線（舊站、CLI、新站可並存，R2 解除）；訂閱推播不計入每日流量
  （近 30 日未用 API 成交的帳號每日查詢流量僅 500MB）。
- 推播的 `pct_chg` 單位是萬分之一，一律改用 `price_chg` 自算漲跌幅。

### 5.2 訂閱管理（永豐金上限 200 檔）
- 常駐訂閱：自選股、加權指數、櫃買指數、台指期近月。
- 動態訂閱：使用者正在看的個股頁；離開 5 分鐘後退訂。
- 超過 190 檔時，退訂最久沒人看的動態訂閱（保留 10 檔緩衝）。
- ~~市場總覽的全市場排行改由 worker 盤中每 10 秒抓一次全市場快照計算~~（違反官方規範，見 §5.0，改用每分鐘一次排行查詢）。

### 5.3 可靠性
- 只在交易時段（08:30–13:45；夜盤另議）維持連線，其餘時間登出，避免浪費每日 1,000 次登入額度。
- 斷線自動重連（指數退避，最多每 60 秒一次）；重連後補訂閱。
- ~~行情服務停擺時自動改成每 5 秒輪詢快照~~（違反官方規範，見 §5.0）。改為顯示「尚未收到今日即時行情」並退回收盤資料，頁面不空白。
- Uptime Kuma 監控 `/api/health`（含 quote 服務最後收到 tick 的時間）。

### 5.4 逐筆資料保存
home server 只剩 43 GB。逐筆**只保留在 redis 當日記憶體**，盤後由 worker 彙總成 1 分 K 寫進 PostgreSQL，原始逐筆不落地（需要長期保存時再另議存 NAS）。

---

## 6. 前端

| 用途 | 選擇 | 理由 |
|---|---|---|
| 框架 | React 19＋TypeScript＋Vite | 生態最大、後續任何 AI 都熟 |
| 路由 | React Router | 單頁應用，不需要伺服器渲染（不需 SEO） |
| 資料抓取 | TanStack Query | 快取、自動重抓、載入狀態一致處理 |
| K 線／走勢圖 | TradingView Lightweight Charts（Apache-2.0 授權） | 專業看盤級 K 線，效能好 |
| 其他圖表 | 純 SVG 元件（沿用設計稿畫法） | 法人柱狀、寬度條、營收柱等簡單圖不需要大型圖表庫 |
| 表格 | TanStack Table | 排序、欄寬、虛擬捲動 |
| 樣式 | CSS 變數設計 token＋CSS Modules | 兩套主題（終端機深色／報告淺色）由模式切換；不用大型 UI 套件，避免長得像通用後台 |
| 測試 | Vitest（元件）＋Playwright（端對端，含手機寬度） | |

**模式切換**：預設依台灣時間，08:30–13:45 交易日為盤中模式，其餘為盤後模式；使用者手動切換後存在瀏覽器（localStorage），直到隔天開盤前重置。

**設計 token**：由設計稿萃取（顏色、字體、間距、漲跌色），存成 `frontend/src/styles/tokens.css`，所有元件只能引用 token，不寫死色碼。

---

## 7. 部署與開發流程

- **部署**：在 home server 新增 git remote `home`，post-receive hook 執行 `docker compose -f deploy/compose.yml up -d --build`（與現在 NAS 的做法一致）。前端在 Docker 多階段建置（node 階段產出靜態檔 → nginx 階段），home server 效能足夠。
- **秘密**：永豐金、FinMind、AI 金鑰放 home server 上的 `deploy/.env`（不進 git，repo 只放 `.env.example`）。
- **CI**（GitHub Actions）：既有 pytest＋ruff 之外，加上 `backend/tests`、前端 `tsc` 型別檢查、Vitest、Playwright 冒煙測試。
- **監控**：Uptime Kuma 加一個監控項；log 用現有 Dozzle 看。
- **舊站**：開發期間 NAS 上的 Streamlit 不動（D5）。P6 切換時才停用。

---

## 8. 品質底線（每一期都要過）

1. `pytest`、`ruff`、前端型別檢查與測試全綠，CI 綠燈。
2. 頁面首次顯示 **< 2 秒**（盤後模式，Tailscale 連線下）；盤中逐筆延遲 **< 1 秒**（從 Shioaji callback 到畫面）。
3. 同一頁數字同一資料日期，並顯示該日期。
4. 每期抽查數字：至少一檔個股、一項大盤數字，與證交所官網或第二資料源比對一致。
5. Playwright 截圖驗收：桌機 1440 寬、手機 390 寬各一張。
6. 完成後更新 `PROJECT.md`（狀態、待辦、工作日誌）。

---

## 9. 風險與待確認事項

| # | 項目 | 影響 | 處理 |
|---|---|---|---|
| R1 | 官方文件確認模擬環境**可以**使用 `quote.subscribe`、snapshots 等行情 API；但推送的是否為真實行情**仍待開盤實測**（2026-10-19 起） | D4 可能做不到 | P2 開工第一件事：查官方文件＋實測。若不行，需改用正式環境登入（只用行情、不下單） |
| R2 | ~~同一帳號多處登入可能互相踢線~~ | — | **已解除**（2026-10-17 官方文件：同一身分證最多 5 條連線） |
| R3 | home server 是單點：它當機時新站全停（D5 之後舊站也已停用） | 無法看盤 | Uptime Kuma 通知；保留 NAS 舊映像可緊急復原 |
| R4 | `get_kbar()` 的 Shioaji／FinMind 切換日期**尚待使用者決定** | P3 個股頁卡關 | P3 開工前必須先決定 |
| R5 | 富途港美股需要 FutuOpenD；目前裝在 Windows 電腦上，home server 連不到 | 港美股 K 線 | P5 再決定：OpenD 有 Linux 版，可裝在 home server |
| R6 | home server 磁碟剩 43 GB | 資料增長 | 逐筆不落地（§5.4）；日線、1 分 K 量小 |
| R7 | D5 直接切換：新站完成前看不到成果、時間拉長 | 進度風險 | 每期在 home server 上都可實際打開驗收（只是還沒取代舊站） |

---

## 10. 分期計畫

| 期 | 內容 | 完成條件 |
|---|---|---|
| **P0 地基** ✅ 2026-10-16 | `backend/`、`frontend/`、`deploy/` 骨架；compose（web、api、redis）；`/api/health`；home server 部署 hook；CI 擴充；設計 token | Tailscale 下打開 `:8600` 看到空殼頁，健康檢查綠燈 |
| **P1 市場總覽（盤後）** ✅ 2026-10-17 | worker 預先計算；`/api/market/overview`；設計稿 B 實作；資料日期契約 | 首次顯示 < 2 秒；數字抽查一致 |
| **P2 即時行情** | 查證 R1、R2；quote 服務；WebSocket；市場總覽盤中版（設計稿 A）；斷線降級 | 盤中實測逐筆延遲 < 1 秒；拔掉 quote 服務時畫面降級不空白 |
| **P3 個股頁** | 先決定 R4；K 線、籌碼、基本面、盤後報告摘要句 | 2330 等三檔數字與第二來源一致 |
| **P4 自選股＋警示** | 自選股存 PostgreSQL；即時報價牆；警示（沿用 `alert_engine.py`） | 警示觸發實測 |
| **P5 其餘頁面** | 選股（抽出 `screener.py` 純函式）、全球市場、行事曆、AI 助理、投資組合 | 舊站功能清單逐項對照完成 |
| **P6 切換** | 舊站停用；`daily_job` 評估搬到 worker；文件更新 | 使用者確認可以停用舊站 |
