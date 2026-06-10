# 台股查詢工具 — 全面改進計劃（2026-06）

> 本文件是給 AI 代理（Gemini / Antigravity）執行的改進計劃。
> 請**按階段順序執行**，每個階段完成後跑 `pytest` 確認全綠（目前基準：266 項測試 100% 通過），再進入下一階段。
> 每個階段做完各自 commit 一次（在 `local` 分支開發），不要把多個階段混在同一個 commit。

---

## 0. 現況診斷摘要（為什麼要改）

| 問題 | 證據 | 影響 |
|---|---|---|
| **巨石檔案** | `app.py` 3,150 行、`sinopac_query.py` 1,962 行、`query_wrapper.py` 1,546 行、`ui_components.py` 1,154 行 | 任何修改都要在數千行中定位，AI 與人類都容易改錯、merge 衝突頻繁 |
| **大量複製貼上樣板** | `query_wrapper.py` 中每個查詢都是 `_cached_X()` + `query_X()` 成對出現，共 40+ 對，邏輯 95% 相同 | 新增一個查詢要複製 30 行；改快取策略要改 40 處 |
| **Git 倉庫污染** | 追蹤了 `app.py.bak`、`2330_daily_kbar.png`、`htmlcov/`、`.coverage`、`shioaji.log`、`T4_10142/`（含 `.suo`、`.dll`、**`.pfx` 憑證檔**）、`scratch_test_screener.py`、`email_preview.html` | 倉庫肥大、含敏感檔案、clone 緩慢 |
| **文件散落** | 根目錄有 10+ 個 `PHASE*.md`、`*_REPORT.md`、`*_GUIDE.md` | 找不到現行有效文件，歷史報告與現行規格混雜 |
| **CSS/主題雙重注入** | `theme.py`（437 行）存在，但 `app.py` 內仍有 60 處 `st.markdown` 注入 CSS/HTML | 改主題要改兩處，容易不同步 |
| **設定層脆弱** | `config.py` 的 `ConfigManager` 用 `global` 改模組級變數；`sinopac_query.py` 的 `FINMIND_TOKEN` 在 import 時固定，UI 改了金鑰要重啟才生效 | 設定變更行為不可預測、測試互相污染 |
| **測試配置拖慢開發** | `pytest.ini` 的 `addopts` 強制每次都跑 `--cov` 並產生 HTML 報告；根目錄殘留 `test_us_stock.py` 不在 `tests/` 內 | 每次跑測試都變慢；測試檔案位置不一致 |
| **依賴無版本鎖定** | `requirements.txt` 全部不帶版本 | NAS / Streamlit Cloud / 本機三個環境可能裝到不同版本，重現問題困難 |
| **無 CI 品質防線** | `.github/workflows/` 只有 daily 排程，沒有 PR/push 時跑測試與 lint | 壞 code 可以直接推上 main 部署到 NAS |
| **快取層用 pickle** | `sqlite_cache.py` 以 `pickle` 序列化 | DataFrame 跨 pandas 版本反序列化可能失敗；安全面也較弱 |

---

## Phase 1：倉庫衛生（低風險，先做，立刻見效）

### 1.1 移除不該追蹤的檔案

從 git 追蹤中移除（用 `git rm --cached`，**保留本機檔案**，除了明確說刪除的）：

```
git rm --cached app.py.bak
git rm --cached 2330_daily_kbar.png
git rm --cached email_preview.html
git rm -r --cached T4_10142/
git rm --cached scratch_test_screener.py   # 內容已被 tests/ 正式測試取代，本機檔案也可刪
```

注意：
- `T4_10142/` 是另一家券商（SinoPac T4 舊版）的 SDK 壓縮包內容，與本專案無關，且含 `.pfx` 憑證與 `.dll`。從追蹤移除後，本機目錄保留即可。
- `app.py.bak` 本機檔案可直接刪除（git 歷史已有舊版）。

### 1.2 補強 `.gitignore`

在現有 `.gitignore` 追加：

```gitignore
# 備份與暫存
*.bak
*.tmp
scratch_*.py

# 產出物
*.png
email_preview.html
T4_10142/

# pytest
.pytest_cache/
```

（注意：若未來有需要追蹤的 png，如 docs 用圖，再用 `!docs/**/*.png` 開白名單。）

### 1.3 整理文件到 `docs/`

建立以下結構並搬移（用 `git mv`）：

```
docs/
├── history/          ← 歷史交付報告（唯讀，不再更新）
│   ├── PHASE4_DELIVERY.md
│   ├── PHASE4_FEATURES.md
│   ├── PHASE4_IMPLEMENTATION_SUMMARY.md
│   ├── PHASE6_ASYNC_REPORT.md
│   ├── PHASE6_COMPLETE_SUMMARY.md
│   ├── PHASE6_PRELOAD_REPORT.md
│   ├── README_PHASE6.md
│   ├── PERFORMANCE_REPORT.md
│   └── MENU_VERIFICATION.md
├── guides/           ← 現行有效的使用指南
│   ├── TECHNICAL_ANALYSIS_GUIDE.md
│   └── TESTING_GUIDE_PHASE4.md
└── plans/            ← 改進計劃（本文件已在此）
```

根目錄只保留：`README.md`、`CLAUDE.md`、`GEMINI.md`。

### 1.4 測試檔案歸位

- 把根目錄的 `test_us_stock.py` 移入 `tests/`（若內容與 `tests/` 既有測試重複則直接刪除；先比對）。
- `verify_non_tw_features.py` 移到 `scripts/`（新建目錄，放手動驗證/一次性腳本）：
  ```
  scripts/
  ├── verify_non_tw_features.py
  ├── backfill.py
  └── email_preview.py
  ```
  搬移後全域搜尋這三個檔名，修正任何引用路徑（CLAUDE.md、GEMINI.md、workflow yml、bat 檔）。

### 1.5 修正 `pytest.ini`

把 coverage 從預設拿掉（要看覆蓋率時手動加參數）：

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -q --tb=short
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow running tests
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
```

**驗收標準**：`git status` 乾淨、`pytest` 全綠、根目錄只剩 README.md / CLAUDE.md / GEMINI.md 三個 md。

---

## Phase 2：依賴鎖定 + CI 品質防線

### 2.1 鎖定依賴版本

1. 在目前可正常運行的環境執行 `pip freeze`，取出 `requirements.txt` 中每個套件的實際版本。
2. 改寫 `requirements.txt` 為 `套件>=目前版本,<下個大版本` 形式（例如 `pandas>=2.2,<3`、`streamlit>=1.40,<2`）。`requirements.daily.txt` 同樣處理。
3. 特別注意 `shioaji`、`FinMind`、`yfinance` 三個 API 套件——yfinance 改版頻繁且常破壞相容性，務必鎖上界。

### 2.2 新增 CI workflow

新建 `.github/workflows/ci.yml`：

```yaml
name: CI
on:
  push:
    branches: [main, local]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - run: pip install -r requirements.txt pytest pytest-cov ruff
      - name: Lint (僅擋嚴重錯誤)
        run: ruff check . --select E9,F63,F7,F82
      - name: Tests
        run: pytest
```

注意：tests 目前在無 Shioaji 金鑰環境可全綠（CI 上 `shioaji` 若安裝失敗，程式已有 `HAS_SHIOAJI=False` fallback；若 CI 裝 shioaji 太慢，可在 CI 改裝 `requirements.daily.txt` + 測試所需套件，視 conftest 的 mock 程度決定）。先試最簡單版本，跑不過再調整。

### 2.3 新增 `ruff` 設定

新建 `pyproject.toml`（僅 lint 設定，不改打包方式）：

```toml
[tool.ruff]
line-length = 120
target-version = "py311"

[tool.ruff.lint]
select = ["E9", "F"]       # 先只抓語法錯誤與未定義名稱，不追求風格
ignore = ["F401"]          # 容忍未使用 import（後續 Phase 再清）
```

**驗收標準**：GitHub Actions 上 CI 全綠；本機 `ruff check .` 無 E9/F8 級錯誤。

---

## Phase 3：消除 query_wrapper.py 的 40+ 對樣板（核心重構之一）

### 3.1 問題

目前模式（重複 40+ 次）：

```python
@st.cache_data(ttl=3600, show_spinner=False)
def _cached_month_revenue(code, start_str, end_str) -> pd.DataFrame:
    return sq.query_month_revenue(code, start_str, end_str)

def query_month_revenue(code, start_date, end_date) -> pd.DataFrame:
    # 計時、log、cache hit 統計、SQLite 快取、add_history …每個函數都複製一份
```

### 3.2 目標：單一快取裝飾器工廠

新建 `caching.py`：

```python
"""統一查詢快取裝飾器：記憶體 (st.cache_data) + SQLite 永久層 + 命中統計 + 計時 log"""
import functools, time, hashlib, json
import pandas as pd
from logging_config import main_logger
from sqlite_cache import get_cache, set_cache

def cached_query(ttl: int = 3600, sqlite_ttl: int | None = None, name: str | None = None):
    """
    ttl:        st.cache_data 記憶體快取秒數
    sqlite_ttl: SQLite 永久快取秒數（None = 不落地）
    name:       快取鍵前綴，預設用函數名
    用法：
        @cached_query(ttl=3600, sqlite_ttl=86400)
        def query_month_revenue(code: str, start_str: str, end_str: str) -> pd.DataFrame:
            return sq.query_month_revenue(code, start_str, end_str)
    """
    ...
```

實作要求：
1. 快取鍵 = `name或函數名 + 所有位置/關鍵字參數的 json 序列化 hash`。參數必須先轉成可序列化的基本型別（date → isoformat 字串）——**因此被裝飾的函數簽名一律收字串/數字，date 轉字串放在呼叫端或裝飾器內處理，沿用現有 `_cached_X(code, start_str, end_str)` 的字串參數慣例**。
2. 查詢順序：`st.cache_data` 記憶體層（由裝飾器內部包一層 `@st.cache_data` 或自行用 session 級 dict）→ SQLite 層 → 真正呼叫 API → 回寫兩層。
3. 保留現有行為：計時 log（沿用 `logging_config`）、`_record_cache_hit` 命中統計（搬進裝飾器）、空 DataFrame 不寫入 SQLite（避免快取失敗結果）。
4. **不要在裝飾器裡呼叫 `add_history`**——歷史記錄屬於 UI 行為，維持在呼叫端（app.py 的 handler）。

### 3.3 漸進遷移策略（重要，降低風險）

1. 先實作 `caching.py` + 新增 `tests/test_caching.py`（測：命中、過期、參數區分、空 DF 不落地、SQLite 損壞時 fallback 直呼 API）。
2. 挑 3 個代表性函數先遷移驗證：`query_month_revenue`（FinMind 歷史）、`query_twse_daily_all`（TWSE 當日）、`query_snapshot`（Shioaji 即時，ttl=10）。跑全部測試。
3. 確認綠燈後，分批（每批 8–10 個函數）把其餘 `_cached_X / query_X` 對改寫為單一函數 + 裝飾器。**對外函數名與簽名完全不變**（`query_wrapper.py` 內所有 `query_*` 與相容性別名都要保留），確保 `app.py`、`tabs/`、tests 的 mock patch 路徑不破。
4. 每批跑一次 `pytest`。tests 內若有直接 patch `_cached_X` 的，同步把 patch 目標改為新函數。

**驗收標準**：`query_wrapper.py` 從 1,546 行縮到約 600 行以下；`pytest` 全綠；手動啟動 `streamlit run app.py` 抽查台股市場、FinMind、TWSE 三個分頁各一個查詢正常。

---

## Phase 4：app.py 拆分（核心重構之二）

### 4.1 目標結構

延續既有的 `tabs/` 慣例（已有 dashboard.py、pdf_export.py 等），把 `app.py` 中所有 `render_*` 函數搬出去：

```
app.py                     ← 只剩 ~300 行：page config、主題注入、session state 初始化、
                              側邊欄導航、QUERY_DISPATCH 註冊表、路由分發
dispatch.py                ← QUERY_DISPATCH dict + execute_query_by_params + execute_from_history
                              + 所有 _handle_* 函數（從 app.py 整體搬移）
tabs/
├── dashboard.py           （已存在）
├── taistock.py            ← render_taistock_market + _taistock_dispatch + _handle 相關
├── twse.py                ← render_twse_section + _twse_dispatch
├── finmind.py             ← render_finmind + _finmind_dispatch
├── futures_forex.py       ← render_futures_forex + _futures_forex_dispatch
├── hk_stocks.py           ← render_hk_us_stocks + _hkus_dispatch（Futu 港股）
├── us_stocks.py           ← render_us_stocks + _us_stock_dispatch
├── us_calendar.py         ← render_us_calendar_consensus（注意：與根目錄資料模組
│                             us_calendar.py 撞名，UI 檔改名 tabs/us_calendar_tab.py）
├── screener_tab.py        ← render_screener + render_us_screener + 兩個 result_block
├── technical.py           ← render_technical_analysis
├── news.py                ← render_news + _render_news_cards + _news_to_text + AI 摘要按鈕
├── tools.py               ← render_tools（書籤/歷史/對比/設定）
├── ai_chat.py             ← render_deepseek_chat
└── （既有的 technical_scanner / pdf_export / watchlist_monitor / portfolio_tracker / health_monitor 不動）
```

### 4.2 執行規則

1. **純搬移，不改邏輯**。每個函數整段剪下貼上，import 補齊。共用的小工具（如 `_qbtn_grid`、`_render_batch_results`、`_nav_btn`）放 `ui_components.py` 或新建 `tabs/_shared.py`。
2. 注意循環 import：`dispatch.py` 不可以 import `tabs/`，`tabs/` 可以 import `dispatch.py`。若 `_handle_*` 需要 tabs 內的 dispatch 函數（如 `_taistock_dispatch`），把 dispatch 函數放到對應 tab 模組，`dispatch.py` 用延遲 import（函數內 import）。
3. 一次搬一個 tab，搬完一個就 `streamlit run app.py` 啟動確認該分頁能開、`pytest` 綠燈，再搬下一個。
4. tests 內 patch `app.XXX` 的路徑會壞，逐一修正為新模組路徑。
5. session state key 名稱完全不變（書籤/歷史的向後相容靠這個）。

**驗收標準**：`app.py` < 400 行；所有側邊欄分頁可開啟並完成一次查詢；`pytest` 全綠；書籤與歷史記錄的舊資料仍可正常重新執行（用既有 `~/.app_config/bookmarks.json` 實測）。

---

## Phase 5：sinopac_query.py 拆分（資料層 / CLI 分離）

### 5.1 目標結構

```
datasources/
├── __init__.py        ← 重新匯出所有公開函數（向後相容：from datasources import query_kbars …）
├── shioaji_client.py  ← ShioajiConnectionPool、login、query_scanner/snapshot/kbars/ticks、
│                         query_shioaji_*、analyze_shioaji_big_orders、帳務 8–13
├── finmind_client.py  ← _finmind_api、FINMIND_TOKEN、所有 FinMind 查詢（16–30）
├── twse_client.py     ← 所有 TWSE 查詢（41–47、mi_index、monthly、annual、company 雙層架構）
├── futu_client.py     ← Futu 連線與查詢（31–38）
└── news_client.py     ← yfinance 新聞（14–15）

cli.py                 ← 互動選單（原 sinopac_query.py 的 menu/main 部分），from datasources import *
sinopac_query.py       ← 保留為相容墊片：from datasources import *（一行式 re-export），
                          並保留 `if __name__ == "__main__": from cli import main; main()`
```

### 5.2 執行規則

1. `sinopac_query.py` **不能刪**——`query_wrapper.py`、tests、CLAUDE.md 全都引用 `import sinopac_query as sq`。改成 re-export 墊片後，所有舊 import 路徑不變即可運作。
2. `FINMIND_TOKEN` 順手修掉「import 時固定」的問題：改為函數 `get_finmind_token()` 每次呼叫時讀取（先查環境變數，再查 config），各 FinMind 查詢內呼叫它。模組層保留 `FINMIND_TOKEN = get_finmind_token()` 變數以向後相容，但內部一律走函數。
3. 同樣一次搬一個 client，每搬完跑 `pytest`。

**驗收標準**：`pytest` 全綠；`python sinopac_query.py` 互動選單仍可啟動；`python cli.py` 也可啟動。

---

## Phase 6：設定層現代化

### 6.1 重寫 `config.py` 的 ConfigManager

問題：`ConfigManager.__init__` 用 `global` 改模組級路徑常數，測試之間互相污染，且 `load_config()` 等純函數永遠讀全域路徑。

改法（保持兩套 API 都能用）：

```python
class ConfigStore:
    """實例化的設定存取器，路徑為實例屬性，不碰全域"""
    def __init__(self, config_dir: Path | None = None):
        self.config_dir = Path(config_dir) if config_dir else Path.home() / ".app_config"
        self.config_file = self.config_dir / "config.json"
        # bookmarks / history / watchlist 同理
    # load_config/save_config/… 全部搬成實例方法

_default_store = ConfigStore()

# 模組級函數 = 預設實例的轉發（向後相容，簽名不變）
def load_config(): return _default_store.load_config()
...

# ConfigManager 舊名保留 = ConfigStore 的別名 + 行為相容
ConfigManager = ConfigStore
```

注意 `tests/test_config.py` 依賴 `ConfigManager(config_dir=...)` 後模組級函數也跟著用該目錄——如果測試真的這樣假設，在 `ConfigStore.__init__` 加一個 `make_default: bool = False` 參數或在測試 conftest 用 monkeypatch 處理。**先讀測試再動手，以測試現有行為為準。**

### 6.2 金鑰讀取統一

新增 `config.get_secret(name: str) -> str`：統一「環境變數 → Streamlit secrets → config.json」的讀取順序，讓 `deepseek_engine.py`、`datasources/finmind_client.py`、`adr_query.py` 等都改用它，移除各自重複的讀取邏輯。

**驗收標準**：`pytest` 全綠；在 UI 設定頁修改 FinMind token 後，**不重啟**直接查詢 FinMind 功能即生效。

---

## Phase 7：UI/主題統一

1. 盤點 `app.py`（拆分後在各 tabs/）中 60 處 `st.markdown(...HTML/CSS...)`，凡屬於「主題級樣式」（顏色、按鈕、卡片框架）全部集中到 `theme.py` 的 `_inject_theme_css`；tabs 內只留「資料呈現用」的 HTML（如五檔報價卡、ADR 卡片），且這些 HTML 一律從 `theme.py` 提供的 helper 取得色票（CSS 變數 `var(--claude-primary)` 形式，禁止 hard-code 色碼）。
2. 全域搜尋 hard-code 色碼（`#D97757`、`#1976d2` 等）出現於 tabs/ 與 ui_components.py 的，改為 CSS 變數。
3. 確認五個主題切換後，ADR 卡片、五檔報價、選股結果等自訂 HTML 區塊顏色都跟著變。

**驗收標準**：切換 5 種主題，肉眼檢查儀表板 / 台股市場 / 美股專區三個分頁無「不變色」的殘留區塊。

---

## Phase 8：穩定性與安全強化

### 8.1 SQLite 快取改用安全序列化

`sqlite_cache.py` 目前用 `pickle`。改為：
- DataFrame → `pyarrow` 序列化（`df.to_parquet` 進 BytesIO / `pa.serialize` 替代品：用 `df.to_parquet(buffer)` + `pd.read_parquet`），其他型別 → JSON。
- value 欄旁加 `fmt TEXT` 欄位（`'parquet'` / `'json'` / `'pickle'`）。讀取舊 `pickle` 資料時仍可反序列化（漸進相容），寫入一律新格式。
- 若環境沒有 pyarrow（requirements 需加入 `pyarrow`），fallback pickle 並 log warning。
- 新增 schema migration：啟動時 `ALTER TABLE cache ADD COLUMN fmt TEXT DEFAULT 'pickle'`（包 try/except 已存在則略過）。

### 8.2 error_handler 全面套用

`error_handler.py` 的 `handle_api_error` 裝飾器已存在但使用率低。把它套到 `datasources/` 所有對外 API 呼叫函數上（FinMind、TWSE、yfinance、Futu），參數建議：`max_retries=2, retry_delay=1.0, fallback=pd.DataFrame()`。注意：
- 裝飾器內呼叫了 `st.error`——在非 Streamlit 環境（daily_job、CLI）會出錯或無效。先修改 `error_handler.py`：偵測 `streamlit.runtime.exists()`（或 try/except），非 Streamlit 環境只 log 不顯示 UI 訊息。
- Shioaji 的登入錯誤（金鑰未設定）**不要**重試——`RuntimeError` 直接 raise，由 UI 顯示引導訊息。在裝飾器加 `no_retry_exceptions: tuple = (RuntimeError,)` 參數。

### 8.3 SQLite 快取定期清理

`clear_expired_cache()` 存在但沒人呼叫。在 `app.py` 啟動流程（session 初始化）加一次性呼叫（用 session_state flag 確保每個 session 只跑一次），並在 `daily_job.py` 結尾也呼叫一次。

### 8.4 日誌輪替

確認 `logging_config.py` 使用 `RotatingFileHandler`（maxBytes=5MB, backupCount=3）；若目前是普通 FileHandler 就改掉，避免 NAS 上 log 無限長大。

**驗收標準**：`pytest` 全綠（新增 `tests/test_sqlite_cache_fmt.py` 測新舊格式相容）；手動把網路斷掉開 app，各分頁顯示友善錯誤而非 traceback。

---

## Phase 9：測試與文件收尾

1. **補測試**：Phase 3–6 的新模組（`caching.py`、`dispatch.py`、`ConfigStore`、`datasources/` 墊片相容性）各補單元測試；目標總測試數 ≥ 290，覆蓋率報告（手動跑 `pytest --cov=. --cov-report=term`）核心模組（caching、config、dispatch、sqlite_cache）≥ 80%。
2. **更新 CLAUDE.md / GEMINI.md**：
   - 更新「主要檔案」表格反映新結構（datasources/、tabs/、dispatch.py、caching.py、scripts/）。
   - 在「代理人互動紀錄」追加本次重構摘要。
   - 選單對照表中的函式位置說明同步更新。
3. **更新 README.md**：補上專案結構樹、開發流程（local 分支 → merge main → push origin/nas）、測試指令。
4. **部署驗證**：依 CLAUDE.md 的標準流程 merge 到 main、push GitHub 與 NAS，確認 NAS 容器重啟後網站正常（首頁、台股查詢、技術分析三項抽查）。

---

## 執行注意事項（給 AI 代理的紅線）

1. **絕對不可改變對外行為**：所有 `query_*` 函數名、參數、回傳格式不變；session state key 不變；`~/.app_config/` 下既有 JSON 格式不變。
2. **每個 Phase 一個 commit**（Phase 3、4 可按批次多個 commit），commit message 用 `refactor(phase-N): ...` 格式。
3. **在 `local` 分支開發**，全部完成並驗證後才依 CLAUDE.md 的流程 merge 進 `main` 推送。
4. **每次改動後必跑 `pytest`**，紅燈不准進下一步；遇到測試假設與重構衝突時，優先保留測試所驗證的行為，調整重構方式。
5. **不要動 `daily_job.py` 的業務邏輯**（NAS 排程依賴它），Phase 8.2/8.3 只做錯誤處理與清理呼叫的最小侵入修改。
6. **不要升級依賴大版本**（Phase 2 只是鎖定現況版本，不是升級）。
7. Windows 環境注意：所有檔案讀寫明示 `encoding="utf-8"`；console 輸出已有 cp950 防護，不要移除 `sys.stdout.reconfigure`。
8. 撞名警告：根目錄已有 `us_calendar.py`、`tw_calendar.py`（資料模組），tabs 下的 UI 檔**必須**取不同名（`us_calendar_tab.py`）。

## 優先順序建議（若時間有限）

| 優先 | Phase | 理由 |
|---|---|---|
| ★★★ | 1, 2 | 零風險、立即改善倉庫品質並建立安全網（CI），是後續重構的前提 |
| ★★★ | 3 | 消除最大技術債，之後新增查詢功能成本降 80% |
| ★★ | 4, 5 | 大幅改善可維護性，但工作量大、需小步前進 |
| ★★ | 8 | 直接提升使用者體感穩定性 |
| ★ | 6, 7, 9 | 品質收尾 |
