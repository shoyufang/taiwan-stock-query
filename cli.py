"""
命令列介面互動模組 — 負責終端互動選單、智能查詢路由與快速決策指南。
所有資料查詢呼叫均轉發至 datasources 客戶端套件。
"""

import pandas as pd
from datetime import date, timedelta
from datasources import (
    query_scanner,
    query_snapshot,
    query_kbars,
    query_ticks,
    query_positions,
    query_profit_loss,
    query_account_balance,
    query_trading_limits,
    query_margin,
    query_settlements,
    print_news,
    query_institutional,
    query_institutional_summary,
    query_daily_kbar_finmind,
    query_per_pbr,
    query_day_trading,
    query_margin_short,
    query_shareholding,
    query_securities_lending,
    query_month_revenue,
    query_financial_statement,
    query_balance_sheet,
    query_dividend,
    query_futures_daily,
    query_futures_institutional,
    query_exchange_rate,
    query_twse_daily_all,
    query_twse_bwibbu,
    query_twse_institutional,
    query_twse_margin,
    query_twse_company,
    query_twse_disposition,
    query_twse_notice,
    query_futu_market_state,
    query_futu_kbar,
    query_futu_basicinfo,
    query_futu_capital_distribution,
    query_futu_capital_flow,
    query_futu_plate_list,
    query_futu_plate_stocks,
    query_futu_owner_plate,
)

# 格式：(關鍵字列表, 選單號碼, 說明, 需要代號?)
_ROUTES = [
    # ── 台股即時（Shioaji）──────────────────────────────
    (["漲幅", "漲停", "漲最多", "漲榜", "漲幅排行"],         "1",  "漲幅排行",         False),
    (["跌幅", "跌停", "跌最多", "跌榜", "跌幅排行"],         "2",  "跌幅排行",         False),
    (["成交量排行", "量排行", "爆量"],                        "3",  "成交量排行",       False),
    (["成交金額排行", "金額排行"],                            "4",  "成交金額排行",     False),
    (["即時", "快照", "現價", "報價", "現在股價"],            "5",  "個股即時快照",     True),
    (["K線", "日K", "走勢", "歷史行情", "台股K"],            "6",  "台股K線（Shioaji）", True),
    (["逐筆", "tick", "每筆成交"],                            "7",  "個股逐筆成交",     True),
    # ── 帳務 ────────────────────────────────────────────
    (["庫存", "持倉", "未實現損益"],                          "8",  "庫存未實現損益",   False),
    (["已實現", "出場損益"],                                  "9",  "已實現損益",       False),
    (["帳戶餘額", "可動用", "現金"],                          "10", "帳戶餘額",         False),
    # ── 新聞 ────────────────────────────────────────────
    (["新聞", "消息", "報導"],                                "14", "個股/大盤新聞",    True),
    # ── FinMind 籌碼/技術 ────────────────────────────────
    (["三大法人歷史", "法人歷史", "外資歷史"],                "16", "三大法人明細（歷史）", True),
    (["法人合計", "累計買超", "法人趨勢"],                    "17", "三大法人合計+累計", True),
    (["本益比歷史", "PER歷史", "股淨比歷史", "殖利率歷史"],  "19", "本益比/殖利率（歷史）", True),
    (["當沖"],                                                "20", "當沖交易量",       True),
    (["融資融券歷史", "資券歷史"],                            "21", "融資融券（歷史）", True),
    (["外資持股", "外資比例"],                                "22", "外資持股比例",     True),
    (["借券"],                                                "23", "借券成交",         True),
    # ── FinMind 基本面 ───────────────────────────────────
    (["月營收", "營收"],                                      "24", "月營收",           True),
    (["損益表", "獲利", "EPS", "淨利", "營業利益"],          "25", "綜合損益表",       True),
    (["資產", "負債", "淨值", "資產負債"],                    "26", "資產負債表",       True),
    (["股利", "股息", "配息", "除息", "除權"],                "27", "股利政策",         True),
    # ── FinMind 期貨/匯率 ────────────────────────────────
    (["台指期", "期貨行情", "TX", "小台", "MTX"],             "28", "期貨日行情",       False),
    (["期貨法人", "期貨三大法人", "期貨外資"],                "29", "期貨三大法人",     False),
    (["匯率", "外幣", "USD", "JPY", "EUR", "美元", "日圓"],  "30", "匯率查詢",         False),
    # ── TWSE 今日全市場 ──────────────────────────────────
    (["今日行情", "全市場行情", "所有股票", "上市行情"],      "41", "全市場當日行情（TWSE）", False),
    (["今日本益比", "今日殖利率", "全市場本益比"],            "42", "本益比/殖利率—今日全市場（TWSE）", False),
    (["今日法人", "今日三大法人", "法人今天", "今天法人"],    "43", "三大法人—今日全市場（TWSE）", False),
    (["今日融資", "今日融券", "融資今天", "融券今天"],        "44", "融資融券彙總今日（TWSE）", False),
    (["公司資料", "基本資料", "公司簡介", "股票資料"],        "45", "公司基本資料（TWSE）", True),
    (["處置", "處置股", "分盤", "禁止當沖", "處置有價證券"], "46", "處置有價證券（TWSE）", False),
    (["注意股", "注意有價證券", "警示", "注意交易"],          "47", "注意有價證券（TWSE）", False),
    # ── Futu 港美股 ─────────────────────────────────────
    (["港股", "HK.", "香港股", "騰訊", "阿里"],              "32", "港股K線（Futu）",  False),
    (["美股", "US.", "蘋果", "特斯拉", "AAPL", "TSLA"],     "32", "美股K線（Futu）",  False),
    (["全球市場", "市場開市", "開市狀態"],                    "31", "全球市場狀態（Futu）", False),
    (["板塊", "行業", "產業分類", "類股"],                    "36", "板塊列表（Futu）", False),
    (["資金分布", "大戶資金", "主力資金"],                    "34", "資金分布（Futu）", False),
    (["資金流向", "分鐘資金"],                                "35", "資金流向（Futu）", False),
]


def smart_query(question: str) -> list:
    """
    根據描述推薦最適合的查詢選項。
    傳回 [(選單號碼, 說明, 需要代號?), ...]，依命中關鍵字數量排序。
    """
    matches = {}  # choice → (score, desc, need_code)
    for keywords, choice, desc, need_code in _ROUTES:
        score = sum(1 for kw in keywords if kw in question)
        if score > 0:
            if choice not in matches or score > matches[choice][0]:
                matches[choice] = (score, desc, need_code)
    # 依分數由高到低排序
    ranked = sorted(matches.items(), key=lambda x: -x[1][0])
    return [(c, info[1], info[2]) for c, info in ranked]


# ── 決策速查表（給使用者參考）──────────────────────────────
DECISION_GUIDE = """
┌─────────────────────────────────────────────────────────────────────┐
│  📌  快速決策：我要查什麼 → 用哪個工具？                            │
├────────────────┬────────────────────────────────────────────────────┤
│  今日 / 即時   │  台股排行/快照/K線/逐筆 → 1~7（Shioaji）          │
│                │  今日全市場行情/法人/融資 → 41~44（TWSE）          │
│                │  港美股即時行情 → 需訂閱（Futu 受限）              │
├────────────────┼────────────────────────────────────────────────────┤
│  歷史 / 趨勢   │  法人/融資/外資/借券/當沖 → 16~23（FinMind）      │
│                │  月營收/損益表/資產負債/股利 → 24~27（FinMind）    │
│                │  港美股K線（歷史） → 32（Futu）                    │
│                │  台股K線（歷史） → 6（Shioaji）或 18（FinMind）    │
├────────────────┼────────────────────────────────────────────────────┤
│  評價指標      │  本益比/殖利率—今日全市場 → 42（TWSE）             │
│                │  本益比/殖利率—個股歷史 → 19（FinMind）            │
├────────────────┼────────────────────────────────────────────────────┤
│  期貨 / 匯率   │  台指期行情 → 28（FinMind）                        │
│                │  期貨三大法人 → 29（FinMind）                      │
│                │  匯率 → 30（FinMind）                              │
├────────────────┼────────────────────────────────────────────────────┤
│  港股 / 美股   │  K線 → 32  資金分布 → 34  板塊 → 36~38（Futu）    │
├────────────────┼────────────────────────────────────────────────────┤
│  公司資料      │  基本資料 → 45（TWSE）                             │
│  新聞          │  個股/大盤新聞 → 14/15（yfinance）                 │
│  帳務          │  庫存/損益/餘額 → 8~13（需CA憑證）                 │
└────────────────┴────────────────────────────────────────────────────┘"""


# 互動式選單
MENU = """
╔══════════════════════════════════╦══════════════════════════════════╦══════════════════════════════════╗
║  【台股市場】不需CA              ║  【FinMind 籌碼/技術面】         ║  【富途 Futu OpenAPI】            ║
║   1. 漲幅排行                    ║  16. 三大法人明細                ║  需FutuOpenD運行中               ║
║   2. 跌幅排行                    ║  17. 三大法人合計+累計           ║  31. 全球市場狀態                ║
║   3. 成交量排行                  ║  18. 股價日K                     ║  32. 港/美股K線                  ║
║   4. 成交金額排行                ║  19. 本益比/股淨比/殖利率        ║  33. 股票基本資訊                ║
║   5. 個股即時快照                ║  20. 當沖交易量                  ║  34. 資金分布（大中小散）        ║
║   6. 個股K線                     ║  21. 融資融券                    ║  35. 資金流向（分鐘）            ║
║   7. 個股逐筆成交                ║  22. 外資持股比例                ║  36. 板塊列表                    ║
║  【帳務】需CA憑證                ║  23. 借券成交                    ║  37. 板塊股票                    ║
║   8. 庫存未實現損益              ║  【FinMind 基本面】              ║  38. 股票所屬板塊                ║
║   9. 已實現損益                  ║  24. 月營收                      ║  【證交所 TWSE】免費無金鑰       ║
║  10. 帳戶餘額                    ║  25. 綜合損益表                  ║  41. 全市場當日行情               ║
║  11. 交易額度                    ║  26. 資產負債表                  ║  42. 本益比/殖利率/股淨比        ║
║  12. 期貨保證金                  ║  27. 股利政策                    ║  43. 三大法人（全市場）           ║
║  13. 交割款明細                  ║  【FinMind 期貨/匯率】           ║  44. 融資融券彙總                 ║
║  【新聞】不需帳號                ║  28. 期貨日行情                  ║  45. 公司基本資料                 ║
║  14. 個股新聞                    ║  29. 期貨三大法人                ║   ?. 智能查詢                    ║
║  15. 大盤新聞                    ║  30. 匯率查詢                    ║   0. 離開                        ║
║                                  ║                                  ║  46. 處置有價證券                ║
║                                  ║                                  ║  47. 注意有價證券                ║
╚══════════════════════════════════╩══════════════════════════════════╩══════════════════════════════════╝"""


def _input(prompt: str, default=None):
    val = input(prompt).strip()
    return val if val else default


def main():
    while True:
        print(MENU)
        choice = input("請選擇功能（? 智能查詢 / g 決策指南）：").strip()

        # ── 決策指南 ─────────────────────────────────────────
        if choice in ("g", "G", "guide"):
            print(DECISION_GUIDE)
            input("\n按 Enter 返回選單...")
            continue

        # ── 智能查詢 ─────────────────────────────────────────
        if choice in ("?", "？", "s"):
            q = input("描述你要查的資料（如：2330今日融資、外資今天買超）：").strip()
            hits = smart_query(q)
            if not hits:
                print("  找不到符合的查詢，請直接輸入選單號碼。")
                input("\n按 Enter 返回選單...")
                continue
            print("\n  推薦查詢方式：")
            for i, (c, d, _) in enumerate(hits[:6], 1):
                print(f"  [{i}] 選單 {c:>2}  {d}")
            pick = input("\n  輸入編號立即執行（Enter 返回選單）：").strip()
            if pick.isdigit() and 1 <= int(pick) <= len(hits[:6]):
                choice = hits[int(pick) - 1][0]
            elif not pick:
                continue
            else:
                choice = pick  # 使用者直接輸入選單號碼

        if choice == "1":
            n = int(_input("筆數（預設10）：", "10"))
            d = _input("日期 YYYY-MM-DD（預設今日）：", None)
            df = query_scanner("ChangePercentRank", ascending=True, query_date=d, count=n)
            print(df.to_string(index=False))
        elif choice == "2":
            n = int(_input("筆數（預設10）：", "10"))
            d = _input("日期 YYYY-MM-DD（預設今日）：", None)
            df = query_scanner("ChangePercentRank", ascending=False, query_date=d, count=n)
            print(df.to_string(index=False))
        elif choice == "3":
            n = int(_input("筆數（預設10）：", "10"))
            d = _input("日期 YYYY-MM-DD（預設今日）：", None)
            df = query_scanner("VolumeRank", ascending=True, query_date=d, count=n)
            print(df.to_string(index=False))
        elif choice == "4":
            n = int(_input("筆數（預設10）：", "10"))
            d = _input("日期 YYYY-MM-DD（預設今日）：", None)
            df = query_scanner("AmountRank", ascending=True, query_date=d, count=n)
            print(df.to_string(index=False))
        elif choice == "5":
            codes = _input("股票代號（逗號分隔，如 2330,2317）：", "2330").split(",")
            codes = [c.strip() for c in codes]
            df = query_snapshot(codes)
            print(df.to_string(index=False))
        elif choice == "6":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期 YYYY-MM-DD：", str(date.today() - timedelta(days=30)))
            end   = _input("結束日期 YYYY-MM-DD（預設今日）：", None)
            df = query_kbars(code, start, end)
            print(df.tail(20).to_string())
        elif choice == "7":
            code = _input("股票代號（如 2330）：", "2330")
            d    = _input("日期 YYYY-MM-DD：", str(date.today()))
            last = _input("只取最後 N 筆（不填則取全日）：", None)
            df = query_ticks(code, d, last_cnt=int(last) if last else None)
            print(df.tail(20).to_string())
        elif choice == "8":
            t = _input("帳戶類型 stock/future（預設 stock）：", "stock")
            df = query_positions(t)
            print("無庫存部位" if df.empty else df.to_string(index=False))
        elif choice == "9":
            t = _input("帳戶類型 stock/future（預設 stock）：", "stock")
            b = _input("開始日期（預設今日）：", str(date.today()))
            e = _input("結束日期（預設今日）：", str(date.today()))
            df = query_profit_loss(b, e, t)
            print("查無損益資料" if df.empty else df.to_string(index=False))
        elif choice == "10":
            print(query_account_balance())
        elif choice == "11":
            print(query_trading_limits())
        elif choice == "12":
            print(query_margin())
        elif choice == "13":
            print(query_settlements().to_string(index=False))
        elif choice == "14":
            code = _input("股票代號（如 2330）：", "2330")
            n    = int(_input("筆數（預設10）：", "10"))
            print_news(code, n)
        elif choice == "15":
            n = int(_input("筆數（預設10）：", "10"))
            print_news(None, n)
        elif choice == "16":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期（預設近30天）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_institutional(code, start, end).to_string(index=False))
        elif choice == "17":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期（預設近30天）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_institutional_summary(code, start, end).to_string(index=False))
        elif choice == "18":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期（預設近60天）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_daily_kbar_finmind(code, start, end).to_string(index=False))
        elif choice == "19":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期（預設近60天）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_per_pbr(code, start, end).to_string(index=False))
        elif choice == "20":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期（預設近30天）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_day_trading(code, start, end).to_string(index=False))
        elif choice == "21":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期（預設近30天）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_margin_short(code, start, end).to_string(index=False))
        elif choice == "22":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期（預設近90天）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_shareholding(code, start, end).to_string(index=False))
        elif choice == "23":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期（預設近30天）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_securities_lending(code, start, end).to_string(index=False))
        elif choice == "24":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期（預設2025-01-01）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_month_revenue(code, start, end).to_string(index=False))
        elif choice == "25":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期（預設2024-01-01）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_financial_statement(code, start, end).to_string(index=False))
        elif choice == "26":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期（預設2024-01-01）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_balance_sheet(code, start, end).to_string(index=False))
        elif choice == "27":
            code  = _input("股票代號（如 2330）：", "2330")
            start = _input("開始日期（預設2015-01-01）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_dividend(code, start, end).to_string(index=False))
        elif choice == "28":
            code  = _input("期貨代號（TX=台指/MTX=小台，預設TX）：", "TX")
            start = _input("開始日期（預設近30天）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_futures_daily(code, start, end).to_string(index=False))
        elif choice == "29":
            code  = _input("期貨代號（TX=台指，預設TX）：", "TX")
            start = _input("開始日期（預設近30天）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_futures_institutional(code, start, end).to_string(index=False))
        elif choice == "30":
            cur   = _input("幣別（USD/JPY/EUR/CNY/HKD，預設USD）：", "USD")
            start = _input("開始日期（預設近30天）：", None)
            end   = _input("結束日期（預設今日）：", None)
            print(query_exchange_rate(cur, start, end).to_string(index=False))
        elif choice == "41":
            code = _input("篩選代號（不填則查全市場）：", None)
            df = query_twse_daily_all(code)
            print(df.to_string(index=False))
        elif choice == "42":
            code = _input("篩選代號（不填則查全市場）：", None)
            df = query_twse_bwibbu(code)
            print(df.to_string(index=False))
        elif choice == "43":
            code = _input("篩選代號（不填則查全市場）：", None)
            df = query_twse_institutional(code)
            print(df.to_string(index=False))
        elif choice == "44":
            print(query_twse_margin().to_string(index=False))
        elif choice == "45":
            code = _input("股票代號（如 2330）：", "2330")
            print(query_twse_company(code).to_string(index=False))
        elif choice == "46":
            df = query_twse_disposition()
            if df.empty:
                print("目前無處置有價證券")
            else:
                pd.set_option("display.max_colwidth", 30)
                print(df.to_string(index=False))
        elif choice == "47":
            df = query_twse_notice()
            if df.empty:
                print("今日無注意有價證券")
            else:
                print(df.to_string(index=False))
        elif choice == "31":
            print(query_futu_market_state().to_string(index=False))
        elif choice == "32":
            code  = _input("代碼（如 HK.00700 / US.AAPL）：", "HK.00700")
            start = _input("開始日期 YYYY-MM-DD：", str(date.today() - timedelta(days=30)))
            end   = _input("結束日期（預設今日）：", None)
            print(query_futu_kbar(code, start, end).to_string(index=False))
        elif choice == "33":
            mkt   = _input("市場 HK/US/SH/SZ（預設HK）：", "HK")
            raw   = _input("代碼逗號分隔（不填查全市場）：", None)
            codes = [c.strip() for c in raw.split(",")] if raw else []
            print(query_futu_basicinfo(mkt, codes).to_string(index=False))
        elif choice == "34":
            code = _input("代碼（如 HK.00700 / US.TSLA）：", "HK.00700")
            print(query_futu_capital_distribution(code).to_string(index=False))
        elif choice == "35":
            code = _input("代碼（如 HK.00700 / US.TSLA）：", "HK.00700")
            print(query_futu_capital_flow(code).to_string(index=False))
        elif choice == "36":
            mkt = _input("市場 HK/US（預設HK）：", "HK")
            print(query_futu_plate_list(mkt).to_string(index=False))
        elif choice == "37":
            pc = _input("板塊代碼（從選單36取得，如 HK.LIST1003）：", "HK.LIST1003")
            print(query_futu_plate_stocks(pc).to_string(index=False))
        elif choice == "38":
            raw = _input("代碼逗號分隔（如 HK.00700,US.AAPL）：", "HK.00700,US.AAPL")
            codes = [c.strip() for c in raw.split(",")]
            print(query_futu_owner_plate(codes).to_string(index=False))
        elif choice == "0":
            print("離開")
            break
        else:
            print("無效選項")

        input("\n按 Enter 返回選單...")


if __name__ == "__main__":
    main()
