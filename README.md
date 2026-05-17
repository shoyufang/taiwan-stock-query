# 台股查詢工具

整合 TWSE OpenAPI、FinMind、yfinance、Gemini AI 的台股查詢 Streamlit 網頁應用。

## 分支說明

| 分支 | 用途 | 需要帳號 |
|------|------|----------|
| `main` | 公開版，Streamlit Cloud 部署用 | 無（FinMind/Gemini 選填）|
| `local` | 本機完整版，含永豐金即時報價 | 永豐金券商帳號 |

## 功能

- 📊 台股排行（漲跌/量/額）
- 🔍 個股報價、日K線（yfinance）
- 🏦 TWSE OpenAPI 全端點（48 項）
- 📈 FinMind 籌碼面/基本面/期貨/匯率
- 🌏 港美股查詢（yfinance）
- 🤖 Gemini AI 智能查詢 + Google Search

## 部署到 Streamlit Community Cloud

1. Fork 此 repo 或直接使用
2. 前往 [share.streamlit.io](https://share.streamlit.io)
3. New app → 選擇此 repo，branch: `main`，main file: `app.py`
4. 在 **App Settings > Secrets** 填入（選填，不填仍可使用大部分功能）：

```toml
FINMIND_TOKEN = "你的 FinMind Token"
GEMINI_API_KEY = "你的 Gemini API Key"
GEMINI_MODEL   = "gemini-2.5-flash-preview-05-20"
```

5. Deploy

## 本機執行

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 取得 API 金鑰

- **FinMind**：[finmindtrade.com](https://finmindtrade.com)（免費註冊）
- **Gemini**：[aistudio.google.com](https://aistudio.google.com)（免費額度）
