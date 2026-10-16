"""公開資訊觀測站（MOPS）。

法說會：舊站 mopsov 的 ajax_t100sb02_1，回傳 HTML 表格（table#myTable，每列 12 格）。
做法參考 TWStockMCPServer（MIT 授權）tools/mops/investor_conference.py：
必須帶隱藏欄位、月份要補零（9 月要送 "09"）。MOPS 有防爬限制，呼叫端應快取。
"""

from __future__ import annotations

from html.parser import HTMLParser

import httpx

LEGACY = "https://mopsov.twse.com.tw/mops/web"
HIDDEN = {"encodeURIComponent": "1", "step": "1", "firstin": "1", "off": "1"}
ROW_WIDTH = 12


class _Table(HTMLParser):
    def __init__(self, table_id: str):
        super().__init__(convert_charrefs=True)
        self.table_id, self.inside, self.rows, self.row, self.cell = table_id, False, [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "table" and dict(attrs).get("id") == self.table_id:
            self.inside = True
        if not self.inside:
            return
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = ""

    def handle_endtag(self, tag):
        if not self.inside:
            return
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(" ".join(self.cell.split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == "table":
            self.inside = False

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data


def parse_conferences(html: str) -> list[dict]:
    p = _Table("myTable")
    p.feed(html)
    out = []
    for r in p.rows:
        if len(r) != ROW_WIDTH or r[0] == "公司代號":
            continue
        out.append({"code": r[0], "name": r[1], "date_text": r[2], "time": r[3], "place": r[4], "summary": r[5]})
    return out


async def conferences(client: httpx.AsyncClient, roc_year: int, month: int, market: str = "sii") -> str:
    r = await client.post(f"{LEGACY}/ajax_t100sb02_1",
                          data={**HIDDEN, "TYPEK": market, "year": str(roc_year), "month": f"{month:02d}", "co_id": ""})
    r.raise_for_status()
    html = r.text
    if "myTable" not in html and "查無資料" not in html:
        raise RuntimeError("公開資訊觀測站回應非預期頁面（可能暫時限制存取）")
    return html
