# 台股查詢工具 — 程式碼改進 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修復一個測試回歸、清除已外洩的 API 金鑰、移除 git 雜物、定案快取策略，並為查詢分派與 app.py 的重構鋪路。

**Architecture:** 純函式 / side-effect 腳本混合的 Streamlit 專案。app.py 由上到下執行，最後依 `selected_tab` 分派 `render_*()`。金鑰已在 `sinopac_query.py` / `config.py` 正確外部化，但有死碼檔與文件殘留明文金鑰。快取為三層（`st.cache_data` + SQLite + 模組 dict），SQLite 因非 host-mount 而每次部署被清空。

**Tech Stack:** Python 3.13、Streamlit、pandas、pytest、Docker（NAS 部署）、yfinance / FinMind / Shioaji。

> **共通規則**
> - 路徑相對於專案根目錄 `永豐金API/`。
> - 部署流程見 `CLAUDE.md`：`local` 開發 → merge 進 `main` → `git push origin main`（GitHub）+ `git push nas main`（NAS 自動重啟）。
> - **每完成一個 Stage 才整批 commit + 部署，不要每個 Task 都推。**
> - 每個 Task 結束都必須跑 `python -m pytest tests/ -q`（**不可加 `--ignore`**）確認全綠且無 collection error。

---

## Task Navigation

**Stage 0 — 止血（P0，必做）**
- Task 1：修復 `date_input` 測試回歸（兩行 `isinstance` 保護）
- Task 2：金鑰止血（刪死碼檔 + 文件改佔位符）

**Stage 1 — 清理（P1，低風險）**
- Task 3：untrack `.coverage`
- Task 4：定案快取策略（cache 目錄可配置 + host-mount + 移除 band-aid）

**Stage 2 — 重構（P2，需測試保護，Stage 0/1 全綠後再啟動）**
- Task 5：統一查詢分派為 registry
- Task 6：抽出 `theme.py` + 移除死碼

---

## Task 1: 修復 `date_input_section` 測試回歸

**背景**：先前修「美股 K 線停在 2/6」時，在日期元件加了 `end_date < date.today() - timedelta(days=7)` 比較。`tests/test_dashboard_pinning.py` 內的 `MockStreamlit`（該檔第 4–37 行）**沒有覆寫 `date_input`**，因此 `st.date_input(...)` 回傳 `MagicMock`；`MagicMock < date` 觸發 `TypeError`，使該檔在 **collection 階段**崩潰、整批 pytest 中斷。
session_state 的兩處比較（`ui_components.py:546`、`app.py:3162`）**已有** `isinstance` 保護；出問題的只有 widget 回傳值的兩處比較。

**Files:**
- Modify: `ui_components.py:564`
- Modify: `app.py:3173`
- Test（既有，不需新建）：`tests/test_dashboard_pinning.py`

- [ ] **Step 1: 重現 RED（既有測試應崩潰）**

Run:
```bash
python -m pytest tests/test_dashboard_pinning.py -q
```
Expected: collection error，訊息含
`TypeError: '<' not supported between instances of 'MockStreamlit' and 'datetime.date'`，指向 `ui_components.py` 日期比較行。

- [ ] **Step 2: 修 `ui_components.py`**

把第 564 行：
```python
    # 若結束日期超過 7 天前，顯示警告提示
    if end_date < date.today() - timedelta(days=7):
```
改為：
```python
    # 若結束日期超過 7 天前，顯示警告提示（isinstance 保護：mock/None 不進入比較）
    if isinstance(end_date, date) and end_date < date.today() - timedelta(days=7):
```
（`date`、`timedelta` 已於檔案頂部 import，無需新增。）

- [ ] **Step 3: 修 `app.py` 技術分析 Tab**

把第 3173 行：
```python
    # 若結束日期超過 7 天前，顯示提示並提供快速重設
    if end_date < date.today() - timedelta(days=7):
```
改為：
```python
    # 若結束日期超過 7 天前，顯示提示並提供快速重設（isinstance 保護）
    if isinstance(end_date, date) and end_date < date.today() - timedelta(days=7):
```

- [ ] **Step 4: 驗證 GREEN（整批，不可加 --ignore）**

Run:
```bash
python -m pytest tests/ -q
```
Expected: `261 passed`（或更多），**0 errors、0 failed、無 collection error**。

- [ ] **Step 5: Verification**
  - [ ] `python -m pytest tests/test_dashboard_pinning.py -q` 單獨通過
  - [ ] `grep -n "isinstance(end_date, date)" ui_components.py app.py` 顯示兩處皆已加保護
  - [ ] `python -m pytest tests/ -q` 全綠無 collection error

---

## Task 2: 金鑰止血（死碼刪除 + 文件佔位符）

**⚠️ 人工前置步驟（執行模型無法代勞）**：舊金鑰已 push 到公開 GitHub，**需使用者先到永豐金 / FinMind 後台重新產生（rotate）金鑰**。本 Task 只清理 repo，不負責換新值。

**背景**：明文金鑰位置（皆已被 git 追蹤並 push）：
- `query_scanner.py:4-5`（Shioaji 金鑰）— 經 grep 確認**無任何檔案 import**，死碼。
- `test_shioaji.py`（Shioaji 金鑰）— 根目錄 scratch，非 `tests/` 內正式測試。
- `CLAUDE.md`、`GEMINI.md`（Shioaji 金鑰 + FinMind token）。

**Files:**
- Delete: `query_scanner.py`、`test_shioaji.py`
- Modify: `CLAUDE.md`、`GEMINI.md`

- [ ] **Step 1: 確認死碼無引用**

Run:
```bash
grep -rn "import query_scanner\|from query_scanner" --include=*.py .
grep -rn "import test_shioaji\|from test_shioaji" --include=*.py .
```
Expected: 兩者皆**無輸出**。若有輸出則停止並回報使用者。

- [ ] **Step 2: 刪除死碼檔**

Run:
```bash
git rm query_scanner.py test_shioaji.py
```

- [ ] **Step 3: 文件金鑰改佔位符**

在 `CLAUDE.md` 與 `GEMINI.md` 中，將實際金鑰字串替換為佔位符（保留周邊說明文字，只換值）：
- Shioaji API Key（`5VBRc94…` 開頭那把）→ `<YOUR_SHIOAJI_API_KEY>`
- Shioaji Secret Key（`HUQv6it…` 開頭那把）→ `<YOUR_SHIOAJI_SECRET_KEY>`
- FinMind token（`eyJ0eXAi…` 開頭那把）→ `<YOUR_FINMIND_TOKEN>`

- [ ] **Step 4: 確認 repo 內已無明文金鑰**

Run:
```bash
grep -rn "5VBRc94\|HUQv6it" --include=*.py --include=*.md .
```
Expected: **無輸出**。（`.git/` 歷史仍含舊值，屬已知；是否用 `git filter-repo` 清歷史由使用者決定，rotate 後風險已大幅降低。）

- [ ] **Step 5: Verification**
  - [ ] `query_scanner.py`、`test_shioaji.py` 已不存在
  - [ ] Step 4 grep 無輸出
  - [ ] `python -m pytest tests/ -q` 仍全綠（確認刪檔未影響正式測試）
  - [ ] 已向使用者確認舊金鑰已 rotate

---

## Task 3: untrack `.coverage`

**背景**：`.coverage`（二進位覆蓋率檔）被追蹤，每次跑測試就顯示 modified，污染每個 commit 的 diff。`htmlcov/` 是 `--cov` 的 HTML 輸出，一併忽略。

**Files:**
- Modify: `.gitignore`
- Untrack: `.coverage`

- [ ] **Step 1: 加入 gitignore**

在 `.gitignore` 末尾（或「日誌」區塊附近）新增：
```
# 測試覆蓋率
.coverage
htmlcov/
```

- [ ] **Step 2: 移除追蹤（保留本機檔案）**

Run:
```bash
git rm --cached .coverage
```

- [ ] **Step 3: Verification**

Run:
```bash
python -m pytest tests/ -q
git status --short
git ls-files | grep -i coverage
```
Expected:
  - [ ] `git status --short` 中不再出現 `.coverage`
  - [ ] `git ls-files | grep -i coverage` 無輸出

---

## Task 4: 定案快取策略（讓 SQLite 真正跨重啟存活）

**背景**：`sqlite_cache.py` 的 db 在 `~/.app_config/cache.db`，位於容器內、**非 host-mount**，故每次 `git push nas`（觸發 `docker restart`）就清空，「永久快取」名不副實。先前為繞過此問題在 `query_wrapper.py` 的 `_cached_kbar` 加了「end_date 距今 ≤30 天就跳過 SQLite」的暫時性 band-aid，應改為正解。

**決策**：採 host-mount 方案。**子步驟有依賴順序**：4a（程式，可立即做且向後相容）→ 4b（NAS 掛載，使用者手動）→ 4c（移除 band-aid，**必須等 4b 確認後才做**，否則會失去保護）。

**Files:**
- Modify: `sqlite_cache.py:14-16`
- Modify: NAS `update_web.sh`（位於 NAS `/volume1/docker/sinopac/`，**不在 repo**，使用者手動）
- Modify: `query_wrapper.py`（`_cached_kbar`，約 241–287 行）

### 4a — cache 目錄可由環境變數覆寫（程式，向後相容）

- [ ] **Step 1: 改 `sqlite_cache.py`**

把第 14–16 行：
```python
# 快取目錄與檔案路徑
CACHE_DIR = Path.home() / ".app_config"
CACHE_DB = CACHE_DIR / "cache.db"
```
改為：
```python
# 快取目錄與檔案路徑（可由 APP_CACHE_DIR 環境變數覆寫，供 Docker host-mount 使用）
import os as _os
CACHE_DIR = Path(_os.environ.get("APP_CACHE_DIR", str(Path.home() / ".app_config")))
CACHE_DB = CACHE_DIR / "cache.db"
```

- [ ] **Step 2: 驗證向後相容**

Run（不設環境變數，行為應與原本相同）:
```bash
python -c "from sqlite_cache import CACHE_DIR; print(CACHE_DIR)"
python -m pytest tests/ -q
```
Expected: 路徑印出為使用者家目錄下的 `.app_config`；測試全綠。

### 4b — NAS 掛載 host volume（使用者手動，SSH 進 NAS）

- [ ] **Step 3: 在 NAS `update_web.sh` 的 `docker run` 加掛載**

於 `docker run` 指令加上（先確認 host 目錄存在）：
```sh
mkdir -p /volume1/docker/sinopac/cache
# docker run ... 內新增：
#   -e APP_CACHE_DIR=/data/cache \
#   -v /volume1/docker/sinopac/cache:/data/cache \
```
重新執行 `sudo sh update_web.sh` 套用。

### 4c — 移除 band-aid（**僅在 4b 完成後**）

- [ ] **Step 4: 還原 `_cached_kbar` 為單純快取邏輯**

把目前 `_cached_kbar` 內依 `_use_sqlite = (_end_dt < date.today() - _td(days=30))` 分流的程式碼，還原為「永遠先查 SQLite → 命中即回 → 未命中再抓 → 抓到即寫入（`ttl=86400`）」。移除所有 `_use_sqlite` 條件。新鮮度改由 TTL 控制；因 cache key 含確切 `end_str` 日期字串（不同結束日 = 不同 key），不會回傳過期區間。

- [ ] **Step 5: Verification**
  - [ ] `grep -n "_use_sqlite" query_wrapper.py` 無輸出
  - [ ] `python -m pytest tests/ -q` 全綠（含 `test_query_wrapper.py`）
  - [ ] 本機 `APP_CACHE_DIR=/tmp/c python -c "import query_wrapper"` 後，`/tmp/c/cache.db` 在一次查詢後出現
  - [ ] NAS：部署 → `sudo docker restart sinopac-web` → 進站查 K 線 → log 出現 `[CACHE HIT]`，證明跨重啟存活

---

## Task 5: 統一查詢分派為 registry

**背景**：`app.py` 的 `execute_from_history()`（約 553 行）與 `execute_query_by_params()`（約 622 行）是兩條平行的大型 if/elif。新增查詢類型須改多處、易漏。改為單一 `{query_type: handler}` registry，兩入口共用。

**Files:**
- Modify: `app.py`
- Create: `tests/test_dispatch_registry.py`

- [ ] **Step 1: 枚舉現有 query_type（動工前必做）**

Run:
```bash
grep -n 'query_type ==\|q_type ==\|qt ==' app.py
```
把列出的所有字串值記下，作為 registry 的 key 全集（至少含 `ranking`、`snapshot`、`kbar`、`ticks`、`institutional`）。

- [ ] **Step 2: Write the failing test**

Create `tests/test_dispatch_registry.py`：
```python
import sys
from unittest.mock import MagicMock

# app.py 於 import 時會碰 streamlit，沿用既有 mock 手法
sys.modules.setdefault("streamlit", MagicMock())

import pytest

@pytest.mark.unit
def test_registry_exists_and_covers_known_types():
    from app import QUERY_DISPATCH
    for qt in ["ranking", "snapshot", "kbar", "ticks", "institutional"]:
        assert qt in QUERY_DISPATCH, f"registry 缺少 {qt}"
        assert callable(QUERY_DISPATCH[qt])
```

- [ ] **Step 3: Run test, verify it fails**

Run:
```bash
python -m pytest tests/test_dispatch_registry.py -q
```
Expected: FAIL，`ImportError: cannot import name 'QUERY_DISPATCH' from 'app'`。

- [ ] **Step 4: Implement registry**

於 `app.py`：
1. 為每個 query_type 抽出 `_handle_<type>(params: dict)` 函式（內容搬自現有 if/elif 分支，統一接 `params` dict、回傳結果）。
2. 定義 `QUERY_DISPATCH = {"ranking": _handle_ranking, "snapshot": _handle_snapshot, ...}`（涵蓋 Step 1 枚舉的全集）。
3. 將 `execute_from_history` 與 `execute_query_by_params` 改為：解析出 `query_type` 與 `params` 後呼叫 `QUERY_DISPATCH[query_type](params)`；保留各自外層差異（來源不同、render 包裝不同），只共用分派核心。

- [ ] **Step 5: Run tests, verify pass**

Run:
```bash
python -m pytest tests/test_dispatch_registry.py tests/ -q
```
Expected: 新測試與既有測試全綠（特別注意 `test_history_flow.py`、`test_bookmark_flow.py`、`test_dashboard_pinning.py`）。

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_dispatch_registry.py
git commit -m "refactor: 統一查詢分派為 QUERY_DISPATCH registry"
```

- [ ] **Step 7: Verification**
  - [ ] `app.py` 內不再有兩段重複的 query_type if/elif
  - [ ] 手動：UI 重跑一筆歷史查詢、執行一個書籤，結果正確

---

## Task 6: 抽出 `theme.py` + 移除死碼

**背景**：app.py 3544 行、覆蓋率 0%。先做最安全的一刀——把主題 CSS 外移；並刪掉無意義的死碼。

> 踩雷提醒（見 `CLAUDE.md`「錯誤一」）：CSS f-string 內的 `{}` 需寫成 `{{}}`；整段 CSS 只能有一個 `st.markdown(f"...")`。搬移時**原樣搬，勿改內容**。

**Files:**
- Create: `theme.py`
- Modify: `app.py`

- [ ] **Step 1: 抽 `theme.py`**

把 `app.py` 的 `THEMES` dict（約 38 行起）與 `_inject_theme_css()` 函式（約 116 行起）整段剪到新檔 `theme.py`（含其 import：`streamlit as st`）。在 `theme.py` 將函式更名匯出為 `inject_theme_css`（去掉前底線）。

- [ ] **Step 2: 在 `app.py` 改用 import**

於 app.py 頂部 import 區新增：
```python
from theme import THEMES, inject_theme_css
```
並把原本呼叫 `_inject_theme_css(...)` 的兩處改為 `inject_theme_css(...)`。刪除 app.py 內已外移的 `THEMES` 與 `_inject_theme_css` 定義。

- [ ] **Step 3: 移除死碼**

刪除 `app.py:2521-2522` 的無意義殘留：
```python
if __name__ == "__main__":
    pass
```

- [ ] **Step 4: Verification**

Run:
```bash
python -c "import ast; ast.parse(open('app.py',encoding='utf-8').read()); ast.parse(open('theme.py',encoding='utf-8').read()); print('parse OK')"
python -m pytest tests/ -q
```
  - [ ] 兩檔皆 parse OK
  - [ ] `tests/` 全綠
  - [ ] 手動：`streamlit run app.py`，切換 5 種主題，配色正常套用
  - [ ] `app.py` 行數明顯下降（CSS 已外移）

- [ ] **Step 5: Commit**

```bash
git add app.py theme.py
git commit -m "refactor: 抽出 theme.py 並移除死碼"
```

---

## Self-Review（撰寫者已核對）

- **涵蓋度**：六項發現各對應一個 Task（測試回歸→T1、金鑰外洩→T2、.coverage→T3、快取→T4、分派重複→T5、app.py 過大/死碼→T6）。
- **無 placeholder**：每個程式步驟皆給出確切舊碼→新碼或確切指令與預期輸出。
- **型別一致**：registry 名稱統一為 `QUERY_DISPATCH`；主題函式統一為 `inject_theme_css`；環境變數統一為 `APP_CACHE_DIR`。
- **依賴順序**：T4 明確標註 4a→4b→4c 的依賴（band-aid 須等 host-mount 後才移除）。

## 給使用者的決策點

1. **T2 金鑰**：執行前需你先 rotate 永豐金/FinMind 金鑰；是否用 `git filter-repo` 清 git 歷史由你決定。
2. **T4 快取**：本計劃預設 host-mount 方案；若你想直接砍掉 SQLite 層（只留 `st.cache_data`），告知我改寫此 Task。
3. **T6 拆分**：預設只先抽 `theme.py`；要否一併拆 `tabs/` 子模組可日後再排。
