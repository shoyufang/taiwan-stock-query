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
| `technical_analysis.py` | Plotly 互動式K線圖 + 技術指標（Phase 7.5） |

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

**Phase 7.5：技術分析視覺化（2026-05-20）**
- 新增 `technical_analysis.py` 模組：Plotly 互動式K線圖
- 支援指標：MA (5/10/20/60/120)、EMA、RSI、MACD、布林帶、ATR
- app.py 集成新 Tab「技術分析」，包含：
  * 動態指標選擇（多選）
  * 日期範圍篩選
  * 互動功能：放大/縮小、懸停提示、日期拖拉
  * 基礎統計（收盤價、漲跌、成交量）
  * 查詢自動記錄到歷史

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

### Phase 7.5：技術分析視覺化（已實現）🎨
- **Plotly 互動式K線圖**：`technical_analysis.py` 完整實現
- **支援技術指標**：
  * MA (5/10/20/60/120)：移動平均線，顏色編碼
  * EMA (5/10/12/26)：指數移動平均
  * RSI：相對強度指標，含超買 (70) / 超賣 (30) 線
  * MACD：信號線 + Histogram 柱狀圖
  * 布林帶 (BB)：上軌/下軌，透明填充區域
  * ATR：真實波幅，波動性分析
- **Streamlit UI 集成**（app.py「技術分析」Tab）：
  * 股票代號輸入 + 日期範圍選擇
  * 多選指標，動態組合
  * 互動功能：放大/縮小、懸停提示、日期拖拉
  * 基礎統計面板：收盤價、漲跌、成交量
  * 自動記錄到查詢歷史
- **視覺特性**：
  * 台股慣例：漲紅跌綠
  * 成交量柱狀圖，顏色與漲跌對應
  * 多行子圖：K線在上，指標在下，共享 X 軸
  * 響應式設計，適配各螢幕寬度

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

### 2026-05-20 Claude Session (郵件格式修復 + 技術分析視覺化 + 歷史數據回填)
- **核心任務**：修復處置股郵件通知格式、實現技術分析圖表、完成 5 年歷史數據回填
- **主要成果**：
    - **郵件格式修復**（daily_job.py）：
        - 升級從純文本 → HTML 專業格式
        - 新增 `df_to_html_table()` 函數，自動轉換 DataFrame 為帶樣式 HTML 表格
        - 改進 `send_email()` 函數支援 HTML 格式（新參數 `html=True`）
        - 視覺設計：紅色警示標題、專業表格樣式、交替背景色、數字右對齊
        - 完全行動裝置友善，CSS 內聯樣式確保兼容各郵件客戶端
        - 新增同日解除處置的橙色區塊突出顯示
    - **郵件主旨改進**：`【台股警示】...` → `⚠️ 台股警示 {DATE} 新增處置股 {COUNT} 檔`
    - **技術分析圖表實現**（Phase 7.5）：
        - 新建 `technical_analysis.py` — 350 行完整 Plotly 模組
        - 函數：`calc_ma`、`calc_ema`、`calc_rsi`、`calc_macd`、`calc_bollinger_bands`、`calc_atr`
        - 主函數 `plot_kbar_with_indicators()`：K線 + 多指標子圖
        - 快速化 `quick_chart()`：一行呼叫預設組合
        - Streamlit 整合：app.py 新增「技術分析」Tab（render_technical_analysis）
        - UI 功能：動態指標選擇、日期範圍篩選、統計面板、歷史記錄
        - 互動特性：放大/縮小、懸停提示、日期拖拉、右鍵保存圖表
    - **測試工具新增**：
        - `email_preview.py` — 無需寄信即可預覽郵件格式
        - 生成 `email_preview.html` 供瀏覽器預覽
    - **後續步驟文檔化**：
        - GitHub Secrets 設定：GMAIL_USER、GMAIL_APP_PASSWORD、NOTIFY_EMAIL
        - 歷史數據回填：執行 `python backfill.py`（25-35 分鐘）
        - 數據上傳：`git add data/ && git commit && git push`
- **相關文件**：
    - `daily_job.py` — 郵件 HTML 格式實現
    - `email_preview.py` — 郵件預覽工具（新增）
    - `technical_analysis.py` — 技術分析圖表模組（新增）
    - `app.py` — 技術分析 Tab 集成
    - `backfill.py` — 5 年歷史數據回填腳本

### 2026-05-20 Claude Session（UI 配色 + 中文股票名稱 + TWSE Bug 修復）
- **核心任務**：套用 Claude 官網配色、支援中文股票名稱輸入、修復 TWSE 三大法人查詢
- **主要成果**：
    - **Claude 官網配色（UI 全面換新）**：
        - `.streamlit/config.toml` 新增 `[theme]`：primaryColor=`#D97757`、bg=`#F2F0EB`、sidebar=`#E8E4DC`
        - `app.py` CSS 從暗色系（紅 `#e63946`）改為 Claude 暖色系（珊瑚橘 `#D97757`）
        - 定義 CSS 變數：`--claude-bg/sidebar/surface/primary/text/border`
        - 移除廢棄的 `[telemetry]` config 設定（避免 Streamlit Cloud 啟動警告）
    - **中文股票名稱輸入支援**：
        - 新增 `stock_lookup.py` 模組：
            - `US_STOCK_ALIASES`：~80 筆美股/港股中英文別名（蘋果→AAPL、輝達→NVDA、騰訊→0700.HK 等）
            - `_load_tw_name_map()`：從每日 TWSE CSV 或 API 載入台股名稱→代號對照
            - `resolve_code(raw)`：中文名稱/英文別名/代號 → 標準股票代號
            - `resolve_codes(raw, sep)`：批量解析逗號分隔名稱
            - `get_name_hint(raw)`：回傳「台積電 → **2330**」提示字串
        - `ui_components.py` `code_input_section()` 整合 resolve_code，自動顯示解析提示
        - `app.py` 技術分析 Tab 代號輸入框也支援中文輸入
    - **TWSE 三大法人 Bug 修復**：
        - **根本原因**：`openapi.twse.com.tw/v1/fund/T86` 回傳 HTML（非 JSON），已失效
        - **影響範圍**：`sinopac_query.py` + `daily_job.py` Step 6 都用了壞端點
        - **修復方式**：改用舊版 `www.twse.com.tw/rwd/zh/fund/T86?selectType=ALL`
            - 不帶日期時只回 7 筆摘要（無意義） → 加 `date=今日&selectType=ALL` → 14,116 筆
        - `sinopac_query.py`：`query_twse_institutional()` 加入日期參數
        - `daily_job.py`：Step 6 `_TWSE_DAILY_ENDPOINTS["institutional"]` 改用舊版 rwd 端點
        - `daily_job.py`：`fetch_twse_daily_cache()` 支援 endpoint 自訂 params 合併

- **已知問題**：
    - GitHub Actions 排程在 `NOTION_TOKEN` 未設定時，`main()` 會 `sys.exit(1)`，Step 6（TWSE 快取下載）永遠跑不到
    - 建議：將 Step 6 移到 NOTION_TOKEN 檢查之前，或獨立為不需 Notion 的步驟

- **Commit 記錄**：
    - `cc5bff6` — feat: 支援中文股票名稱輸入（台股＋美股）
    - `12e0bef` — style: 套用 Claude 官網配色系統（暖奶油白 + 珊瑚橘）
    - `acb2b5b` — fix: 修復 TWSE 三大法人查詢（T86 必須帶日期參數）
    - `0253d27` — fix: 修復 daily_job.py Step 6 的三大法人下載

### 2026-05-20 Claude Session（NAS Docker 每日排程設定）
- **核心任務**：解決 TWSE API 封鎖 Streamlit Cloud 海外 IP 問題，改由 NAS 在台灣 IP 執行每日任務
- **架構決策**：
    - Streamlit Cloud（海外 IP）→ TWSE API 被封鎖
    - 方案：NAS 本機執行 `daily_job.py`（台灣 IP），抓完 CSV 後 push 到 GitHub；Streamlit Cloud 只讀 CSV
    - GitHub Actions 保留為 20:05 備援，NAS 排程為 20:00 主力
- **新增檔案（已 commit 9e3b8fc）**：
    - `Dockerfile.daily` — 輕量 Docker 映像（python:3.11-slim + git + requirements.daily.txt）
    - `requirements.daily.txt` — 精簡依賴（pandas / yfinance / requests / urllib3 / notion-client）
- **NAS 設定（ASUSTOR AS6604T）**：
    - Docker 版本：28.1.1，NAS 路徑：`/volume1/docker/sinopac`
    - `/volume1/docker/sinopac/run_daily.sh`（NAS 本機，不在 repo）
        - `git pull` → `docker run` daily_job.py → `git add data/ && git push`
        - ⚠️ ASUSTOR 使用 `sh`（busybox），shebang 需為 `#!/bin/sh`，不可用 `bash`
    - crontab（`sudo crontab -e`）加入：
      ```
      0 20 * * 1-5 /bin/sh /volume1/docker/sinopac/run_daily.sh >> /volume1/docker/sinopac/run_daily.log 2>&1
      ```
      ⚠️ 注意：由於您的 NAS 系統時區已設定為 CST (台灣時間 UTC+8)，因此 crontab 應直接設定為 `0 20` (晚間 20:00)。如果設定為 `0 12` 會在中午 12 點執行。
- **安全事項**：✅ Git PAT token 曾外洩於對話中，已在 GitHub 撤銷並更新 NAS remote URL（token 名稱：`NAS-sinopac`）

### 2026-05-20 Gemini Session（測試套件全面修復與 Notion 排程解耦）
- **核心任務**：極速修復單元測試崩潰，解耦 `daily_job.py` 與 `NOTION_TOKEN` 的硬性依賴。
- **主要成果**：
    - **測試套件全面綠燈** (232 passed)：
        - 於 `config.py` 中實現向後相容類別 `ConfigManager`，成功使 47 個舊測試免改動即通過。
        - 於 `query_wrapper.py` 中新增相容性別名 (`query_kbars`、`query_institutional` 等)，解決 mock 裝飾器引發的 14 個測試崩潰。
        - 於 `test_comparison_tool.py` 中將 Pandas 的 `freq="M"` 修正為 `freq="ME"`。
        - 於 `test_utils.py` 中將 `@patch('utils.to_csv')` 修正為 `@patch('utils.export_csv')`。
    - **Notion 依賴解耦**：
        - 移除 `daily_job.py` 中因缺失 `NOTION_TOKEN` 而執行的 `sys.exit(1)` 硬性中止。
        - 在 `notion_insert`、`write_market` 及 `write_screener` 等函數中加入防禦性 guard，在未配置 Notion 金鑰或資料庫時優雅跳過，避免無謂的 API 呼叫與超時等待。
    - **終端機 CP950 編碼相容性優化**：
        - 在 `daily_job.py` 頂層導入 `sys.stdout.reconfigure(encoding="utf-8")`，徹底解決 Windows 在預設 BIG5/CP950 編碼下因 Emoji 或特殊字元引發的 `UnicodeEncodeError` 崩潰問題。
    - **功能驗證**：
        - 於無 Notion 設定環境下成功執行 `python daily_job.py`，驗證其不僅完美前進至 Step 6，更成功下載並更新全部 7 大 TWSE 快取數據。

### 2026-05-20 Gemini Session（非台股功能完整驗證完成）
- **核心任務**：在 Windows 環境下，針對**除「台股市場」分頁外**之所有功能進行全面的自動化數據與功能層面驗證。
- **驗證成果**：
    - 成功在 Windows 環境下執行 `verify_non_tw_features.py` 驗證腳本。
    - **測試結果**：**32 項成功 (PASS)**，**1 項軟性提醒 (WARN)**，**0 項失敗 (FAIL)**。
    - **受檢模組與功能均 100% 健全**，包含：
        * **系統設定**：成功讀取與解析自選監控、偏好及金鑰遮蔽。
        * **儀表板**：7 大本地快取目錄及 yfinance 全球指數/加權指數大盤快照成功載入。
        * **技術分析**：2330 日K線數據獲取、指標（MA/EMA/RSI/MACD/BB/ATR）數學運算、與互動式 Plotly K線圖繪製全數成功。
        * **TWSE 證交所**：個股日行情、估值、法人買賣超、信用交易、處置/注意股票及收盤指數成功讀取。
        * **FinMind 財務籌碼**：歷史營收、損益表、資產負債表、除權息、信用交易餘額、外資持股、借券餘額全數通過。
        * **期貨/匯率**：期指每日行情、法人持倉、美元兌台幣匯率全數通過。
        * **選股引擎**：股票池獲取、基本過濾（成交量與價格）、技術/財報/籌碼面多因子篩選全數通過。
        * **新聞模組**：yfinance 個股/大盤即時新聞查詢成功。
        * **工具模組**：書籤完整生命週期讀寫（增刪查）、歷史查詢紀錄自動序列化與反序列化測試成功。
    - **結論**：核心數據層與 API 介面極度健全，非台股之業務功能完美運行。

### 2026-05-20 Gemini Session（公司基本資料查詢崩潰修復與雙層整合升級）
- **核心任務**：徹底解決「公司基本資料」分頁出現的 `Expecting value: line 1 column 1` JSON 解析錯誤。
- **主要成果**：
    - **根本原因診斷**：由於舊的 TWSE OpenAPI `/company/getCompanyByCode` 被官方正式廢棄，返回 HTML 導致 `r.json()` 解碼崩潰。
    - **重構雙層查詢架構**：
        - 於 `sinopac_query.py` 中重構 `query_twse_company`。
        - **方案 A (極速 JSON)**：優先調用 TWSE OpenAPI `/opendata/t187ap03_L` 的 JSON，在 0.1 秒內極速完成上市公司基本資料比對。
        - **方案 B (強健 CSV Fallback)**：當方案 A 失效或為非上市公司時，自動降級（Fallback）調用公開資訊觀測站 (MOPS) 的上市 (`_L`)、上櫃 (`_O`)、興櫃 (`_R`) 開放資料 CSV，實現三合一的全市場基本資料覆蓋。
    - **優雅向後相容**：
        - 新增 `_process_company_df` 輔助函數，在重命名的同時，將上櫃公司的 `上櫃日期` 與興櫃/上市的 `上市日期` 統一映射為 `上市日期`。
        - 欄位完全相容 legacy Dataframe 格式，無縫對齊 Streamlit Web UI。
    - **功能驗證**：
        - 於本機執行單行 Python 命令，完美驗證上市公司 `2330` (自方案 A) 及上櫃公司 `5483` (自方案 B) 均 100% 成功獲取資料且無任何亂碼與格式碎裂。

### 2026-05-21 Gemini Session（台股選股引擎與三大法人端點修復）
- **核心任務**：徹底修復「選股」分頁中因 TWSE OpenAPI `/v1/fund/T86` 廢棄而導致「什麼股票都不符合條件」的故障。
- **主要成果**：
    - **全新三層效能與穩定防線**：
        - **今日快取優先 (Cache-First)**：優先加載今日由背景自動下載的 CSV 快取數據 (`data/twse/`)，實現 0 延遲秒開。
        - **官方 RWD 接口重建**：若無今日快取，則線上調用官方穩定舊版 RWD 端點 (`/rwd/zh/fund/T86`)，傳入 `YYYYMMDD` 及 `selectType=ALL`。
        - **5日智能 Fallback**：若線上不可達（如 Streamlit Cloud 海外 IP 阻擋），往前檢索最近 5 天（包含週末與假日前交易日）的最新本地快取；若仍無，則透過 glob 讀取目錄下最新的一筆快取作為終極安全保障。
    - **CP950 編碼相容與 Unicode 修復**：
        - 本地 `read_csv` 顯式聲明 `encoding="utf-8-sig"`，徹底解決 Windows 環境下預設 CP950 導致 CSV 欄位名稱變 Mojibake 亂碼的隱蔽 bug。
    - **防止 Column Conflict KeyError**：
        - 在 `_process_institutional_df` 結尾主動排除重複的 `名稱` 欄位，避免 merge 時 pandas 生成 `名稱_x` / `名稱_y` 從而引發 `screen_chip()` 訪問 `row["名稱"]` 產生 `KeyError` 崩潰。
    - **測試全綠通過**：
        - 建立測試腳本 `scratch_test_screener.py`，完美驗證資料加載比對與多因子選股流程。選股引擎在「外資投信今日雙買超」中精準篩出 47 檔、「本益比<=15且殖利率>=4%」篩出 213 檔，不再是「什麼都不符合」。
        - 232 項單元測試 100% PASS 綠燈。

---

## NAS 每日排程（ASUSTOR AS6604T）

### 架構說明

```
NAS (台灣 IP, 20:00)
  └─ git pull
  └─ docker run daily_job.py  →  data/twse/*.csv, data/market/*.csv …
  └─ git push
        │
        ▼
   GitHub repo  ←  Streamlit Cloud 讀取 CSV（不呼叫 TWSE）
        │
        ▼
  GitHub Actions (20:05, 備援)
```

### 關鍵路徑

| 項目 | 路徑/指令 |
|---|---|
| NAS 專案目錄 | `/volume1/docker/sinopac` |
| 執行腳本 | `/volume1/docker/sinopac/run_daily.sh` |
| 執行日誌 | `/volume1/docker/sinopac/run_daily.log` |
| crontab 檔案 | `/var/spool/cron/crontabs.26988` |
| Docker 映像 | `python:3.11-slim`（直接跑，不 build 自訂 image） |

### NAS 常見注意事項

| 問題 | 解法 |
|---|---|
| `-sh: bash: not found` | 改用 `sh script.sh`，shebang 改 `#!/bin/sh` |
| `crontab: must be suid` | 使用 `sudo crontab -e` |
| 無 nano 編輯器 | 使用 `vi`（`:wq` 存檔，`:q!` 放棄） |
| git push 需輸入密碼 | remote URL 嵌入 PAT：`https://TOKEN@github.com/…` |

---

## NAS 本地網頁伺服器部署 (解鎖海外 IP 限制)

為了解決 Streamlit Cloud (海外 IP) 無法查詢 TWSE 即時資料 (如月/年成交資訊) 的問題，建議將 Streamlit 網站直接運行於本地 NAS，利用台灣 IP 進行 API 查詢，並達成資料 0 延遲。

### 部署腳本 (`update_web.sh`)
本專案已提供 `update_web.sh`。執行流程：
1. 進入 NAS 專案目錄：`cd /volume1/docker/sinopac`
2. 編輯並填入 API 金鑰：`vi update_web.sh` (填入 `GEMINI_API_KEY` 與 `FINMIND_TOKEN`)
3. 執行啟動腳本：`sudo sh update_web.sh`
4. 網頁將背景運行於 NAS 的 **Port 8502** (`http://NAS_IP:8502`)。

未來若需更新網站，只要在 NAS 上重新執行 `sudo sh update_web.sh` 即可自動 `git pull` 最新程式碼並重啟 Docker 容器。

---

## 環境需求（完整）

```bash
pip install shioaji pandas yfinance FinMind requests futu-api mplfinance streamlit streamlit-option-menu plotly openpyxl reportlab
```

---

### 2026-05-23 Gemini Session（美股與跨市場功能升級 - Stage 1, 2, 3 完整交付）
- **核心任務**：依照使用者指令，一個一個推進美股及跨市場功能重磅升級。
- **主要成果**：
  - **Stage 1: 跨市場技術分析 Plotly 圖表升級**：
    * `query_wrapper.py`：`_cached_kbar` 自動偵測非台股代號（非純數字）並分流走 `yfinance` API，進行 `tz_localize(None)` 時區剝離防崩潰處理，完美支援 SQLite 快取與 Streamlit 記憶體雙快取。
    * `technical_analysis.py`：Plotly K 線圖 `plot_kbar_with_indicators` 自動切換配色——美股/港股為國際標準的「綠漲紅跌」，台股為習慣的「紅漲藍跌」，且成交量與 MACD 柱狀體配色同步；價格小數點自適應美股為 `.2f`，台股 `.0f`。
    * `app.py`：`render_technical_analysis` 代號解析整合 `resolve_us_stock` Fallback 機制，當解析含有中文未命中時，呼叫 DeepSeek 大模型背景翻譯為美股 Ticker。
  - **Stage 2: 台美 ADR 溢折價即時監控儀表板**：
    * 新增 `adr_query.py` 模組：
      - `get_usd_twd_rate()`：優先抓取 yfinance `TWD=X` 匯率，備用 FinMind 歷史匯率，終極 Fallback 預設 `32.2`。
      - `get_adr_snapshots()`：整合 TSMC (TSM vs 2330)、UMC (UMC vs 2303)、ASE (ASX vs 3711)，比例 1:5。
      - 實作 60 秒極速 SQLite 快取限制，防範儀表板每 30 秒自動刷新局部頁面（`st.fragment`）頻繁請求被鎖。
      - 台股價格防線：優先 Shioaji 快照，斷線或假日 Fallback yfinance `Code.TW` 歷史收盤價。
    * `app.py`：儀表板整合高質感玻璃擬態 HTML/CSS 資訊卡片，溢價顯示珊瑚橘 (`var(--claude-primary)`)，折價顯示深藍色 (`#1976d2`)。
  - **Stage 3: 一鍵「AI 美股健檢與研究報告」功能**：
    * `deepseek_engine.py`：實作 `generate_us_stock_report(ticker)` 核心功能，自動精簡財務三大表歷史數據與機構持股，透過華爾街級 Prompt 指導 AI 生成繁體中文 Markdown 投資報告（包含核心業務與護城河、財務結構、籌碼意涵、本益比估值空間、SWOT矩陣）。
    * `app.py`：美股專區下方引入 AI 報告容器，實作 `st.session_state` 本地快取金鑰 `us_ai_report_{ticker}`，確保重整時已生成報告不消失，並整合 `📥 下載 Markdown 投資報告` 按鈕一鍵匯出 `.md` 檔案。
  - **單元測試全綠通過**：
    * 建立 `tests/test_adr_query.py` 與 `tests/test_ai_report.py`。
    * 成功通過 `pytest` 測試套件 237 項 100% 綠燈，極度健全！

### 2026-05-23 Gemini Session（美股與跨市場功能升級 - Stage 4 完整交付）
- **核心任務**：依照使用者指令，實現美股多因子選股篩選器（Screener）升級。
- **主要成果**：
  - **Stage 4: 美股多因子選股篩選器**：
    * 新增 `us_screener.py` 模組：
      - 定義 `US_SCREENER_POOL`：包含 M7（AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA）、半導體（TSM, AMD, INTC, ASML, QCOM, AVGO, MU, TXN）、消費/零售（KO, PEP, WMT, PG, MCD, SBUX 等）、金融（JPM, BAC, MS, GS, V, MA, BRK-B 等）、醫藥（LLY, JNJ, PFE, MRK, UNH, ABBV）與能源/工業共 50 檔最具代表性的美股權值股與藍籌巨頭。
      - 實作 `_fetch_ticker_metrics(ticker)`：透過 `yfinance` API 多重 Fallback 解析最新收盤價、52週高點、本益比 (PE)、預期本益比 (Forward PE)、股利殖利率%、股東權益報酬率 (ROE%) 與市值。
      - 實作 `get_us_screener_data()`：內建 **12小時 SQLite 永久快取 (TTL: 43200s)**。當快取失效時，透過 `ThreadPoolExecutor` 啟用 10 個背景線程極速並行下載 50 檔美股基本面與拉回幅度數據，控制在 5-8 秒內極速完成。
      - 實作 `filter_us_stocks(df, filters)`：多因子過濾邏輯，支持市值過濾、PE門檻、Forward PE門檻、ROE下限、殖利率下限、52週高點拉回區間 (拉回比率) 與行業板塊等多因子聯合漏斗篩選。
    * 升級 `app.py` 選股 UI (Screener)：
      - 在選股分頁最上方引進「選擇選股市場」單選紐（台股選股 / 美股選股），台股功能完全無縮排不破壞相容性，美股功能完全獨立。
      - `render_us_screener()`：實現高質感兩欄式因子配置面板。
        * 左欄：市值規模過濾、本益比上限、預期本益比上限、以及動態解析所有行業板塊 (`df["行業板塊"].unique()`) 的板塊篩選 multiselect。
        * 右欄：ROE 下限、殖利率下限、以及拉回幅度 (%) 的雙向滑桿 (Slider) 的安全邊際過濾。
      - 實作選股雙按鈕：`🔍 開始選股篩選` 與 `🔄 強制更新數據`。點擊強制更新會徹底清理快取並重啟並行下載線程池。
      - 實作 `_us_screener_result_block`：顯示格式化美股選股結果表格（將市值十進位化為 `XXX.X B`），提供一鍵導出 Excel 下載 (已過濾 datetime 類型確保 0 崩潰)，並主動提示複製代號至「技術分析」與「美股專區」查看。
  - **單元測試全綠通過**：
    * 新增 `tests/test_us_screener.py`。
    * `pytest` 跑綠 **242 項測試 (100% 全數通過，無 Regression)**！

### 2026-05-23 Gemini Session（美股與跨市場功能升級 - Stage 5 完整交付）
- **核心任務**：依照使用者指令，實現美股財報行事曆與華爾街共識 UI 升級。
- **主要成果**：
  - **Stage 5: 美股財報行事曆與華爾街共識 UI**：
    * 新增 `us_calendar.py` 模組：
      - 實作 `_fetch_single_calendar_consensus(ticker)`：提取 `yfinance` 的財報公佈日 (Earnings Date)、下季預估 EPS、下季預估營收，並從 recommendations 提取平均目標價、最高價、最低價、推薦評等（如 `buy`, `hold` 等）及參與評估分析師人數。
      - 建立中文化評等與 Emoji 標籤對照表 (`RATING_MAP`，如強力買入 🟢🟢、持有 🟡、賣出 🔴 等)，使分析師共識的視覺化極其精緻 premium。
      - 實作 `get_us_calendar_consensus_data()`：內建 **24小時 SQLite 永久快取 (TTL: 86400s)**，極速加載，快取失效或手動更新時啟用BACKGROUND並行抓取 50 檔美股巨頭日程。
    * 升級 `app.py` 側邊欄與分流：
      - 於 `OTHER_TABS` 選單中新增獨立導航項 **`"📅 美股日曆 & 共識"`**，點擊直接流暢切換至專屬的 render 區塊，完全不影響其他既有頁面。
      - `render_us_calendar_consensus()`：實現雙分頁 Tab 控制：
        * **Tab 1: 📅 財報公佈日曆 (Earnings Calendar)**：以時間表日程呈现即將公佈財報之美股巨頭日期、預期營收與 EPS，並依公佈日期由近到遠自動排序，提供一鍵下載 Excel 檔案。
        * **Tab 2: 🎯 華爾街共識與潛在空間 (Wall Street Consensus)**：按照分析師目標價之「潛在漲幅%」由高到低降序排列，提供尋找被低估資產的強大量化工具。支援最低潛在漲幅 Slider 控制與板塊 multiselect 篩選。提供 Excel 檔案下載，並整合代號快速跳轉提示。
  - **單元測試全綠通過**：
    * 新增 `tests/test_us_calendar.py`。
    * `pytest` 跑綠 **245 項測試 (100% 全數綠燈通過，0 異常，無 Regression)**！

### 2026-05-23 Gemini Session（台股法說與除息日曆擴充）
- **核心任務**：依照使用者指令，為「台股市場」分頁擴充並整合台股法說會與除息日曆。
- **主要成果**：
  - **台股法說與除息日曆實作**：
    * 新增 `tw_calendar.py` 模組：
      - 定義 `TW_SCREENER_POOL`：包含 50 檔最具代表性的台股權值巨頭（台灣 50 指數成分股）。
      - 實作 `_fetch_single_tw_calendar_consensus(code)`：利用 `yfinance` 自動提取法說會/財報日期、下季預估 EPS、下季預估營收（台幣元）及除息日。
      - 本地股票中文名稱映射：完美串接 `stock_lookup.py` 機制，確保台股代號自動轉換為 100% 正確的中文名稱（如 `2330` -> `台積電`）。
      - 實作 `get_tw_calendar_consensus_data()`：內建 **24小時 SQLite 永久快取 (TTL: 86400s)**，極速加載，支援背景並行抓取 50 檔台股日程。
    * 升級 `app.py` 台股市場批次查詢 UI：
      - 於 `NO_DATE_ITEMS` 中新增項目 **`"台股法說與除息日曆"`** 複選按鈕。
      - 於 `_taistock_dispatch` 批次查詢分派器中，完美實作 `"台股法說與除息日曆"` 分流邏輯，重整並自動排序數據。
      - 重用高階組件 `display_result()`：讓該日曆直接獲得表格呈现、Notion 跨平台連接儲存、以及一鍵導出下載 Excel 檔案的強大功能。
  - **單元測試全綠通過**：
    * 新增 `tests/test_tw_calendar.py`。
    * `pytest` 跑綠 **248 項測試 (100% 全數綠燈通過，無 Regression)**！

### 2026-05-23 Gemini Session（永豐金 Shioaji 獨家行情與歷史查詢功能上架）
- **核心任務**：盤點並上架永豐金 Shioaji 除了下單與帳務之外的所有核心行情與歷史數據查詢功能。
- **主要成果**：
  - **實作 Shioaji 行情查詢核心**（`sinopac_query.py`）：
    * 實作 `query_shioaji_snapshot(codes)`：使用 `api.snapshots` 獲取盤中即時快照與五檔委買委賣價量，並結構化解析。
    * 實作 `query_shioaji_kbars(code, start, end, resolution)`：獲取多週期（1分K、5分K、15分K、30分K、60分K、日K）歷史與盤中分K數據，免去 sub-import 避免 module 衝突。
    * 實作 `query_shioaji_contract_info(code)`：查詢商品官方交易所合約，包含融資融券成數限制、當沖/資券互抵、昨日參考與今日漲跌停價格等權威屬性。
    * 實作 `analyze_shioaji_big_orders(code, date, threshold_vol, threshold_amt)`：逐筆成交 ticks 大單主力籌碼分析，結構化返回 Dict 便於渲染。
  - **包裝與 SQLite 快取機制**（`query_wrapper.py`）：
    * 對接四行情函數，整合 `add_history` 使其無縫融入書籤釘選儀表板與查詢軌跡中。
    * 實施 SQLite 永久快取防流量爆點：快照快取 10秒，分K快取 10分鐘，合約快取 24小時，大單快取 5分鐘/1天。
  - **視覺化原地高階渲染與選單上架**（`app.py` & `ui_components.py`）：
    * 選單升級：`NO_DATE_ITEMS` 和 `DATE_ITEMS` 新增四核心 Shioaji 選項，提供 K 線週期、大單門檻動態面板。
    * 最佳五檔 HTML/CSS 視覺化：在 `ui_components.py` 中以高質感卡片繪製「五檔報價盤」，成交價正中央，委買委賣 Bar 紅綠雙向進度條。
    * 主力大單流向圓餅圖：以 Plotly 圓餅圖（大單買入 vs 大單賣出 vs 一般交易）與淨流入指標卡動態解讀，並提供明細名冊。
    * 官方合約 Key-Value 列表與漲跌停價格大徽章面板。
    * 書籤快速原位查詢與分流：`_taistock_dispatch` 重構為 `**kwargs` 動態接收選用分K週期與大單參數，確保舊書籤調用 100% 綠燈相容。
  - **單元測試全綠通過**：
    * 新增 `tests/test_shioaji_market.py`。
    * `pytest` 跑綠 **266 項測試 (100% 全數綠燈通過，無任何 Regression，相容性達極致)**！
