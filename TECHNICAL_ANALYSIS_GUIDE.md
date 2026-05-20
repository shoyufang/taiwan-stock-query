# 技術分析模組使用指南

## 概述

`technical_analysis.py` 是一個 **Plotly 互動式圖表模組**，提供專業的 K 線圖繪製與多種技術指標支援。

**特色：**
- 🎨 **互動式圖表**：放大/縮小、懸停提示、日期拖拉
- 📊 **多指標支援**：MA、EMA、RSI、MACD、布林帶、ATR
- 🔗 **Streamlit 整合**：無縫集成網頁應用
- ⚡ **高效計算**：Pandas 向量化運算
- 🎯 **台股慣例**：漲紅跌綠，符合台灣市場習慣

---

## 核心函數

### 1. 技術指標計算函數

#### `calc_ma(df, window=20, col="close")`
計算簡單移動平均線（SMA）

```python
ma_20 = ta.calc_ma(df, window=20)
```

**參數：**
- `df`：DataFrame，包含 OHLCV 數據
- `window`：週期（預設 20）
- `col`：計算欄位（預設 "close"）

**回傳：** Series，MA 值序列

---

#### `calc_ema(df, window=12, col="close")`
計算指數移動平均線（EMA）

```python
ema_12 = ta.calc_ema(df, window=12)
```

**參數：** 同上

**回傳：** Series，EMA 值序列

---

#### `calc_rsi(df, window=14, col="close")`
計算相對強度指標（RSI）

```python
rsi = ta.calc_rsi(df, window=14)
```

**參數：** 同上（window 預設 14）

**回傳：** Series，RSI 值序列（0-100）

---

#### `calc_macd(df, fast=12, slow=26, signal=9, col="close")`
計算 MACD（Moving Average Convergence Divergence）

```python
macd, signal, histogram = ta.calc_macd(df)
```

**參數：**
- `fast`：快速 EMA 週期（預設 12）
- `slow`：慢速 EMA 週期（預設 26）
- `signal`：信號線週期（預設 9）

**回傳：** 三元組 `(macd_line, signal_line, histogram)`

---

#### `calc_bollinger_bands(df, window=20, num_std=2.0, col="close")`
計算布林帶（Bollinger Bands）

```python
middle, upper, lower = ta.calc_bollinger_bands(df)
```

**參數：**
- `window`：週期（預設 20）
- `num_std`：標準差倍數（預設 2.0）

**回傳：** 三元組 `(middle_band, upper_band, lower_band)`

---

#### `calc_atr(df, window=14)`
計算真實波幅（Average True Range）

```python
atr = ta.calc_atr(df, window=14)
```

**參數：** `window` - 週期（預設 14）

**回傳：** Series，ATR 值序列

---

### 2. 主繪圖函數

#### `plot_kbar_with_indicators(df, code, indicators=None, title=None, height=700)`
繪製 K 線圖 + 技術指標（多行子圖）

```python
import technical_analysis as ta

# 取得 K 線數據
df = qw.query_daily_kbar("2330", date(2025, 1, 1), date(2026, 5, 20))

# 繪製 K 線 + 指標
fig = ta.plot_kbar_with_indicators(
    df,
    "2330",
    indicators=["MA5", "MA20", "RSI", "MACD", "BB"],
    height=800
)

# 在 Streamlit 中顯示
import streamlit as st
st.plotly_chart(fig, use_container_width=True)
```

**參數：**
- `df`：DataFrame，必須包含 `open`, `high`, `low`, `close`, `volume` 欄位
  * 支援欄位別名：「開盤」→ `open`、「收盤」→ `close` 等
- `code`：股票代號（用於標題）
- `indicators`：指標列表，支援值如下：
  * `"MA5"`, `"MA10"`, `"MA20"`, `"MA60"`, `"MA120"`
  * `"EMA5"`, `"EMA10"`, `"EMA12"`, `"EMA26"`
  * `"RSI"`
  * `"MACD"`
  * `"BB"`（布林帶）
  * `"ATR"`
- `title`：自訂標題（預設："{code} 技術分析"）
- `height`：圖表高度（px，預設 700）

**回傳：** Plotly `go.Figure` 物件

**圖表構成：**
1. **第 1 列**：K 線 + 成交量 + MA/EMA + 布林帶
2. **第 2 列**（如含 RSI）：RSI 曲線 + 70/30 參考線
3. **第 3 列**（如含 MACD）：MACD 線 + 信號線 + Histogram 柱狀圖

---

### 3. 快捷函數

#### `quick_chart(code, df, indicators=None)`
一行快速繪製 K 線圖（預設指標：MA5、MA20、RSI）

```python
fig = ta.quick_chart("2330", df)
st.plotly_chart(fig, use_container_width=True)
```

**參數：** 同上（簡化版）

---

## 使用範例

### 範例 1：基礎 K 線圖

```python
import technical_analysis as ta
import query_wrapper as qw
from datetime import date

# 取得數據
df = qw.query_daily_kbar("2330", date(2025, 1, 1), date(2026, 5, 20))

# 繪製簡單 K 線圖 + MA
fig = ta.plot_kbar_with_indicators(df, "2330", indicators=["MA20"])
```

### 範例 2：完整技術分析

```python
# 多指標組合
fig = ta.plot_kbar_with_indicators(
    df,
    "2330",
    indicators=["MA5", "MA20", "EMA12", "RSI", "MACD", "BB"],
    height=900
)
```

### 範例 3：Streamlit 應用集成

```python
import streamlit as st
import technical_analysis as ta
import query_wrapper as qw
from datetime import date

# 使用者輸入
code = st.text_input("股票代號", "2330")
indicators = st.multiselect("指標", ["MA5", "MA20", "RSI", "MACD", "BB"], default=["MA20"])

if st.button("繪製"):
    df = qw.query_daily_kbar(code, date(2025, 1, 1), date(2026, 5, 20))
    fig = ta.plot_kbar_with_indicators(df, code, indicators=indicators)
    st.plotly_chart(fig, use_container_width=True)
```

---

## Streamlit Web 應用中的技術分析 Tab

應用程式在 **`app.py`** 中已集成「技術分析」Tab（通過 `render_technical_analysis()` 函數）。

**使用方式：**

```bash
streamlit run app.py
```

在側邊欄點選「📊 台股市場」下的「技術分析」Tab。

**UI 功能：**
1. **股票代號輸入**：支援單一股票代號
2. **圖表類型選擇**：日K（預設）、分鐘K（開發中）
3. **日期範圍**：開始日期、結束日期
4. **指標多選**：複選框動態選擇
5. **參數調整**：MA/EMA 週期多選
6. **統計面板**：收盤價、漲跌、成交量

---

## 資料格式要求

### DataFrame 欄位

最少需要以下欄位之一（大小寫不敏感）：

| 欄位（英文） | 欄位（中文） | 說明 |
|---|---|---|
| `open` | `開盤` | 開盤價 |
| `high` | `最高` | 最高價 |
| `low` | `最低` | 最低價 |
| `close` | `收盤` | 收盤價 |
| `volume` | `成交量` | 成交量（股） |

### 索引

建議使用 **DatetimeIndex**（自動處理）：

```python
df.index = pd.to_datetime(df.index)
```

---

## 色彩方案

| 元素 | 色彩 | 說明 |
|---|---|---|
| 漲 | 紅色 (#d32f2f) | 收盤 > 開盤 |
| 跌 | 綠色 (#1976d2) | 收盤 < 開盤 |
| MA 5 | 橙色 (#ff9800) | 短期趨勢 |
| MA 20 | 藍色 (#1976d2) | 中期趨勢 |
| MA 60 | 紫色 (#9c27b0) | 長期趨勢 |
| BB 上軌 | 淡紅色 | 超買區 |
| BB 下軌 | 淡綠色 | 超賣區 |
| RSI 70 | 紅虛線 | 超買線 |
| RSI 30 | 綠虛線 | 超賣線 |

---

## 常見問題

**Q: 能否同時顯示多個技術指標？**  
A: 可以。指標列表支援任意組合。但建議：
- **子圖自動佈置**：RSI、MACD 各佔一行，MA/BB 共享 K 線行
- **過多指標會擁擠**：建議不超過 3-4 個主指標

**Q: 資料最遠可以回溯多久？**  
A: 取決於資料來源：
- Shioaji：2020 年起
- FinMind：1994 年起
- TWSE：不同資料集有不同覆蓋期

**Q: 支援期貨、外匯或 ETF 嗎？**  
A: 支援。只要提供 OHLCV 資料即可。期貨代號例：`TX`（台指期）

**Q: 能否自訂顏色或樣式？**  
A: 目前為內置樣式。若需自訂，修改 `plot_kbar_with_indicators()` 內的 Plotly 設定。

---

## 性能建議

| 場景 | 建議 |
|---|---|
| 即時報價（1分K） | 限制在 1-2 小時範圍內（≤120 根K線） |
| 中期分析（日K） | 推薦 3-6 個月範圍（≤180 根K線） |
| 長期分析 | 1-5 年範圍可接受（>500 根K線 時會稍慢） |
| 超多指標 | 4+ 個指標時，建議使用 `@st.cache_data` 快取結果 |

---

## 未來增強

- [ ] 分鐘 K 線支援
- [ ] 成交量加權指標（OBV、CMF）
- [ ] 帝江交易指標（DMI、ADX）
- [ ] 回測架構整合
- [ ] 指標警示設定

---

## 參考資源

- **Plotly 文件**：https://plotly.com/python/candlestick-charts/
- **Streamlit 文件**：https://docs.streamlit.io/
- **技術分析基礎**：台灣證交所、XQ 教學資源

---

**最後更新：2026-05-20**  
**版本：Phase 7.5**
