# 台股查詢與看盤工具

前後端分離的台股（含港美股與全球市場）看盤與研究系統。僅透過 Tailscale 內網存取，部署於 Home Server（`:8600`），支援**盤中專業終端機模式（深色）**與**盤後研究報告模式（淺色）**自動／手動切換。

> 專案目前進度、待辦事項與工作日誌請見 [`PROJECT.md`](PROJECT.md)；開發與部署細節請見 [`CLAUDE.md`](CLAUDE.md)。

## 系統架構

| 目錄 | 說明 |
|---|---|
| `backend/` | FastAPI 服務（`app/main.py`）、背景排程預先計算（`app/worker.py`）、永豐金 Shioaji 即時行情推播（`app/quote/`） |
| `frontend/` | React 19 + Vite 8 + TypeScript 7 + TradingView Lightweight Charts v5 |
| `deploy/` | Docker Compose（`web`、`api`、`worker`、`quote`、`redis`、`twse-mcp`、`ntfy`、`tailnet-proxy`）與自動部署 Hook |
| `legacy/` | 已退役的舊版 Streamlit 網站、CLI 選單與舊排程封存 |

## 核心功能

- **市場總覽（`/`）**：加權指數、漲跌家數、成交金額、三大法人買賣超、處置股／注意股、國際指數與匯率；盤中由永豐金 Shioaji WebSocket 逐筆即時推播。
- **個股頁（`/stock/:code`）**：FinMind 歷史日 K（支援不還原／還原權值切換）＋盤中即時 K 棒與五檔、外資 15 日買賣超、融資融券、月營收年增率、本益比五年位置，以及可展開的**基本面區塊**（單季損益與三率、SVG 本益比河流圖、資產負債結構、歷年股利政策、同業比較）。
- **自選股與警示（`/watchlist`）**：自選股即時報價牆、價格與法人條件警示、處置／注意股自動偵測，支援網頁內、自架 ntfy 與 Telegram 推播。
- **選股與技術掃描（`/screener`）**：涵蓋全市場上市普通股與台灣 50 權值股，內建四階段多因子篩選漏斗（母體 → 技術面 16 項指標訊號 OR/AND → 法人籌碼面 OR/AND → 估值與月營收 YoY），瀏覽器端毫秒級即時篩選。
- **全球市場与美股選股（`/global`）**：國際重要指數、台股 ADR 折溢價、商品與債匯、互動式日 K 圖，以及**美股權值 50 多因子選股**與**美股財報日曆＆華爾街共識**。
- **投資行事曆（`/calendar`）**：除權除息預告、上市櫃法說會、財報與營收法定公布期限。
- **投資組合（`/portfolio`）**：持股部位、未實現與已實現損益統計。
- **AI 助理（`/ai`）**：串接 Agnes LLM 與自架 `TWStockMCPServer`＋站內即時工具，提供有憑有據的個股與總經問答。

## 本機開發與測試

### 後端（Python 3.13）
```bash
C:\Users\shoyu\.venvs\twstock-backend\Scripts\ruff.exe check backend/app backend/tests
C:\Users\shoyu\.venvs\twstock-backend\Scripts\pytest.exe backend/tests -q
```

### 前端（Node 24，於非雲端硬碟鏡像目錄執行）
```powershell
robocopy frontend\src C:\Users\shoyu\dev\twstock-fe\src /MIR
npm --prefix C:\Users\shoyu\dev\twstock-fe run typecheck
npm --prefix C:\Users\shoyu\dev\twstock-fe test -- --run
npm --prefix C:\Users\shoyu\dev\twstock-fe run build
```

## 部署（Home Server）

```bash
git push home local:main
```
推送後由 Home Server `post-receive` hook 自動執行 `docker compose -f deploy/compose.yml up -d --build --remove-orphans`。
