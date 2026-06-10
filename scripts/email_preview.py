#!/usr/bin/env python3
"""
郵件格式預覽生成器（無需寄信）
執行後會在當前目錄產生 email_preview.html，用瀏覽器打開看效果
"""

import pandas as pd
from datetime import date

TODAY = date.today().isoformat()

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


# 範例數據
example_data = {
    "代號": ["2330", "3008", "5490"],
    "公司名稱": ["台積電", "聯發科", "寶滿"],
    "處置原因": ["融資餘額過高", "股價跌幅超過60%", "股價跌幅超過60%"],
    "生效日期": ["2026-05-20", "2026-05-20", "2026-05-21"],
    "備註": ["限制融資", "注意股", ""],
}

new_df = pd.DataFrame(example_data)
gone_codes = {"1234", "5678"}

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
            <strong>新增檔數：</strong> {len(new_df)} 檔
        </div>
        <div class="table-wrapper">
            {df_to_html_table(new_df)}
        </div>

        <div class="gone">
            <strong>同日解除處置：</strong> {', '.join(sorted(gone_codes))}
        </div>

        <div class="footer">
            此為系統自動通知，請勿直接回覆此郵件。
        </div>
    </div>
</body>
</html>
"""

# 存檔
output_file = "email_preview.html"
with open(output_file, "w", encoding="utf-8") as f:
    f.write(html_body)

print(f"已生成預覽 → {output_file}")
print(f"用瀏覽器打開看效果\n")
