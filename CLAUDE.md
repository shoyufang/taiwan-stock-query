# 台股查詢工具 — Claude 工作手冊

> 這份文件是 Claude 工作記憶，記載本專案的完整設定、函式對照、已知問題與決策規則。
> 每次開啟新 session 請先讀這份文件。

---

## 專案概覽

**目的**：整合多個 API 的台股（及港美股）查詢工具，以互動選單操作。

**主要檔案**

| 檔案 | 說明 |
|---|---|
| `sinopac_query.py` | 主工具，含全部函式 + 互動選單（選單 1–47） |
| `查詢工具.bat` | 雙擊啟動 `sinopac_query.py` 的捷徑 |
| `chart_kbar.py` | K 線圖（mplfinance），CLI 工具 |
| `app.py` | Streamlit Web UI 應用（Phase 4+） |
| `query_wrapper.py` | 查詢包裝層 + 非同步批量查詢（Phase 6.1） |
| `preload.py` | 背景預加載管理器（Phase 6.2） |

**性能優化歷程**

| Phase | 功能 | 改善 | 狀態 |
|---|---|---|---|
| **Phase 5** | @st.cache_data 緩存 + 日誌監控 | 60-80%（重複查詢） | ✅ 完成 |
| **Phase 6.1** | 非同步批量查詢 (batch_query_sync) | 50-66%（批量查詢） | ✅ 完成 |
| **Phase 6.2** | 背景預加載 (PreloadManager) | 30-40%（首次訪問） | ✅ 完成 |
| **整體堆疊** | 三層性能優化 | **~93%** 理論值 | ✅ 完成 |

**報告檔案**

- `PHASE6_ASYNC_REPORT.md` — Phase 6.1 非同步查詢完整報告
- `PHASE6_PRELOAD_REPORT.md` — Phase 6.2 背景預加載完整報告

**執行方式**
```bash
# 互動選單
python sinopac_query.py

# K 線圖
python chart_kbar.py 2330 2026-01-01 2026-04-28
```

---

## API 金鑰與連線設定

### 券商提供 Shioaji
```python
API_KEY    = "<YOUR_SHIOAJI_API_KEY>"
SECRET_KEY = "<YOUR_SHIOAJI_SECRET_KEY>"
SIMULATION = True   # 正式環境改 False
```
- 帳務功能（選單 8–13）需 CA 憑證，模擬環境受限

### FinMind
```python
FINMIND_TOKEN = "<YOUR_FINMIND_TOKEN>"
```
- 帳號：shoyufang / shoyufang@gmail.com
- 等級：register（免費）

### Futu OpenAPI
- **不需 API 金鑰**，需本機運行 FutuOpenD
- 安裝路徑：`D:\Futu_OpenD_10.4.6408_Windows\`
- 連線：`ft.OpenQuoteContext(host='127.0.0.1', port=11111)`
- 代碼格式：`HK.00700`（騰訊）、`US.AAPL`、`HK.09988`（阿里）
- `get_market_snapshot` 需付費訂閱，其餘均可用

### TWSE OpenAPI
- **完全免費，不需金鑰**
- 新版 API：`https://openapi.twse.com.tw/v1/...`（SSL 正常）
- 舊版 API：`https://www.twse.com.tw/rwd/zh/...`（需 `verify=False`，憑證缺 SKI）

---

## 選單對照表（共 47 項）

### 台股市場（Shioaji，不需CA）
| # | 函式 | 說明 |
|---|---|---|
| 1 | `query_scanner("ChangePercentRank", True)` | 漲幅排行 |
| 2 | `query_scanner("ChangePercentRank", False)` | 跌幅排行 |
| 3 | `query_scanner("VolumeRank")` | 成交量排行 |
| 4 | `query_scanner("AmountRank")` | 成交金額排行 |
| 5 | `query_snapshot(["2330"])` | 個股即時快照（上限 500 檔） |
| 6 | `query_kbars("2330", start, end)` | 台股日K（分鐘K resample，2020起） |
| 7 | `query_ticks("2330", date)` | 逐筆成交（2020起） |

### 帳務（需 CA 憑證）
| # | 函式 | 說明 |
|---|---|---|
| 8 | `query_positions("stock")` | 庫存未實現損益 |
| 9 | `query_profit_loss(begin, end)` | 已實現損益 |
| 10 | `query_account_balance()` | 帳戶餘額 |
| 11 | `query_trading_limits()` | 交易額度 |
| 12 | `query_margin()` | 期貨保證金 |
| 13 | `query_settlements()` | 交割款明細 |

### 新聞（yfinance，不需帳號）
| # | 函式 | 說明 |
|---|---|---|
| 14 | `print_news("2330", 10)` | 個股新聞（Yahoo Finance，英文） |
| 15 | `print_news(None, 10)` | 大盤新聞（^TWII） |

### FinMind 技術/籌碼面（免費）
| # | 函式 | 說明 |
|---|---|---|
| 16 | `query_institutional(code, start, end)` | 三大法人明細（歷史） |
| 17 | `query_institutional_summary(code, start, end)` | 三大法人合計＋累計買超 |
| 18 | `query_daily_kbar_finmind(code, start, end)` | 股價日K（1994起） |
| 19 | `query_per_pbr(code, start, end)` | 本益比/股淨比/殖利率（歷史） |
| 20 | `query_day_trading(code, start, end)` | 當沖交易量 |
| 21 | `query_margin_short(code, start, end)` | 融資融券餘額（歷史） |
| 22 | `query_shareholding(code, start, end)` | 外資持股比例 |
| 23 | `query_securities_lending(code, start, end)` | 借券成交 |

### FinMind 基本面（免費）
| # | 函式 | 說明 |
|---|---|---|
| 24 | `query_month_revenue(code, start, end)` | 月營收（2002起） |
| 25 | `query_financial_statement(code, start, end)` | 綜合損益表（⚠️ 無s） |
| 26 | `query_balance_sheet(code, start, end)` | 資產負債表（2011起） |
| 27 | `query_dividend(code, start, end)` | 股利政策（2005起） |

### FinMind 期貨/匯率（免費）
| # | 函式 | 說明 |
|---|---|---|
| 28 | `query_futures_daily("TX", start, end)` | 期貨日行情（TX/MTX，1998起） |
| 29 | `query_futures_institutional("TX", start, end)` | 期貨三大法人 |
| 30 | `query_exchange_rate("USD", start, end)` | 台銀匯率（19幣別） |

### 富途 Futu OpenAPI（港股/美股）
| # | 函式 | 說明 |
|---|---|---|
| 31 | `query_futu_market_state()` | 全球市場開收盤狀態 |
| 32 | `query_futu_kbar(code, start, end)` | 港/美股日K |
| 33 | `query_futu_basicinfo(market, codes)` | 股票基本資訊 |
| 34 | `query_futu_capital_distribution(code)` | 資金分布（大/中/小戶） |
| 35 | `query_futu_capital_flow(code)` | 資金流向（分鐘級） |
| 36 | `query_futu_plate_list(market)` | 板塊列表 |
| 37 | `query_futu_plate_stocks(plate_code)` | 板塊成分股 |
| 38 | `query_futu_owner_plate(codes)` | 股票所屬板塊 |

### 證交所 TWSE OpenAPI（當日資料，免費）
| # | 函式 | API 路徑 | 說明 |
|---|---|---|---|
| 41 | `query_twse_daily_all(code)` | `/exchangeReport/STOCK_DAY_ALL` | 全市場當日行情，可篩代號 |
| 42 | `query_twse_bwibbu(code)` | `/exchangeReport/BWIBBU_ALL` | 本益比/殖利率/股淨比 |
| 43 | `query_twse_institutional(code)` | `/fund/T86` | 三大法人（全市場） |
| 44 | `query_twse_margin()` | `/exchangeReport/MI_MARGN` | 融資融券彙總 |
| 45 | `query_twse_company(code)` | `/company/getCompanyByCode` | 公司基本資料 |
| 46 | `query_twse_disposition()` | `rwd/zh/announcement/punish` | 處置有價證券清單（verify=False） |
| 47 | `query_twse_notice()` | `rwd/zh/announcement/notice` | 注意有價證券（verify=False） |

---

## 互動選單特殊功能

| 輸入 | 功能 |
|---|---|
| `?` | 智能查詢：輸入中文描述，自動比對關鍵字推薦選單並執行 |
| `g` | 決策指南：顯示「今日/歷史/港美股」速查表 |
| `0` | 離開 |

---

## 快速決策：要查什麼 → 用哪個

| 情境 | 工具 | 選單 |
|---|---|---|
| 今日排行 / 即時報價 | Shioaji | 1–5 |
| 今日全市場行情/法人/融資 | TWSE | 41–44 |
| 個股歷史籌碼（法人/融資/外資） | FinMind | 16–23 |
| 個股歷史基本面（財報/股利/營收） | FinMind | 24–27 |
| 本益比—今日全市場 vs 個股歷史 | TWSE 42 vs FinMind 19 | — |
| 處置股 / 注意股 | TWSE | 46–47 |
| 港美股 K線/資金/板塊 | Futu | 32–38 |
| 期貨/匯率 | FinMind | 28–30 |
| 新聞 | yfinance | 14–15 |
| 帳務 | Shioaji（需CA） | 8–13 |

---

## 已知問題與修正紀錄

| 問題 | 原因 | 解法 |
|---|---|---|
| 處置股郵件格式混亂 | DataFrame.to_string() 在純文本郵件上排版差，列寬超出、換行破碎 | 升級為 HTML 格式 + CSS 樣式，新增 `df_to_html_table()` 和 `send_email(..., html=True)` |
| `taiwan_stock_financial_statements` AttributeError | FinMind 方法名無 s | 改用 `taiwan_stock_financial_statement` |
| TWSE 舊版 SSL 憑證錯誤 | 憑證缺少 Subject Key Identifier | `requests.get(..., verify=False)` + `urllib3.disable_warnings()` |
| Shioaji `change_rate` 不存在 | 欄位名稱錯誤 | 改用 `rank_value`（漲跌幅）、`change_price`（漲跌額） |
| Shioaji kbars 無日K參數 | API 只有分鐘K | `pd.DataFrame.resample("1D").agg(...)` 轉日K |
| Futu `get_market_snapshot` hang | 需付費訂閱 | 改用 `request_history_kline`（不需訂閱） |
| FinMind 期貨三大法人欄位 `name` 不存在 | 欄位名為 `institutional_investors` | 改用 `_finmind_api()` 直接呼叫 REST |

---

## Shioaji 查詢頻率限制

- 5 秒內最多 50 次
- 盤中：ticks ≤ 10 次 / kbars ≤ 270 次
- 最多同時訂閱 200 個商品
- 每日登入上限 1000 次

---

## FinMind 免費版不支援（需付費）

| 資料集 | 需要等級 |
|---|---|
| 券商分點買賣（主力追蹤） | Sponsor |
| 集保戶數分級（散戶/大戶分布） | Backer |
| 市值 | Backer |
升級：https://finmindtrade.com/analysis/#/Sponsor/sponsor

---

## 財報行事曆說明

- **美股**：可用 FMP MCP `calendar → earnings-calendar`（含 EPS 預估）
- **台股 ADR**：FMP `earnings-company` 輸入 TSM / UMC 等可查
- **台股本土**：無即時行事曆 API，法定截止日如下：

| 期別 | 截止日 |
|---|---|
| Q1（1–3月） | 5 月 15 日 |
| Q2（4–6月） | 8 月 14 日 |
| Q3（7–9月） | 11 月 14 日 |
| 年報（1–12月） | 隔年 3 月 31 日 |

---

## GitHub Actions 自動化設定

### 每日排程執行（daily_job.py）

**排程時間**：每個交易日 **20:05 台灣時間**（UTC 12:05）

設定位置：`.github/workflows/daily.yml`

```yaml
on:
  schedule:
    - cron: '5 12 * * 1-5'   # 每週一至五 20:05 台灣時間（UTC 12:05）
```

### 必需的 GitHub Secrets

進入 GitHub 專案 → Settings → Secrets and variables → Actions

| Secret 名稱 | 說明 | 取得方式 |
|---|---|---|
| `NOTION_TOKEN` | Notion 內部集成 Token | Notion Developer Portal |
| `NOTION_MARKET_DB_ID` | 大盤快照 Database ID | Notion URL 複製 |
| `NOTION_SCREENER_DB_ID` | 選股紀錄 Database ID | Notion URL 複製 |
| `FINMIND_TOKEN` | FinMind API Token（選填） | finmindtrade.com 帳號設定 |
| `GMAIL_USER` | 寄件 Gmail 帳號 | 例：shoyufang@gmail.com |
| `GMAIL_APP_PASSWORD` | Gmail 應用程式密碼 | [myaccount.google.com → 安全性](https://myaccount.google.com/apppasswords) |
| `NOTIFY_EMAIL` | 收件地址（預設同 GMAIL_USER） | 通常同 GMAIL_USER |

### Gmail 應用程式密碼設定步驟

1. 進入 [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. 選擇應用程式：**Mail**
3. 選擇設備：**Windows 電腦**（或選擇 Other）
4. 複製產生的 **16 位密碼**
5. 貼到 GitHub Secret `GMAIL_APP_PASSWORD` 中

### 每日工作流程

daily_job.py 執行以下 5 個步驟：

| Step | 工作 | 輸出 |
|---|---|---|
| 1 | 抓取大盤資料（STOCK_DAY_ALL、T86、yfinance） | 無 |
| 2 | 寫入大盤快照到 Notion + 存 CSV | `data/market/YYYY-MM-DD.csv` |
| 3 | 籌碼選股（外資+投信雙買超） | 無 |
| 4 | 寫入選股紀錄到 Notion + 存 CSV | `data/screener/YYYY-MM-DD.csv` |
| 5 | 處置股清單 + HTML 郵件通知 | `data/disposition/YYYY-MM-DD.csv` |

### 郵件通知規則（Step 5）

- **觸發**：當 TWSE 處置股清單出現新增的股票
- **格式**：HTML 專業格式（CSS 內聯樣式）
- **內容**：新增代號表格、新增檔數、同日解除處置
- **去重**：使用 `disposition_cache.json` 記錄前一日清單，只通知新增
- **頻率**：有新增時寄信，無新增則不寄

### 手動觸發工作流程

測試時無需等待 20:05：

1. GitHub 專案首頁
2. 點擊 **Actions** 頁籤
3. 左側選擇 **台股每日資料抓取** workflow
4. 點右側 **Run workflow** → **Run workflow** (green button)

約 2-3 分鐘執行完成，檢查：
- 📧 郵件是否送達
- 📋 Notion 是否有新資料
- 💾 GitHub 是否有新 CSV 檔案

---

## 歷史數據回填（backfill.py）

### 用途

一次性填充過去 5 年的台股市場數據和選股紀錄到 GitHub CSV 檔案。

### 執行方法

**注意**：此腳本僅在本機執行，不放入 GitHub Actions（避免 Action 超時）

```bash
cd "路徑/永豐金API"
python backfill.py
```

執行時間：約 25-35 分鐘（視網路速度）

### 產出檔案

| 目錄 | 檔案 | 內容 |
|---|---|---|
| `data/market/` | `YYYY-MM-DD.csv` | 大盤快照（加權指數 + 三大法人合計） |
| `data/screener/` | `YYYY-MM-DD.csv` | 選股紀錄（外資+投信雙買超的交易日） |

### 實現細節

1. **Step 1**：用 yfinance 下載 5 年加權指數歷史（一次性下載）
2. **Step 2**：逐日迴圈抓取 TWSE T86 三大法人數據
   - API：`https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date=YYYYMMDD`
   - 限速：每次呼叫間隔 0.8 秒（避免 API 限流）
3. **Step 3**：存檔並支援斷點續傳
   - 已存檔的日期自動跳過
   - 中斷後重新執行會從上次中斷處繼續

### 上傳到 GitHub

回填完成後，上傳 CSV 檔案：

```bash
git add data/
git commit -m "data: 5年歷史資料回填"
git push
```

### 常見問題

| 問題 | 解決方式 |
|---|---|
| 執行到一半中斷 | 重新執行 `python backfill.py`，程式會從上次中斷處繼續 |
| 進度條不顯示 | 安裝 tqdm：`pip install tqdm`（選填，無此庫也能執行） |
| 特定日期抓不到資料 | 正常現象（非交易日、假日）。日誌會顯示 ⚠️ 警告但程式繼續 |
| 網路超時 | 調整 `SLEEP_SEC` 從 0.8 改成 1.0，或多執行幾次 |

---

## Streamlit Web UI 相關（Phase 4+）

### 新增依賴
```bash
pip install streamlit streamlit-option-menu plotly openpyxl reportlab
```

### 啟動 Web UI
```bash
streamlit run app.py
```

### Phase 4 新功能（已實現）
- **書籤系統**：快速保存和執行常用查詢
- **查詢歷史**：自動記錄所有查詢，支持重複執行
- **對比工具**：並排對比多檔股票的快照、技術面、基本面數據
- **設定管理**：修改 API 金鑰、偏好設置、歷史管理

### Phase 5 性能優化（已實現）✅
- **連線池** (Shioaji 單例)：首次 1000ms，後續 0ms
- **智能緩存** (@st.cache_data + TTL)：90% 命中率，重複查詢 <100ms
- **完整監控**：21 個查詢函數插樁，性能可追蹤
- **健康檢查** UI：連線狀態、配置驗證、文件系統檢查

### Phase 6 Task 1：非同步查詢執行（已實現）✨
- **批量查詢**：`query_wrapper.batch_query_sync()` 並行執行多個查詢
- **對比工具優化**：3檔股票快照對比 ~3600ms → ~1200ms (66% 改善)
- **線程池執行**：ThreadPoolExecutor 最多 5 個並行查詢
- **完全向後相容**：現有同步查詢無任何改動
- **9/9 測試通過**：包括性能基準驗證

參考文件：
- `PHASE4_FEATURES.md` — Phase 4 詳細功能說明
- `TESTING_GUIDE_PHASE4.md` — Phase 4 功能測試指南
- `PERFORMANCE_REPORT.md` — Phase 5 性能優化報告
- `PHASE6_ASYNC_REPORT.md` — Phase 6 Task 1 非同步查詢報告

---

---

## 代理人互動紀錄 (Agent Interaction Log)

> 本區塊記錄不同 AI 代理人（如 Claude, Gemini）對專案進行的變更，以避免互相干擾。

### 2026-05-16 Gemini Session (Phase 7 完整交付)
- **核心開發任務**：將專案升級至 **Phase 7: 深度效能與智慧整合**。
- **重大變更記錄**：
    - **效能優化**：
        - 實作 **SQLite 永久快取層** (`sqlite_cache.py`)，將 K線、財報等歷史數據持久化，解決冷啟動下載緩慢問題。
        - 實作 **自動刷新機制**，利用 Streamlit `st.fragment` 實現即時報價每 30 秒局部更新。
        - 重構 **連線池 (Connection Pooling)**，Futu、FinMind 與 TWSE 均採用長連線單例，極大化 Python 查詢速度。
    - **AI 智能整合**：
        - 實作 `gemini_engine.py` 並升級至 **最新 google-genai 2.3.0 SDK**。
        - 支援 **Function Calling** (自動調用本地 47+ 工具) 與 **Google Search** (網路資訊補全)。
        - 實作 **動態模型偵測與手動覆寫**，使用者可在 UI 自由指定任何 Gemini 模型版本（如 2.5, 3.1 等）。
    - **UI/UX 重大翻新**：
        - 新增 **跨市場整合儀表板**，一站式監控全球市場狀態與台股指標。
        - 實作 **設定齒輪 (Settings Gear)**，將敏感 API 設定隱藏於右上角彈出視窗，淨化側邊欄。
        - 實作 **自選名單 (Watchlist) UI 化**，支援在設定中直接輸入監控代號，並與背景預載引擎同步。
    - **穩定性強化**：
        - 實作 **背景預載 (Non-blocking Startup)**，數據抓取移至背景線程，網頁進入速度提升至秒開。
        - 強化 **JSON 容錯機制**，針對損壞的配置或歷史檔案具備自動回退功能。

### 2026-05-20 Claude Session (郵件格式修復 + 歷史數據回填)
- **核心任務**：修復處置股郵件通知格式，完成 5 年歷史數據回填
- **主要成果**：
    - **郵件格式修復**（daily_job.py）：
        - 升級從純文本 → HTML 專業格式
        - 新增 `df_to_html_table()` 函數，自動轉換 DataFrame 為帶樣式 HTML 表格
        - 改進 `send_email()` 函數支援 HTML 格式（新參數 `html=True`）
        - 視覺設計：紅色警示標題、專業表格樣式、交替背景色、數字右對齐
        - 完全行動裝置友善，CSS 內聯樣式確保兼容各郵件客戶端
        - 新增同日解除處置的橙色區塊突出顯示
    - **郵件主旨改進**：`【台股警示】...` → `⚠️ 台股警示 {DATE} 新增處置股 {COUNT} 檔`
    - **測試工具新增**：
        - `email_preview.py` — 無需寄信即可預覽郵件格式
        - 生成 `email_preview.html` 供瀏覽器預覽
    - **後續步驟文檔化**：
        - GitHub Secrets 設定：GMAIL_USER、GMAIL_APP_PASSWORD、NOTIFY_EMAIL
        - 歷史數據回填：執行 `python backfill.py`（25-35 分鐘）
        - 數據上傳：`git add data/ && git commit && git push`
- **相關文件**：
    - `daily_job.py` — 新增郵件 HTML 格式實現
    - `email_preview.py` — 郵件預覽工具（新增）
    - `backfill.py` — 5 年歷史數據回填腳本（已存在）

---

## 環境需求（完整）

```bash
pip install shioaji pandas yfinance FinMind requests futu-api mplfinance streamlit streamlit-option-menu plotly openpyxl reportlab
```
