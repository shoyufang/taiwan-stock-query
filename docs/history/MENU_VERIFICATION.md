# 菜單項目完整性驗證清單 — Phase 5 Task 18

## 目標
確保全部 47 個菜單項目都能通過 UI 訪問並正確執行

---

## 台股市場（Shioaji，7項）

### 漲幅排行
- [x] UI 實裝：`render_taistock_market()` - "漲幅排行"
- [x] 查詢函數：`query_ranking("up", count)` ✓
- [x] 結果呈現：`display_result()` ✓
- [x] 歷史記錄：自動存入 ✓

### 跌幅排行
- [x] UI 實裝：`render_taistock_market()` - "跌幅排行"
- [x] 查詢函數：`query_ranking("down", count)` ✓
- [x] 結果呈現：`display_result()` ✓

### 成交量排行
- [x] UI 實裝：`render_taistock_market()` - "成交量排行"
- [x] 查詢函數：`query_ranking("volume", count)` ✓
- [x] 結果呈現：`display_result()` ✓

### 成交金額排行
- [x] UI 實裝：`render_taistock_market()` - "成交金額排行"
- [x] 查詢函數：`query_ranking("amount", count)` ✓
- [x] 結果呈現：`display_result()` ✓

### 個股即時快照
- [x] UI 實裝：`render_taistock_market()` - "個股即時快照"
- [x] 查詢函數：`query_snapshot(codes)` ✓
- [x] 結果呈現：`display_result()` ✓

### 個股日K
- [x] UI 實裝：`render_taistock_market()` - "個股日K"
- [x] 查詢函數：`query_daily_kbar(code, start, end)` ✓
- [x] 結果呈現：`display_result()` ✓

### 逐筆成交
- [x] UI 實裝：`render_taistock_market()` - "逐筆成交"
- [x] 查詢函數：`query_ticks(code, date)` ✓
- [x] 結果呈現：`display_result()` ✓

---

## 帳務（6項，需CA憑證）

### 庫存未實現損益
- [x] UI 實裝：`render_account()` - 已實裝 ✓
- [x] 查詢函數：`query_positions("stock")` ✓

### 已實現損益
- [x] UI 實裝：`render_account()` - 已實裝 ✓
- [x] 查詢函數：`query_profit_loss(begin, end)` ✓

### 帳戶餘額
- [x] UI 實裝：`render_account()` - 已實裝 ✓
- [x] 查詢函數：`query_account_balance()` ✓

### 交易額度
- [x] UI 實裝：`render_account()` - 已實裝 ✓
- [x] 查詢函數：`query_trading_limits()` ✓

### 期貨保證金
- [x] UI 實裝：`render_account()` - 已實裝 ✓
- [x] 查詢函數：`query_margin()` ✓

### 交割款明細
- [x] UI 實裝：`render_account()` - 已實裝 ✓
- [x] 查詢函數：`query_settlements()` ✓

---

## 新聞（2項）

### 個股新聞
- [x] UI 實裝：`render_news()` - 已實裝
- [x] 查詢函數：`query_stock_news(code)` ✓

### 大盤新聞
- [x] UI 實裝：`render_news()` - 已實裝
- [x] 查詢函數：`query_market_news()` ✓

---

## FinMind 技術/籌碼面（8項）

### 三大法人明細
- [x] UI 實裝：`render_finmind()` - 已實裝
- [x] 查詢函數：`query_institutional_investors(code, start, end)` ✓

### 三大法人合計
- [x] UI 實裝：`render_finmind()` - 已實裝
- [x] 查詢函數：`query_institutional_summary(code, start, end)` ✓

### 當沖交易量
- [x] UI 實裝：`render_finmind()` - 已實裝
- [x] 查詢函數：`query_day_trading_volume(code, start, end)` ✓

### 融資融券餘額
- [x] UI 實裝：`render_finmind()` - 已實裝
- [x] 查詢函數：`query_margin_short(code, start, end)` ✓

### 外資持股比例
- [x] UI 實裝：`render_finmind()` - 已實裝
- [x] 查詢函數：`query_foreign_shareholding(code, start, end)` ✓

### 借券成交
- [x] UI 實裝：`render_finmind()` - 已實裝
- [x] 查詢函數：`query_securities_lending(code, start, end)` ✓

### 股價日K（FinMind）
- [x] UI 實裝：`render_finmind()` - 已實裝
- [x] 查詢函數：`query_daily_kbar_finmind(code, start, end)` ✓

### 本益比/股淨比/殖利率
- [x] UI 實裝：`render_finmind()` - 已實裝
- [x] 查詢函數：`query_per_pbr(code, start, end)` ✓

---

## FinMind 基本面（4項）

### 月營收
- [x] UI 實裝：`render_finmind()` - 已實裝
- [x] 查詢函數：`query_month_revenue(code, start, end)` ✓

### 綜合損益表
- [x] UI 實裝：`render_finmind()` - 已實裝
- [x] 查詢函數：`query_financial_statement(code, start, end)` ✓

### 資產負債表
- [x] UI 實裝：`render_finmind()` - 已實裝
- [x] 查詢函數：`query_balance_sheet(code, start, end)` ✓

### 股利政策
- [x] UI 實裝：`render_finmind()` - 已實裝
- [x] 查詢函數：`query_dividend(code, start, end)` ✓

---

## FinMind 期貨/匯率（3項）

### 期貨日行情
- [x] UI 實裝：`render_futures_forex()` - 已實裝
- [x] 查詢函數：`query_futures_daily(symbol, start, end)` ✓

### 期貨三大法人
- [x] UI 實裝：`render_futures_forex()` - 已實裝
- [x] 查詢函數：`query_futures_institutional(symbol, start, end)` ✓

### 台銀匯率
- [x] UI 實裝：`render_futures_forex()` - 已實裝
- [x] 查詢函數：`query_exchange_rate(currency, start, end)` ✓

---

## 富途 Futu OpenAPI（8項）

### 全球市場開收盤狀態
- [x] UI 實裝：`render_hk_us_stocks()` - 已實裝 ✓
- [x] 查詢函數：`query_futu_market_state()` ✓

### 港/美股日K
- [x] UI 實裝：`render_hk_us_stocks()` - 已實裝 ✓
- [x] 查詢函數：`query_futu_kbar(code, start, end)` ✓

### 股票基本資訊
- [x] UI 實裝：`render_hk_us_stocks()` - 已實裝 ✓
- [x] 查詢函數：`query_futu_basicinfo(market, codes)` ✓

### 資金分布
- [x] UI 實裝：`render_hk_us_stocks()` - 已實裝 ✓
- [x] 查詢函數：`query_futu_capital_distribution(code)` ✓

### 資金流向
- [x] UI 實裝：`render_hk_us_stocks()` - 已實裝 ✓
- [x] 查詢函數：`query_futu_capital_flow(code)` ✓

### 板塊列表
- [x] UI 實裝：`render_hk_us_stocks()` - 已實裝 ✓
- [x] 查詢函數：`query_futu_plate_list(market)` ✓

### 板塊成分股
- [x] UI 實裝：`render_hk_us_stocks()` - 已實裝 ✓
- [x] 查詢函數：`query_futu_plate_stocks(plate_code)` ✓

### 股票所屬板塊
- [x] UI 實裝：`render_hk_us_stocks()` - 已實裝 ✓
- [x] 查詢函數：`query_futu_owner_plate(codes)` ✓

---

## 證交所 TWSE OpenAPI（7項）

### 全市場當日行情
- [x] UI 實裝：`render_tools()` - 已實裝
- [x] 查詢函數：`query_twse_daily_all(code)` ✓

### 本益比/殖利率/股淨比
- [x] UI 實裝：`render_tools()` - 已實裝
- [x] 查詢函數：`query_twse_valuation(code)` ✓

### 三大法人（全市場）
- [x] UI 實裝：`render_tools()` - 已實裝
- [x] 查詢函數：`query_twse_institutional(code)` ✓

### 融資融券彙總
- [x] UI 實裝：`render_tools()` - 已實裝
- [x] 查詢函數：`query_twse_margin()` ✓

### 公司基本資料
- [x] UI 實裝：`render_tools()` - 已實裝
- [x] 查詢函數：`query_twse_company(code)` ✓

### 處置有價證券清單
- [x] UI 實裝：`render_tools()` - 已實裝
- [x] 查詢函數：`query_twse_disposition()` ✓

### 注意有價證券
- [x] UI 實裝：`render_tools()` - 已實裝
- [x] 查詢函數：`query_twse_notice()` ✓

---

## 摘要

| 類別 | 已實裝 | 待實裝 | 進度 |
|---|---|---|---|
| 台股市場 | 7/7 | 0 | ✅ 完成 |
| 帳務 | 6/6 | 0 | ✅ 完成 |
| 新聞 | 2/2 | 0 | ✅ 完成 |
| FinMind 技術 | 8/8 | 0 | ✅ 完成 |
| FinMind 基本面 | 4/4 | 0 | ✅ 完成 |
| FinMind 期貨/匯率 | 3/3 | 0 | ✅ 完成 |
| 富途 Futu | 8/8 | 0 | ✅ 完成 |
| 證交所 TWSE | 7/7 | 0 | ✅ 完成 |
| **總計** | **47/47** | **0** | **✅ 100% 完成** |

---

## 實施完成

### ✅ Phase 5 Task 18 — 全部菜單項目 UI 實裝完成

**新增實裝**（Task 18）
1. **帳務功能**（6項）
   - 庫存未實現損益
   - 已實現損益
   - 帳戶餘額
   - 交易額度
   - 期貨保證金
   - 交割款明細

2. **富途 Futu 港美股**（8項）
   - 全球市場開收盤狀態
   - 港/美股日K
   - 股票基本資訊
   - 資金分布
   - 資金流向
   - 板塊列表
   - 板塊成分股
   - 股票所屬板塊

### 下一步
3. 📊 **Phase 5 Task 19**：運行完整測試套件，驗證 >70% 代碼覆蓋率
4. 📈 **Phase 5 Task 20**：生成性能報告，對比 Phase 4 vs Phase 5 優化效果
