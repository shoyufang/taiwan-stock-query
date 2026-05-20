#!/usr/bin/env python3
"""
台股每日自動抓取 → 存入 Notion + 存 CSV 本地快取
每個交易日 20:05 台灣時間由 GitHub Actions 觸發（UTC 12:05）

GitHub Secrets 需設定：
  NOTION_TOKEN          — Notion Integration Token
  NOTION_MARKET_DB_ID   — 每日大盤快照 Database ID
  NOTION_SCREENER_DB_ID — 選股紀錄 Database ID
  FINMIND_TOKEN         — FinMind API Token（選填）
  GMAIL_USER            — 寄件 Gmail 帳號
  GMAIL_APP_PASSWORD    — Gmail 應用程式密碼
  NOTIFY_EMAIL          — 收件地址（預設同 GMAIL_USER）

TWSE 每日資料快取目錄（data/twse/）：
  daily_all/    — 全市場當日行情（STOCK_DAY_ALL）
  institutional/ — 三大法人（T86）
  valuation/    — 本益比/殖利率/股淨比（BWIBBU_ALL）
  margin/       — 融資融券彙總（MI_MARGN）
  notice/       — 注意有價證券
  disposition/  — 處置有價證券
"""

import os
import sys
import json
import time
import smtplib
import requests
import pandas as pd
from datetime import date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─── 環境變數 ───────────────────────────────────────────────
NOTION_TOKEN          = os.environ.get("NOTION_TOKEN", "")
NOTION_MARKET_DB_ID   = os.environ.get("NOTION_MARKET_DB_ID", "")
NOTION_SCREENER_DB_ID = os.environ.get("NOTION_SCREENER_DB_ID", "")
FINMIND_TOKEN         = os.environ.get("FINMIND_TOKEN", "")
GMAIL_USER            = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD    = os.environ.get("GMAIL_APP_PASSWORD", "")
NOTIFY_EMAIL          = os.environ.get("NOTIFY_EMAIL", "") or GMAIL_USER

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

TODAY      = date.today().isoformat()
WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]
CACHE_FILE = "disposition_cache.json"


# ═══════════════════════════════════════════════════════════
# CSV 存檔工具
# ═══════════════════════════════════════════════════════════

def save_csv(df: pd.DataFrame, category: str) -> None:
    """將 DataFrame 存到 data/<category>/YYYY-MM-DD.csv"""
    if df.empty:
        return
    path = os.path.join("data", category)
    os.makedirs(path, exist_ok=True)
    filepath = os.path.join(path, f"{TODAY}.csv")
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    print(f"  💾 已存檔 → {filepath}（{len(df)} 筆）")


# ═══════════════════════════════════════════════════════════
# Notion 寫入工具
# ═══════════════════════════════════════════════════════════

def _title(v: str) -> dict:
    return {"title": [{"text": {"content": str(v)[:200]}}]}

def _text(v) -> dict:
    return {"rich_text": [{"text": {"content": str(v)[:2000]}}]}

def _num(v) -> dict:
    try:
        return {"number": round(float(v), 2)}
    except Exception:
        return {"number": None}

def _date_prop(d: str) -> dict:
    return {"date": {"start": d}}


def notion_insert(db_id: str, props: dict) -> bool:
    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers=NOTION_HEADERS,
        json={"parent": {"database_id": db_id}, "properties": props},
        timeout=15,
    )
    if resp.status_code not in (200, 201):
        print(f"  ⚠️  Notion 寫入失敗 {resp.status_code}: {resp.text[:150]}")
        return False
    return True


# ═══════════════════════════════════════════════════════════
# Step 1：抓取大盤資料
# ═══════════════════════════════════════════════════════════

def fetch_market() -> dict:
    data: dict = {}

    # ── 全市場行情 (STOCK_DAY_ALL) ──────────────────────────
    try:
        df = pd.DataFrame(
            requests.get(
                "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
                timeout=15,
            ).json()
        )
        for col in ["ClosingPrice", "Change", "TradeVolume", "TradeValue"]:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")
        stocks = df[df["Code"].str.len() == 4]
        data["up"]    = int((stocks["Change"] > 0).sum())
        data["down"]  = int((stocks["Change"] < 0).sum())
        data["value"] = round(stocks["TradeValue"].sum() / 1e8, 1)
        data["stock_df"] = df
        print(f"  上漲 {data['up']} 下跌 {data['down']} 成交 {data['value']:.0f} 億")
    except Exception as e:
        print(f"  ⚠️  STOCK_DAY_ALL: {e}")

    # ── 三大法人 (T86) ─────────────────────────────────────
    try:
        df = pd.DataFrame(
            requests.get("https://openapi.twse.com.tw/v1/fund/T86", timeout=15).json()
        )
        for col in ["ForeignInvestmentNetBuySell", "InvestmentTrustNetBuySell", "DealerNetBuySell"]:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")
        data["foreign"] = round(df["ForeignInvestmentNetBuySell"].sum() / 10000, 2)
        data["trust"]   = round(df["InvestmentTrustNetBuySell"].sum() / 10000, 2)
        data["dealer"]  = round(df["DealerNetBuySell"].sum() / 10000, 2)
        data["t86_df"]  = df
        print(f"  外資 {data['foreign']:+.2f} 投信 {data['trust']:+.2f} 自營 {data['dealer']:+.2f} 億股")
    except Exception as e:
        print(f"  ⚠️  T86: {e}")

    # ── 加權指數 (yfinance) ────────────────────────────────
    try:
        import yfinance as yf
        hist = yf.Ticker("^TWII").history(period="3d")
        if len(hist) >= 1:
            close = float(hist["Close"].iloc[-1])
            prev  = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else close
            chg   = close - prev
            pct   = chg / prev * 100 if prev else 0
            data["taiex"]     = round(close, 2)
            data["taiex_chg"] = round(chg, 2)
            data["taiex_pct"] = round(pct, 2)
            print(f"  加權指數 {close:.2f} ({chg:+.2f} / {pct:+.2f}%)")
    except Exception as e:
        print(f"  ⚠️  指數: {e}")

    return data


# ═══════════════════════════════════════════════════════════
# Step 2：寫入大盤快照
# ═══════════════════════════════════════════════════════════

def write_market(data: dict) -> bool:
    wd  = WEEKDAY_CN[date.today().weekday()]
    props = {
        "名稱": _title(f"{TODAY} (週{wd})"),
        "日期": _date_prop(TODAY),
    }
    for key, col in [
        ("taiex",     "加權指數"),
        ("taiex_chg", "漲跌點"),
        ("taiex_pct", "漲跌幅%"),
        ("up",        "上漲家數"),
        ("down",      "下跌家數"),
        ("value",     "成交金額(億)"),
        ("foreign",   "外資買賣超(億)"),
        ("trust",     "投信買賣超(億)"),
        ("dealer",    "自營商買賣超(億)"),
    ]:
        if key in data:
            props[col] = _num(data[key])

    ok = notion_insert(NOTION_MARKET_DB_ID, props)
    if ok:
        print("  ✅ 大盤快照已存入 Notion")
    return ok


# ═══════════════════════════════════════════════════════════
# Step 3：籌碼面選股（外資 + 投信雙買超）
# ═══════════════════════════════════════════════════════════

def run_screener(data: dict) -> pd.DataFrame:
    t86      = data.get("t86_df", pd.DataFrame())
    stock_df = data.get("stock_df", pd.DataFrame())
    if t86.empty:
        return pd.DataFrame()

    # 外資 + 投信同時買超，排除 ETF
    mask = (
        (t86["ForeignInvestmentNetBuySell"] > 0) &
        (t86["InvestmentTrustNetBuySell"] > 0) &
        (t86["Code"].str.len() == 4)
    )
    hits = t86[mask].copy()

    # 合併股價
    if not stock_df.empty:
        hits = hits.merge(
            stock_df[["Code", "ClosingPrice", "Change", "TradeVolume"]],
            on="Code", how="left",
        )

    # 合併估值 (BWIBBU)
    try:
        val = pd.DataFrame(
            requests.get(
                "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL",
                timeout=15,
            ).json()
        )
        for c in ["PEratio", "DividendYield", "PBratio"]:
            val[c] = pd.to_numeric(val[c], errors="coerce")
        hits = hits.merge(val[["Code", "PEratio", "DividendYield", "PBratio"]],
                          on="Code", how="left")
    except Exception:
        pass

    rows = []
    for _, r in hits.iterrows():
        close = float(r.get("ClosingPrice", 0) or 0)
        chg   = float(r.get("Change", 0) or 0)
        pct   = round(chg / (close - chg) * 100, 2) if (close - chg) > 0 else 0
        rows.append({
            "代號":          str(r["Code"]),
            "名稱":          str(r.get("Name", "")),
            "收盤價":        close,
            "漲跌幅%":       pct,
            "成交量(張)":    int(float(r.get("TradeVolume", 0) or 0) // 1000),
            "外資買賣超(張)": int(r["ForeignInvestmentNetBuySell"]),
            "投信買賣超(張)": int(r["InvestmentTrustNetBuySell"]),
            "本益比":        r.get("PEratio"),
            "殖利率%":       r.get("DividendYield"),
            "股淨比":        r.get("PBratio"),
            "符合條件":      "外資買超、投信買超",
        })

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════
# Step 4：寫入選股紀錄
# ═══════════════════════════════════════════════════════════

def write_screener(df: pd.DataFrame) -> int:
    count = 0
    for _, r in df.iterrows():
        props = {
            "股票":    _title(f"{r['代號']} {r['名稱']}"),
            "日期":    _date_prop(TODAY),
            "代號":    _text(r["代號"]),
            "名稱":    _text(r["名稱"]),
            "符合條件": _text(r["符合條件"]),
        }
        for field in ["收盤價", "漲跌幅%", "成交量(張)", "外資買賣超(張)",
                      "投信買賣超(張)", "本益比", "殖利率%", "股淨比"]:
            val = r.get(field)
            if val is not None and not (isinstance(val, float) and pd.isna(val)):
                props[field] = _num(val)

        if notion_insert(NOTION_SCREENER_DB_ID, props):
            count += 1
        time.sleep(0.4)   # Notion API: 3 req/s 上限

    return count


# ═══════════════════════════════════════════════════════════
# Step 5：處置股清單 + Email 通知（只通知新增）
# ═══════════════════════════════════════════════════════════

def fetch_disposition() -> pd.DataFrame:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    try:
        resp = requests.get(
            "https://www.twse.com.tw/rwd/zh/announcement/punish",
            timeout=15, verify=False,
        )
        data = resp.json()
        # 回傳格式：{"stat":"OK","fields":[...],"data":[[...],...]}
        if data.get("stat") != "OK" or not data.get("data"):
            return pd.DataFrame()
        df = pd.DataFrame(data["data"], columns=data["fields"])
        return df
    except Exception as e:
        print(f"  ⚠️  處置股: {e}")
        return pd.DataFrame()


def load_prev_codes() -> set:
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_curr_codes(codes: set) -> None:
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(codes), f, ensure_ascii=False)
    except Exception as e:
        print(f"  ⚠️  快取寫入失敗: {e}")


def send_email(subject: str, body: str, html: bool = False) -> bool:
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("  ⚠️  GMAIL_USER / GMAIL_APP_PASSWORD 未設定，略過 email")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = GMAIL_USER
        msg["To"]      = NOTIFY_EMAIL

        if html:
            msg.attach(MIMEText(body, "html", "utf-8"))
        else:
            msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            smtp.sendmail(GMAIL_USER, NOTIFY_EMAIL, msg.as_string())
        print(f"  ✅ Email 已寄出 → {NOTIFY_EMAIL}")
        return True
    except Exception as e:
        print(f"  ⚠️  Email 寄送失敗: {e}")
        return False


def df_to_html_table(df: pd.DataFrame) -> str:
    """將 DataFrame 轉換為 HTML 表格"""
    if df.empty:
        return ""

    html = '<table style="border-collapse: collapse; width: 100%; font-family: Arial, sans-serif; font-size: 12px;">'
    html += '<thead><tr style="background-color: #f0f0f0; border: 1px solid #ddd;">'

    # 表頭
    for col in df.columns:
        html += f'<th style="border: 1px solid #ddd; padding: 8px; text-align: left; font-weight: bold;">{col}</th>'
    html += '</tr></thead><tbody>'

    # 表內容（交替背景色，提高可讀性）
    for idx, row in df.iterrows():
        bg_color = "#ffffff" if idx % 2 == 0 else "#f9f9f9"
        html += f'<tr style="background-color: {bg_color}; border: 1px solid #ddd;">'
        for val in row:
            # 處理數字對齐
            if isinstance(val, (int, float)):
                html += f'<td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{val}</td>'
            else:
                html += f'<td style="border: 1px solid #ddd; padding: 8px; text-align: left;">{val}</td>'
        html += '</tr>'

    html += '</tbody></table>'
    return html


# ═══════════════════════════════════════════════════════════
# Step 6：TWSE 每日完整快取（供 Streamlit App 直接讀取）
# ═══════════════════════════════════════════════════════════

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# TWSE 每日快取端點設定
_TWSE_DAILY_ENDPOINTS = {
    "daily_all": {
        "url": "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
        "label": "全市場當日行情",
        "verify": True,
    },
    "institutional": {
        "url": "https://openapi.twse.com.tw/v1/fund/T86",
        "label": "三大法人",
        "verify": True,
    },
    "valuation": {
        "url": "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL",
        "label": "本益比/殖利率/股淨比",
        "verify": True,
    },
    "margin": {
        "url": "https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN",
        "label": "融資融券彙總",
        "verify": True,
    },
    "mi_index": {
        "url": "https://openapi.twse.com.tw/v1/exchangeReport/MI_INDEX",
        "label": "大盤指數",
        "verify": True,
    },
    "notice": {
        "url": "https://www.twse.com.tw/rwd/zh/announcement/notice",
        "label": "注意有價證券",
        "verify": False,   # 舊版 API 需 verify=False
        "is_rwd": True,    # 舊版格式：{"stat":"OK","fields":[...],"data":[[...]]}
    },
    "disposition": {
        "url": "https://www.twse.com.tw/rwd/zh/announcement/punish",
        "label": "處置有價證券",
        "verify": False,
        "is_rwd": True,
    },
}


def fetch_twse_daily_cache() -> dict:
    """
    下載所有 TWSE 每日資料，存到 data/twse/<category>/YYYY-MM-DD.csv。
    回傳 {category: DataFrame} 字典。
    """
    results = {}
    print(f"\n📥 Step 6  下載 TWSE 每日快取資料（{len(_TWSE_DAILY_ENDPOINTS)} 項）")

    for category, cfg in _TWSE_DAILY_ENDPOINTS.items():
        out_path = os.path.join("data", "twse", category, f"{TODAY}.csv")

        # 已存在則跳過
        if os.path.exists(out_path):
            print(f"  ⏭  {cfg['label']}（已存在，跳過）")
            try:
                results[category] = pd.read_csv(out_path, dtype=str)
            except Exception:
                pass
            continue

        try:
            resp = requests.get(cfg["url"], timeout=20, verify=cfg.get("verify", True))
            resp.raise_for_status()
            raw = resp.json()

            # 判斷格式
            if cfg.get("is_rwd"):
                # 舊版 TWSE 格式：{"stat":"OK","fields":[...],"data":[[...],...]}
                if raw.get("stat") != "OK" or not raw.get("data"):
                    print(f"  ⚠️  {cfg['label']}：回傳空資料（可能非交易日）")
                    continue
                df = pd.DataFrame(raw["data"], columns=raw["fields"])
            else:
                # 新版 OpenAPI 格式：直接是 list of dict
                if not raw:
                    print(f"  ⚠️  {cfg['label']}：回傳空資料")
                    continue
                df = pd.DataFrame(raw)

            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            df.to_csv(out_path, index=False, encoding="utf-8-sig")
            results[category] = df
            print(f"  ✅ {cfg['label']}：{len(df)} 筆 → {out_path}")

        except Exception as e:
            print(f"  ⚠️  {cfg['label']}：{e}")

        time.sleep(0.5)   # 限速

    return results


# ═══════════════════════════════════════════════════════════
# 主程式
# ═══════════════════════════════════════════════════════════

def main():
    print(f"\n{'='*52}")
    print(f"  台股每日自動抓取  {TODAY}")
    print(f"{'='*52}\n")

    if not NOTION_TOKEN:
        print("❌ NOTION_TOKEN 未設定，中止")
        sys.exit(1)

    print("📊 Step 1/5  抓取大盤資料...")
    data = fetch_market()

    print("\n💾 Step 2/5  寫入大盤快照...")
    write_market(data)
    # 大盤摘要存 CSV（單列）
    summary_row = {k: data[k] for k in
                   ["taiex","taiex_chg","taiex_pct","up","down","value","foreign","trust","dealer"]
                   if k in data}
    summary_row["date"] = TODAY
    save_csv(pd.DataFrame([summary_row]), "market")

    print("\n🔍 Step 3/5  籌碼選股（外資＋投信雙買超）...")
    screener_df = run_screener(data)
    print(f"  符合條件：{len(screener_df)} 檔")
    if not screener_df.empty:
        print(screener_df[["代號", "名稱", "外資買賣超(張)", "投信買賣超(張)"]].to_string(index=False))

    print(f"\n💾 Step 4/5  寫入選股紀錄...")
    if not screener_df.empty:
        saved = write_screener(screener_df)
        print(f"  ✅ 已存入 {saved}/{len(screener_df)} 筆")
        save_csv(screener_df, "screener")
    else:
        print("  今日無符合選股條件的股票")

    print("\n🚨 Step 5/5  處置股（僅通知新增）...")
    disp_df    = fetch_disposition()
    prev_codes = load_prev_codes()

    if disp_df.empty:
        print("  今日處置股清單為空")
        save_curr_codes(set())
    else:
        # 取代號欄（嘗試常見欄位名）
        code_col = next((c for c in disp_df.columns if "代號" in c or "Code" in c), disp_df.columns[0])
        curr_codes = set(disp_df[code_col].astype(str).str.strip())
        new_codes  = curr_codes - prev_codes
        gone_codes = prev_codes - curr_codes

        print(f"  目前清單 {len(curr_codes)} 檔 | 新增 {len(new_codes)} 檔 | 解除 {len(gone_codes)} 檔")

        if new_codes:
            new_df = disp_df[disp_df[code_col].astype(str).str.strip().isin(new_codes)]

            # 構建 HTML email
            html_body = f"""
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: Arial, sans-serif; background-color: #f5f5f5; margin: 0; padding: 20px; }}
                    .container {{ background-color: #ffffff; border-radius: 8px; padding: 20px; max-width: 800px; margin: 0 auto; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                    .header {{ color: #d32f2f; font-size: 18px; font-weight: bold; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #d32f2f; }}
                    .info {{ color: #666; font-size: 14px; margin-bottom: 20px; }}
                    .table-wrapper {{ overflow-x: auto; margin-bottom: 20px; }}
                    table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
                    th {{ background-color: #d32f2f; color: white; padding: 10px; text-align: left; font-weight: bold; border: 1px solid #b71c1c; }}
                    td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    tr:nth-child(even) {{ background-color: #f9f9f9; }}
                    .footer {{ color: #999; font-size: 12px; margin-top: 20px; padding-top: 10px; border-top: 1px solid #eee; }}
                    .gone {{ color: #ff9800; margin-top: 15px; padding: 10px; background-color: #fff3e0; border-left: 3px solid #ff9800; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">⚠️ 新增處置有價證券通知</div>
                    <div class="info">
                        <strong>日期：</strong> {TODAY}<br>
                        <strong>新增檔數：</strong> {len(new_codes)} 檔
                    </div>
                    <div class="table-wrapper">
                        {df_to_html_table(new_df[new_df.columns.tolist()])}
                    </div>
            """

            if gone_codes:
                html_body += f"""
                    <div class="gone">
                        <strong>同日解除處置：</strong> {', '.join(sorted(gone_codes))}
                    </div>
            """

            html_body += """
                    <div class="footer">
                        此為系統自動通知，請勿直接回覆此郵件。
                    </div>
                </div>
            </body>
            </html>
            """

            send_email(
                subject=f"⚠️ 台股警示 {TODAY} 新增處置股 {len(new_codes)} 檔",
                body=html_body.strip(),
                html=True,
            )
        else:
            print("  無新增處置股，不寄信")

        save_curr_codes(curr_codes)
        save_csv(disp_df, "disposition")

    # Step 6：TWSE 每日完整快取（供 Streamlit 直接讀取）
    fetch_twse_daily_cache()

    print(f"\n✅ 完成  {TODAY}\n")


if __name__ == "__main__":
    main()
