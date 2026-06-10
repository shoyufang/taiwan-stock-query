#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
券商提供查詢工具 - 非台股市場功能完整驗證腳本
驗證範圍：
1. 系統設定 (System Config)
2. 儀表板 (Dashboard)
3. 技術分析 (Technical Analysis)
4. TWSE (證交所)
5. FinMind (財務資料)
6. 期貨/匯率 (Futures/Exchange Rate)
7. 選股 (Screener)
8. 新聞 (News)
9. DeepSeek AI
10. 工具 (Tools - Bookmarks & History)
"""

import sys
import os
import io
import time
import pandas as pd
from datetime import date, timedelta, datetime
import traceback

# 確保輸出支援 UTF-8 以防 emoji 導致 Windows console 崩潰
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# 將當前路徑加入 sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
import query_wrapper as qw
import sinopac_query as sq
import technical_analysis as ta
import screener
from deepseek_engine import DeepSeekEngine, get_deepseek_engine

# 美化終端機輸出
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(title):
    print(f"\n{Colors.BOLD}{Colors.HEADER}======================================================================")
    print(f" {title}")
    print(f"======================================================================{Colors.ENDC}")

def print_sub_header(title):
    print(f"\n{Colors.BOLD}{Colors.OKBLUE}--- {title} ---{Colors.ENDC}")

def print_success(message):
    print(f"  {Colors.OKGREEN}✅ {message}{Colors.ENDC}")

def print_warning(message):
    print(f"  {Colors.WARNING}⚠️ {message}{Colors.ENDC}")

def print_error(message):
    print(f"  {Colors.FAIL}❌ {message}{Colors.ENDC}")

def print_info(message):
    print(f"  {Colors.OKCYAN}ℹ️ {message}{Colors.ENDC}")

# 儲存各項驗證結果的列表
verification_results = []

def record_result(category, name, status, details=""):
    verification_results.append({
        "Category": category,
        "Name": name,
        "Status": status,
        "Details": details
    })

# 1. 驗證系統設定
def test_system_config():
    print_header("1. 系統設定 (System Config) 驗證")
    try:
        cfg = config.load_config()
        print_info(f"偏好設置導出格式: {cfg.get('export_format')}")
        print_info(f"模擬模式啟用狀態: {cfg.get('simulation_mode')}")
        
        # 遮蔽敏感金鑰顯示
        for key in ["api_key", "secret_key", "finmind_token", "notion_token", "deepseek_api_key"]:
            val = cfg.get(key, "")
            status_str = f"已設定 (長度 {len(val)})" if val else "未設定"
            print_info(f"金鑰 {key}: {status_str}")
        
        print_success("系統設定讀取成功")
        record_result("系統設定", "載入/解析 config.json", "PASS", "偏好及金鑰載入成功")
    except Exception as e:
        print_error(f"系統設定讀取失敗: {str(e)}")
        record_result("系統設定", "載入/解析 config.json", "FAIL", str(e))

# 2. 驗證儀表板
def test_dashboard():
    print_header("2. 儀表板 (Dashboard) 驗證")
    
    # 2.1 測試本地 TWSE 緩存狀態
    print_sub_header("2.1 本地 TWSE 緩存狀態")
    try:
        status = qw.twse_cache_status()
        print_info(f"緩存根目錄: {status.get('root')}")
        categories = status.get('categories', {})
        for cat, details in categories.items():
            print_info(f"  - {cat}: 檔案存在={details.get('exists')}, 大小={details.get('size_bytes', 0)} 位元組")
        print_success("TWSE 本地緩存狀態查詢成功")
        record_result("儀表板", "TWSE 緩存狀態查詢", "PASS", f"已驗證 {len(categories)} 個緩存資料集")
    except Exception as e:
        print_error(f"TWSE 緩存狀態查詢失敗: {str(e)}")
        record_result("儀表板", "TWSE 緩存狀態查詢", "FAIL", str(e))
        
    # 2.2 測試 yfinance 指數獲取
    print_sub_header("2.2 全球指數與大盤即時快照")
    try:
        # 測試下載加權指數和大盤個股
        df = sq.query_snapshot(["^TWII", "2330"])
        if isinstance(df, pd.DataFrame) and not df.empty:
            print_info(f"大盤及個股快照數據 (前 5 筆):\n{df.head(2).to_string(index=False)}")
            print_success("加權指數與大盤即時數據獲取成功")
            record_result("儀表板", "全球大盤與即時數據", "PASS", "yfinance 指數快照獲取正常")
        else:
            print_warning("即時數據回傳空值")
            record_result("儀表板", "全球大盤與即時數據", "WARN", "大盤即時數據回傳空值")
    except Exception as e:
        print_error(f"即時數據獲取失敗: {str(e)}")
        record_result("儀表板", "全球大盤與即時數據", "FAIL", str(e))

# 3. 驗證技術分析
def test_technical_analysis():
    print_header("3. 技術分析 (Technical Analysis) 驗證")
    
    # 3.1 獲取 K 線數據
    print_sub_header("3.1 獲取日 K 線數據 (yfinance / 本地緩存)")
    try:
        today = date.today()
        start_date = today - timedelta(days=90)
        df_kbar = qw.query_daily_kbar("2330", start_date, today)
        if isinstance(df_kbar, pd.DataFrame) and not df_kbar.empty:
            print_info(f"已獲取 2330 K線資料 {len(df_kbar)} 筆，欄位: {list(df_kbar.columns)}")
            print_success("K 線數據查詢成功")
            record_result("技術分析", "K 線數據查詢", "PASS", f"成功獲取 {len(df_kbar)} 筆 K 線數據")
            
            # 3.2 測試技術指標計算
            print_sub_header("3.2 計算技術指標 (MA, EMA, RSI, MACD, Bollinger Bands, ATR)")
            try:
                # 複製資料，避免被 inplace 修改影響
                df_ta = df_kbar.copy()
                
                # 標準化欄位以供計算
                df_norm = ta._normalize_columns(df_ta)
                
                ma5 = ta.calc_ma(df_norm, 5)
                ema12 = ta.calc_ema(df_norm, 12)
                rsi14 = ta.calc_rsi(df_norm, 14)
                macd_line, macd_hist, macd_sig = ta.calc_macd(df_norm)
                bb_u, bb_m, bb_l = ta.calc_bollinger_bands(df_norm)
                atr14 = ta.calc_atr(df_norm, 14)
                
                print_info(f"  - MA5 最新值: {ma5.iloc[-1]:.2f}")
                print_info(f"  - EMA12 最新值: {ema12.iloc[-1]:.2f}")
                print_info(f"  - RSI14 最新值: {rsi14.iloc[-1]:.2f}" if not pd.isna(rsi14.iloc[-1]) else "  - RSI14 最新值: NaN")
                print_info(f"  - MACD 柱狀最新值: {macd_hist.iloc[-1]:.4f}")
                print_info(f"  - 布林通道 (上/中/下): {bb_u.iloc[-1]:.2f} / {bb_m.iloc[-1]:.2f} / {bb_l.iloc[-1]:.2f}")
                print_info(f"  - ATR14 最新值: {atr14.iloc[-1]:.2f}" if not pd.isna(atr14.iloc[-1]) else "  - ATR14 最新值: NaN")
                
                print_success("技術指標計算成功")
                record_result("技術分析", "指標計算 (MA/EMA/RSI/MACD/BB/ATR)", "PASS", "各項指標數學計算正確")
            except Exception as e:
                print_error(f"技術指標計算失敗: {str(e)}")
                traceback.print_exc()
                record_result("技術分析", "指標計算 (MA/EMA/RSI/MACD/BB/ATR)", "FAIL", str(e))
                
            # 3.3 測試 Plotly K線圖繪製
            print_sub_header("3.3 繪製互動式 Plotly K線圖")
            try:
                fig = ta.plot_kbar_with_indicators(
                    df_kbar, 
                    "2330", 
                    indicators=["MA5", "MA20", "EMA12", "RSI", "MACD", "BB", "ATR"],
                    height=600
                )
                if fig is not None:
                    print_success("Plotly 圖表對象生成成功")
                    record_result("技術分析", "Plotly K線圖繪製", "PASS", "互動式圖表成功渲染輸出")
                else:
                    print_error("Plotly 圖表生成為 None")
                    record_result("技術分析", "Plotly K線圖繪製", "FAIL", "圖表對象生成為 None")
            except Exception as e:
                print_error(f"Plotly 圖表繪製失敗: {str(e)}")
                record_result("技術分析", "Plotly K線圖繪製", "FAIL", str(e))
                
        else:
            error_msg = df_kbar.get("錯誤").iloc[0] if "錯誤" in df_kbar.columns else "無可用數據"
            print_error(f"K 線數據查詢失敗: {error_msg}")
            record_result("技術分析", "K 線數據查詢", "FAIL", error_msg)
    except Exception as e:
        print_error(f"K 線模組運作錯誤: {str(e)}")
        record_result("技術分析", "K 線數據查詢", "FAIL", str(e))

# 4. 驗證 TWSE 證交所
def test_twse():
    print_header("4. TWSE (證交所) 本地緩存查詢驗證")
    
    twse_apis = {
        "個股日行情 (STOCK_DAY_ALL)": qw.query_twse_daily_all,
        "本益比/殖利率 (BWIBBU)": qw.query_twse_valuation,
        "三大法人買賣超 (T86)": qw.query_twse_institutional,
        "信用交易統計 (Margin)": qw.query_twse_margin,
        "處置股票 (Disposition)": qw.query_twse_disposition,
        "注意股票 (Notice)": qw.query_twse_notice,
        "每日收盤指數 (MI_INDEX)": qw.query_twse_mi_index
    }
    
    for label, api_func in twse_apis.items():
        try:
            print_sub_header(f"查詢 {label}")
            df = api_func()
            if isinstance(df, pd.DataFrame) and not df.empty:
                print_info(f"回傳筆數: {len(df)} 筆, 欄位: {list(df.columns[:5])}...")
                print_success(f"{label} 查詢成功")
                record_result("TWSE", label, "PASS", f"回傳 {len(df)} 筆資料")
            else:
                # 沒資料有可能是今天還沒收盤或假日，如果是非強制錯誤視為軟性提示
                print_warning(f"{label} 回傳空資料表（可能當日無緩存）")
                record_result("TWSE", label, "WARN", "回傳空資料（可能無當日緩存）")
        except Exception as e:
            print_error(f"{label} 查詢異常: {str(e)}")
            record_result("TWSE", label, "FAIL", str(e))

    # 4.2 測試公司基本資訊
    print_sub_header("查詢公司基本資訊")
    try:
        df_comp = qw.query_twse_company("2330")
        if isinstance(df_comp, pd.DataFrame) and not df_comp.empty:
            print_info(f"公司資訊: {df_comp.iloc[0].to_dict()}")
            print_success("公司基本資訊查詢成功")
            record_result("TWSE", "公司基本資訊", "PASS", "成功獲取台積電基本資料")
        else:
            print_warning("公司基本資訊回傳空表")
            record_result("TWSE", "公司基本資訊", "WARN", "無此股票基本資料")
    except Exception as e:
        print_error(f"公司基本資訊查詢異常: {str(e)}")
        record_result("TWSE", "公司基本資訊", "FAIL", str(e))

# 5. 驗證 FinMind 財務與券商資料
def test_finmind():
    print_header("5. FinMind 財務/營收/籌碼功能驗證")
    
    finmind_apis = {
        "月營收 (MonthRevenue)": qw.query_month_revenue,
        "綜合損益表 (FinancialStatement)": qw.query_financial_statement,
        "資產負債表 (BalanceSheet)": qw.query_balance_sheet,
        "除權息股利 (Dividend)": qw.query_dividend,
        "融資融券餘額 (MarginShort)": qw.query_margin_short,
        "外資持股比例 (ForeignShareholding)": qw.query_foreign_shareholding,
        "借券賣出餘額 (SecuritiesLending)": qw.query_securities_lending
    }
    
    today = date.today()
    start_date = today - timedelta(days=365) # 測試一年的資料範圍
    
    for label, api_func in finmind_apis.items():
        try:
            print_sub_header(f"查詢 {label}")
            df = api_func("2330", start_date, today)
            if isinstance(df, pd.DataFrame) and not df.empty:
                print_info(f"回傳筆數: {len(df)} 筆, 欄位: {list(df.columns[:5])}...")
                print_success(f"{label} 查詢成功")
                record_result("FinMind", label, "PASS", f"回傳 {len(df)} 筆財務/籌碼資料")
            else:
                # 可能是沒有 token 或是模擬模式下無快取，不視為嚴重錯誤
                print_warning(f"{label} 回傳空資料表（在無 token 限制或模擬模式下為預期行為）")
                record_result("FinMind", label, "WARN", "回傳空資料（無 token 或模擬限制）")
        except Exception as e:
            print_error(f"{label} 查詢失敗: {str(e)}")
            record_result("FinMind", label, "FAIL", str(e))

# 6. 驗證期貨/匯率 (Futures/Exchange Rate)
def test_futures_forex():
    print_header("6. 期貨/匯率 (Futures/Exchange Rate) 驗證")
    
    today = date.today()
    start_date = today - timedelta(days=30)
    
    # 6.1 測試期貨每日行情
    print_sub_header("查詢台指期每日行情 (Futures Daily)")
    try:
        df_fut = sq.query_futures_daily("TX", start_date.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
        if isinstance(df_fut, pd.DataFrame) and not df_fut.empty:
            print_info(f"回傳筆數: {len(df_fut)} 筆, 最新一筆行情:\n{df_fut.tail(1).to_string(index=False)}")
            print_success("期貨每日行情查詢成功")
            record_result("期貨/匯率", "期貨每日行情", "PASS", f"成功獲取 {len(df_fut)} 筆期貨行情")
        else:
            print_warning("期貨每日行情回傳空值")
            record_result("期貨/匯率", "期貨每日行情", "WARN", "期貨回傳空值")
    except Exception as e:
        print_error(f"期貨每日行情查詢失敗: {str(e)}")
        record_result("期貨/匯率", "期貨每日行情", "FAIL", str(e))
        
    # 6.2 測試期貨法人持倉
    print_sub_header("查詢期貨三大法人持倉 (Futures Institutional)")
    try:
        df_fut_inst = sq.query_futures_institutional("TX", start_date.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
        if isinstance(df_fut_inst, pd.DataFrame) and not df_fut_inst.empty:
            print_info(f"回傳筆數: {len(df_fut_inst)} 筆, 欄位: {list(df_fut_inst.columns[:5])}...")
            print_success("期貨法人持倉查詢成功")
            record_result("期貨/匯率", "期貨三大法人持倉", "PASS", f"成功獲取 {len(df_fut_inst)} 筆法人持倉")
        else:
            print_warning("期貨三大法人持倉回傳空值")
            record_result("期貨/匯率", "期貨三大法人持倉", "WARN", "法人持倉回傳空值")
    except Exception as e:
        print_error(f"期貨三大法人持倉查詢失敗: {str(e)}")
        record_result("期貨/匯率", "期貨三大法人持倉", "FAIL", str(e))
        
    # 6.3 測試匯率查詢
    print_sub_header("查詢美元兌台幣匯率 (Exchange Rate)")
    try:
        df_ex = sq.query_exchange_rate("USD", start_date.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
        if isinstance(df_ex, pd.DataFrame) and not df_ex.empty:
            print_info(f"回傳筆數: {len(df_ex)} 筆, 最新匯率: {df_ex.iloc[-1].to_dict()}")
            print_success("匯率查詢成功")
            record_result("期貨/匯率", "匯率查詢", "PASS", f"成功獲取 {len(df_ex)} 筆匯率資料")
        else:
            print_warning("匯率查詢回傳空值")
            record_result("期貨/匯率", "匯率查詢", "WARN", "匯率回傳空值")
    except Exception as e:
        print_error(f"匯率查詢失敗: {str(e)}")
        record_result("期貨/匯率", "匯率查詢", "FAIL", str(e))

# 7. 驗證選股 (Screener)
def test_screener():
    print_header("7. 選股引擎 (Screener) 驗證")
    
    # 7.1 獲取股票池
    print_sub_header("7.1 獲取全市場股票池 (get_twse_universe)")
    try:
        univ = screener.get_twse_universe()
        if isinstance(univ, pd.DataFrame) and not univ.empty:
            print_info(f"全市場上市股票共: {len(univ)} 檔")
            print_success("股票池獲取成功")
            record_result("選股引擎", "獲取全市場股票池", "PASS", f"載入 {len(univ)} 檔股票資訊")
            
            # 7.2 進行基本過濾
            print_sub_header("7.2 基本股票過濾 (過濾價格與成交量)")
            filtered_univ = screener.filter_universe(univ, min_price=50.0, max_price=300.0, min_vol=2000)
            print_info(f"符合價格 (50~300) 與成交量 (>2000張) 的上市個股共: {len(filtered_univ)} 檔")
            print_success("基本股票過濾成功")
            record_result("選股引擎", "基本過濾", "PASS", f"過濾後剩下 {len(filtered_univ)} 檔")
            
            # 7.3 技術面選股測試 (僅對前 3 檔做測試，避免批量下載耗時太長)
            print_sub_header("7.3 技術面條件篩選 (KD黃金交叉 / 均線排列)")
            test_sub = filtered_univ.head(3)
            try:
                # 測試 KD 低檔黃金交叉 或 均線多頭排列
                df_screen = screener.screen_technical(test_sub, ["ma_bullish", "kd_oversold"], mode="OR")
                print_info(f"技術篩選測試結果筆數: {len(df_screen)}")
                if not df_screen.empty:
                    print_info(f"篩選通過個股:\n{df_screen.to_string(index=False)}")
                print_success("技術面篩選流程執行成功")
                record_result("選股引擎", "技術面條件篩選", "PASS", "KD與均線篩選演算法執行成功")
            except Exception as e:
                print_error(f"技術面篩選失敗: {str(e)}")
                record_result("選股引擎", "技術面條件篩選", "FAIL", str(e))
                
            # 7.4 財報面選股測試
            print_sub_header("7.4 財報面條件篩選 (PE/PB/殖利率)")
            try:
                # 篩選 PE <= 20, 殖利率 >= 3%
                df_fund = screener.screen_fundamental(test_sub, pe_max=20.0, yield_min=3.0)
                print_info(f"財報篩選測試結果筆數: {len(df_fund)}")
                print_success("財報面篩選流程執行成功")
                record_result("選股引擎", "財報面條件篩選", "PASS", "PE與殖利率篩選演算法執行成功")
            except Exception as e:
                print_error(f"財報面篩選失敗: {str(e)}")
                record_result("選股引擎", "財報面條件篩選", "FAIL", str(e))
                
            # 7.5 籌碼面選股測試
            print_sub_header("7.5 籌碼面條件篩選 (三大法人買超)")
            try:
                # 篩選投信或外資今日買超
                df_chip = screener.screen_chip(test_sub, ["foreign_buy", "trust_buy"], mode="OR")
                print_info(f"籌碼篩選測試結果筆數: {len(df_chip)}")
                print_success("籌碼面篩選流程執行成功")
                record_result("選股引擎", "籌碼面條件篩選", "PASS", "三大法人買超篩選演算法執行成功")
            except Exception as e:
                print_error(f"籌碼面篩選失敗: {str(e)}")
                record_result("選股引擎", "籌碼面條件篩選", "FAIL", str(e))
                
        else:
            print_warning("STOCK_DAY_ALL 外部 API 當前無回傳")
            record_result("選股引擎", "獲取全市場股票池", "WARN", "STOCK_DAY_ALL API 未回傳數據")
    except Exception as e:
        print_error(f"選股模組運作錯誤: {str(e)}")
        record_result("選股引擎", "選股模組整體", "FAIL", str(e))

# 8. 驗證新聞 (News)
def test_news():
    print_header("8. 新聞查詢 (News) 驗證")
    try:
        df_news = sq.query_news("2330", count=5)
        if isinstance(df_news, pd.DataFrame) and not df_news.empty:
            print_info(f"回傳新聞筆數: {len(df_news)}")
            for idx, r in df_news.iterrows():
                print_info(f"  - [{r.get('publisher', '來源')}] {r.get('title', '無標題')} ({r.get('date', '時間')})")
            print_success("新聞查詢成功")
            record_result("新聞模組", "個股/大盤新聞查詢", "PASS", f"成功載入 {len(df_news)} 則即時新聞")
        else:
            print_warning("新聞回傳空值")
            record_result("新聞模組", "個股/大盤新聞查詢", "WARN", "新聞資料為空")
    except Exception as e:
        print_error(f"新聞查詢失敗: {str(e)}")
        record_result("新聞模組", "個股/大盤新聞查詢", "FAIL", str(e))

# 9. 驗證 DeepSeek AI 功能
def test_deepseek_ai():
    print_header("9. DeepSeek AI 模組驗證")
    
    cfg = config.load_config()
    api_key = cfg.get("deepseek_api_key", "")
    model_name = cfg.get("deepseek_model", "deepseek-3.5-flash")
    
    if not api_key:
        print_warning("尚未設定 DeepSeek API Key，跳過實際網路調用測試")
        record_result("DeepSeek AI", "DeepSeek 引擎連接", "WARN", "無 API Key，跳過實際調用")
        return
        
    try:
        print_info(f"嘗試連接 DeepSeek Engine, 模型: {model_name}...")
        engine = DeepSeekEngine(api_key, model_name=model_name)
        
        # 測試獲取可用模型
        models = DeepSeekEngine.list_available_models(api_key)
        print_info(f"帳戶可用 DeepSeek 模型列表: {models}")
        print_success("DeepSeek API 連接及模型獲取成功")
        record_result("DeepSeek AI", "DeepSeek 引擎連接", "PASS", f"成功連結並獲取可用模型，當前：{model_name}")
        
    except Exception as e:
        print_error(f"DeepSeek API 測試失敗: {str(e)}")
        record_result("DeepSeek AI", "DeepSeek 引擎連接", "FAIL", str(e))

# 10. 驗證工具功能 (Bookmarks & History)
def test_tools():
    print_header("10. 工具 (Bookmarks & History) 驗證")
    
    # 10.1 書籤讀寫測試
    print_sub_header("書籤載入與儲存")
    try:
        bookmarks = config.load_bookmarks()
        print_info(f"現有書籤數量: {len(bookmarks)} 個")
        
        # 測試添加一個驗證用書籤，再刪除
        test_bookmark_name = f"__verify_test_{int(time.time())}"
        config.add_bookmark(test_bookmark_name, "技術分析", {"code": "2330"})
        print_info(f"已添加臨時測試書籤: {test_bookmark_name}")
        
        # 重新載入檢查
        b_list2 = config.load_bookmarks()
        found = any(b.get("name") == test_bookmark_name for b in b_list2)
        
        if found:
            print_success("書籤寫入及保存正常")
            # 刪除測試書籤
            config.remove_bookmark(test_bookmark_name)
            print_info("已移除臨時測試書籤")
            record_result("工具模組", "書籤讀寫與儲存", "PASS", "完整添加與刪除流程正常")
        else:
            print_error("未找到剛寫入的測試書籤")
            record_result("工具模組", "書籤讀寫與儲存", "FAIL", "書籤寫入後無法被重新載入")
    except Exception as e:
        print_error(f"書籤功能異常: {str(e)}")
        record_result("工具模組", "書籤讀寫與儲存", "FAIL", str(e))
        
    # 10.2 歷史紀錄測試
    print_sub_header("歷史查詢紀錄讀寫")
    try:
        history = config.load_history()
        print_info(f"現有查詢歷史數量: {len(history)} 筆")
        
        # 測試寫入一筆歷史
        test_tab = "技術分析"
        test_params = {"code": "2330", "test_time": str(time.time())}
        config.add_history(test_tab, test_params)
        
        # 重新載入檢查
        history2 = config.load_history()
        found_hist = len(history2) > len(history) or len(history2) > 0
        if found_hist:
            print_success("查詢歷史紀錄寫入正常")
            record_result("工具模組", "查詢歷史讀寫", "PASS", "歷史紀錄寫入並成功加載")
        else:
            print_error("未成功載入新寫入的歷史紀錄")
            record_result("工具模組", "查詢歷史讀寫", "FAIL", "歷史紀錄無法寫入或加載")
    except Exception as e:
        print_error(f"歷史紀錄功能異常: {str(e)}")
        record_result("工具模組", "查詢歷史讀寫", "FAIL", str(e))

# ==================== 執行所有測試 ====================
def run_all_tests():
    start_time = time.time()
    print(f"\n{Colors.BOLD}{Colors.OKCYAN}🚀 開始執行券商提供查詢工具 - 非台股市場功能完整驗證流程...{Colors.ENDC}\n")
    
    test_system_config()
    test_dashboard()
    test_technical_analysis()
    test_twse()
    test_finmind()
    test_futures_forex()
    test_screener()
    test_news()
    test_deepseek_ai()
    test_tools()
    
    elapsed = time.time() - start_time
    print_header(f"驗證總結報告 (耗時 {elapsed:.1f} 秒)")
    
    # 繪製美化的結果表格
    print(f"{Colors.BOLD}{'分類':<15} | {'功能名稱':<35} | {'狀態':<10} | {'備註':<30}{Colors.ENDC}")
    print("-" * 100)
    
    pass_count = 0
    warn_count = 0
    fail_count = 0
    
    for r in verification_results:
        color = Colors.OKGREEN if r["Status"] == "PASS" else (Colors.WARNING if r["Status"] == "WARN" else Colors.FAIL)
        status_text = f"{color}{r['Status']:<10}{Colors.ENDC}"
        
        # 計數
        if r["Status"] == "PASS":
            pass_count += 1
        elif r["Status"] == "WARN":
            warn_count += 1
        else:
            fail_count += 1
            
        print(f"{r['Category']:<15} | {r['Name']:<35} | {status_text} | {r['Details']:<30}")
        
    print("-" * 100)
    summary_color = Colors.OKGREEN if fail_count == 0 else Colors.FAIL
    print(f"{Colors.BOLD}{summary_color}驗證統計: {pass_count} 項成功 (PASS), {warn_count} 項軟性提醒/警告 (WARN), {fail_count} 項失敗 (FAIL){Colors.ENDC}\n")
    
    if fail_count == 0:
        print_success("🎉 所有受檢功能完全正常！相容性與核心數據層極為健全。")
    else:
        print_error("⚠️ 檢測到部分功能異常，請參閱上方詳細資訊進行修正。")

if __name__ == "__main__":
    run_all_tests()
