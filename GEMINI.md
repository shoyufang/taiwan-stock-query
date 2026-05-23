# Gemini CLI 專案規範與進度

> 本文件記載 Gemini Agent 在此專案中的工作規範、決策與重要進度。

## 工作流程

1. **變更紀錄**：所有對代碼庫的實質修改，必須同時記錄於 `CLAUDE.md` 的「代理人互動紀錄」區塊，以便與 Claude 代理人同步。
2. **Gemini 模型規範**：嚴禁在代碼或建議中預設使用 `gemini-1.5-flash` 或 `gemini-1.5-pro`。應始終透過 API 動態獲取可用模型清單，或由使用者在 UI 手動挑選。
3. **開發標準**：
    - 遵循 Phase 6 的三層優化架構（Preload -> Async -> Cache）。
    - 保持對 `sinopac_query.py` 的向後兼容性。
    - UI 變更需考量 Streamlit 的狀態管理（Session State）。

## 當前進度 (2026-05-16)

- [x] 建立代理人協作機制。
- [x] 理解 Phase 6 效能優化架構。
- [x] **UI 通稱化**：將「永豐金」統一改為「券商提供」。
- [x] **Futu 測試**：驗證 Futu OpenAPI 功能正常。
- [x] **Phase 7 實作完成**：
    - [x] **SQLite 永久快取**：優化冷啟動效能。
    - [x] **智能動態預載**：基於歷史紀錄預熱數據。
    - [x] **背景定時刷新**：即時報價自動更新（每 30 秒）。
    - [x] **跨市場整合儀表板**：全新的數據總覽介面。
    - [x] **Gemini AI 智能分析**：整合 API 與本地工具，支援自動化功能調用與網頁搜尋。
    - [x] **連線池重構**：大幅加速 Python-native 查詢。
- [x] **專案健檢修復與排程 Notion 解耦 (2026-05-20)**：
    - [x] **單元測試全綠**：相容性包裝 `ConfigManager` 與查詢別名，使 232 項測試 100% 綠燈通過。
    - [x] **Notion 解耦**：無 Notion 金鑰時可優雅略過寫入，不中斷本地排程。
    - [x] **CP950 編碼相容**：修正 Windows 終端機 CP950 Unicode 輸出崩潰，完美支援 Emoji 顯示。
    - [x] **非台股功能完整驗證**：除「台股市場」分頁外，33 項跨模組功能 100% 驗證通過（32 PASS, 1 WARN, 0 FAIL）。
- [x] **公司基本資料查詢崩潰修復與雙層整合升級 (2026-05-21)**：
    - [x] **崩潰修復**：徹底解決 `/company/getCompanyByCode` 廢棄導致的 JSONDecodeError。
    - [x] **雙層查詢架構**：整合 TWSE OpenAPI JSON (上市) 與 MOPS OpenData CSV (上市、上櫃、興櫃)。
    - [x] **完美向後相容**：欄位精確 renaming 映射，並將上櫃/興櫃/上市日期格式完美對齊。
    - [x] **100% 測試全綠**：保持 232 項單元測試 100% 綠燈。
- [x] **台股選股引擎與三大法人端點修復 (2026-05-21)**：
    - [x] **三層防線重構**：今日快取優先 (Cache-First) + 舊版 RWD 接口重建 + 5日智能 Fallback，徹底解決 T86 OpenAPI 廢棄導致選股回傳為空的嚴重故障。
    - [x] **防止重複列 KeyError**：在 `_process_institutional_df` 移除重複 `名稱` 欄位，解決 pandas merge 產生名稱_x/名稱_y 的 KeyError 訪問崩潰。
    - [x] **解決 CP950 Mojibake 亂碼**：顯式聲明 `encoding="utf-8-sig"`，防範 Windows 本地編碼亂碼導致欄位映射失敗。
    - [x] **美股專區功能升級與 Excel 匯出崩潰完美解決 (2026-05-22)**：
    - [x] **美股多數據結構攤平導出**：重構批次結果 Excel 導出邏輯，支援將個股基本資料、多表財務報表、大股東與機構持股、分析師評等與目標價、相關新聞等字典/清單格式自動攤平為多 Sheets 導出。
    - [x] **時區與欄位欄寬安全清理**：強制轉欄位名稱為字串並過濾 timezone-aware datetime 元素，徹底解決 `openpyxl` datetime timezone 崩潰引發的「匯出失敗」問題。
    - [x] **測試全綠通過**：美股單元測試與 Excel 導出流程測試維持 100% 全綠。
    - [x] **美股與港美股功能三大階段深度升級 (2026-05-23)**：
    - [x] **Stage 1 (跨市場 Plotly 技術圖表)**：`query_wrapper.py` 自動分流非台股代號至 `yfinance`，剝離時區防崩潰，SQLite 短期與長期雙重快取；`technical_analysis.py` 漲跌配色與價格 Y 軸小數點自適應；`app.py` 整合中文 AI 別名翻譯。
    - [x] **Stage 2 (台美 ADR 折溢價即時儀表板)**：新增 `adr_query.py` 匯率三防線獲取、三組主流半導體 ADR 折溢價計算公式、以及 60 秒 SQLite 安全頻率限制快取；`app.py` 正中央整合 Glassmorphic 卡片與溢折價自適應徽章。
    - [x] **Stage 3 (一鍵 AI 美股健檢報告)**：`deepseek_engine.py` 匯總財務/股東/評等/新聞並精簡 Token，結合華爾街級 Prompt 指導 AI 產出 5 大模組 SWOT 繁體中文 Markdown 投資報告；`app.py` 引入 AI 報告容器，實作 `st.session_state` 頁面快取防消失，並提供 `.md` 下載匯出。
    - [x] **測試全綠通過**：建立 `test_adr_query.py` 與 `test_ai_report.py`，順利通過 237 項 `pytest` 測試（100% PASSED）。
    - [x] **Phase 7 Stage 4 (美股多因子選股篩選器) 實作完成**：
      - [x] **美股選股模組與 50 檔股票池**：新建 `us_screener.py`，定義 50 檔最具代表性的美股權值股與藍籌巨頭。
      - [x] **12小時 SQLite 永久快取**：實作 `get_us_screener_data()`，支援 12小時永久快取以極速讀取基本面數據。
      - [x] **背景並行下載**：使用 `ThreadPoolExecutor` 背景並行 10 線程下載 50 檔美股基本面與拉回幅度數據，5-8 秒內極速完成。
      - [x] **多因子過濾邏輯**：包含市值、PE、Forward PE、ROE、殖利率、52W高點拉回幅度與行業板塊等多因子聯合漏斗篩選。
      - [x] **Streamlit UI 整合與 Excel 導出**：在 `app.py` 選股分頁引進「台股選股/美股選股」雙模式，美股選股提供高質感兩欄式因子過濾面板、Excel 下載，並主動提示代號快速跳轉。
      - [x] **單元測試全綠通過**：建立 `test_us_screener.py`，順利跑通 242 項 `pytest` 測試（100% PASSED 全綠）。
    - [x] **Phase 7 Stage 5 (美股財報行事曆與華爾街共識 UI) 實作完成**：
      - [x] **財報日程與目標價共識引擎**：新建 `us_calendar.py`，解析 yfinance 財報日程、預期營收/EPS，並獲取推薦評等、分析師平均目標價與參與評估人數。
      - [x] **中文化評等與精緻徽章**：實作 `RATING_MAP`，將 buy, hold 等共識中文化並帶有精美 Emoji 徽章（如 強力買入 🟢🟢）。
      - [x] **24小時 SQLite 永久快取**：日曆與共識數據支援 24 小時 SQLite 永久快取（TTL: 86400s）。
      - [x] **背景並行抓取**：快取失效或強刷時使用 `ThreadPoolExecutor` 開啟 10 線程並行下載，可在 5-8 秒內極速完成。
      - [x] **Streamlit UI 整合與雙 Tab 表格**：在 `app.py` 側邊欄新增獨立導航分頁，實作財報日程公佈表（支持 Excel 下載、按公佈日由近到遠排序）與華爾街潛在漲幅排名表（支持最低潛在漲幅 Slider 與板塊 Filter，一鍵下載 Excel 檔案）。
      - [x] **單元測試全綠通過**：建立 `test_us_calendar.py`，順利跑通 245 項 `pytest` 測試（100% PASSED 全綠）。
- [ ] 待命：等待使用者回饋或新功能開發指令。
