"""
工具函式 — 導出、對比、智能呈現邏輯
"""

import pandas as pd
import io
from typing import List, Tuple, Optional
from enum import Enum

class ResultType(Enum):
    """結果類型判斷"""
    TABLE = "table"
    KBAR = "kbar"
    FINANCIAL = "financial"
    RANKING = "ranking"
    SINGLE_VALUE = "single_value"
    MIXED = "mixed"

def detect_result_type(df: pd.DataFrame, query_type: str = "") -> ResultType:
    """自動判斷結果類型，決定最佳呈現方式"""

    if df.empty:
        return ResultType.TABLE

    cols = df.columns.tolist()
    col_lower = [c.lower() for c in cols]

    # K線檢測：有 開、高、低、收
    if all(x in col_lower for x in ['開盤', '最高', '最低', '收盤']) or \
       all(x in col_lower for x in ['open', 'high', 'low', 'close']):
        return ResultType.KBAR

    # 排行榜檢測：有排名相關欄位
    if any(x in col_lower for x in ['排名', 'rank', '漲跌幅', 'change_percent']):
        return ResultType.RANKING

    # 財報檢測：有營收、淨利等欄位
    if any(x in col_lower for x in ['營收', '淨利', '營業成本', 'revenue', 'net_income']):
        return ResultType.FINANCIAL

    # 單一數值檢測：只有一行一列
    if len(df) == 1 and len(cols) == 1:
        return ResultType.SINGLE_VALUE

    return ResultType.TABLE

def export_to_notion(df: pd.DataFrame, title: str, notion_token: str, database_id: str) -> tuple[bool, str]:
    """將 DataFrame 匯出到 Notion 資料庫（建立一個包含表格的頁面）"""
    import requests, json
    if not notion_token or not database_id:
        return False, "請先在設定中填入 Notion Token 與 Database ID"

    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    # 將 DataFrame 前 100 列轉成 Notion table block
    rows = df.head(100)
    cols = rows.columns.tolist()

    table_rows = []
    # 標題行
    header_cells = [{"type": "text", "text": {"content": str(c)}} for c in cols]
    table_rows.append({"type": "table_row", "table_row": {"cells": [[cell] for cell in header_cells]}})
    # 資料行
    for _, row in rows.iterrows():
        cells = [[{"type": "text", "text": {"content": str(row[c]) if pd.notna(row[c]) else ""}}] for c in cols]
        table_rows.append({"type": "table_row", "table_row": {"cells": cells}})

    payload = {
        "parent": {"database_id": database_id},
        "properties": {
            "Name": {"title": [{"text": {"content": title}}]}
        },
        "children": [
            {
                "type": "table",
                "table": {
                    "table_width": len(cols),
                    "has_column_header": True,
                    "has_row_header": False,
                    "children": table_rows,
                }
            }
        ]
    }

    try:
        r = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload, timeout=15)
        if r.status_code == 200:
            page_url = r.json().get("url", "")
            return True, page_url
        else:
            return False, f"Notion API 錯誤 {r.status_code}: {r.json().get('message', r.text[:200])}"
    except Exception as e:
        return False, str(e)


def export_csv(df: pd.DataFrame, filename: str = "export.csv") -> bytes:
    """導出 CSV"""
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")

def export_excel(df: pd.DataFrame, filename: str = "export.xlsx") -> bytes:
    """導出 Excel"""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Data", index=False)
    return buffer.getvalue()

def export_pdf(df: pd.DataFrame, filename: str = "export.pdf", title: str = "") -> bytes:
    """導出 PDF（簡易表格）"""
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch

    buffer = io.BytesIO()

    # 根據列數決定頁面方向
    pagesize = landscape(letter) if len(df.columns) > 4 else letter
    doc = SimpleDocTemplate(buffer, pagesize=pagesize, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)

    elements = []

    # 標題
    if title:
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1f77b4'),
            spaceAfter=12
        )
        elements.append(Paragraph(title, title_style))
        elements.append(Spacer(1, 0.2 * inch))

    # 轉換為表格數據
    data = [df.columns.tolist()] + df.values.tolist()

    # 限制表格寬度和字體
    col_widths = [letter[0] / len(df.columns) * 0.9] * len(df.columns)
    table = Table(data, colWidths=col_widths)

    # 表格樣式
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F2F2F2')]),
    ]))

    elements.append(table)
    doc.build(elements)

    return buffer.getvalue()

def compare_results(results: List[Tuple[str, pd.DataFrame]]) -> pd.DataFrame:
    """並排對比多個查詢結果（簡化版：堆疊表格）"""
    if not results or len(results) == 0:
        return pd.DataFrame()

    if len(results) == 1:
        return results[0][1]

    # 如果是多個結果，暫時採用堆疊方式，每個結果前加標籤行
    all_dfs = []
    for label, df in results:
        # 添加標籤行
        label_row = pd.DataFrame({col: [f"【{label}】"] if i == 0 else [""] for i, col in enumerate(df.columns)})
        all_dfs.append(label_row)
        all_dfs.append(df)

    return pd.concat(all_dfs, ignore_index=True)

def format_number(value: float, decimals: int = 2) -> str:
    """格式化數字，自動加千位符"""
    if pd.isna(value):
        return "-"
    try:
        return f"{value:,.{decimals}f}"
    except:
        return str(value)

def truncate_dataframe(df: pd.DataFrame, max_rows: int = 50) -> pd.DataFrame:
    """截斷大型 DataFrame 以提高顯示性能"""
    if len(df) > max_rows:
        return df.head(max_rows)
    return df
