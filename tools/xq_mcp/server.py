"""XQ 全球贏家（XQLite）DDE 報價 MCP server。

只在 Windows 本機、XQ 開著並登入時可用。透過 user32 DDEML（ctypes，免 pywin32）
向 XQ 的 DDE 服務 `XQLITE`、topic `Quote` 要資料，item 格式為 `<代號>.TW-<欄位>`。

DDEML instance 綁定建立它的執行緒，所以所有 DDE 呼叫都丟到同一條專用執行緒執行。
資料授權限個人使用，勿公開散布。
"""

from __future__ import annotations

import ctypes
import sys
from concurrent.futures import ThreadPoolExecutor
from ctypes import wintypes as wt

from mcp.server.mcpserver import MCPServer

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

SERVICE = "XQLITE"
TOPIC = "Quote"
DEFAULT_FIELDS = ["Name", "Price", "PreClose", "Open", "High", "Low", "Bid", "Ask", "TotalVolume", "Time"]
TIMEOUT_MS = 5000

CP_WINUNICODE = 1200
CF_TEXT, CF_UNICODETEXT = 1, 13
XTYP_REQUEST = 0x20B0
APPCMD_CLIENTONLY = 0x10

_u = ctypes.WinDLL("user32", use_last_error=True)
_CB = ctypes.WINFUNCTYPE(ctypes.c_void_p, wt.UINT, wt.UINT, ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_cb = _CB(lambda *a: 0)

_u.DdeInitializeW.argtypes = [ctypes.POINTER(wt.DWORD), _CB, wt.DWORD, wt.DWORD]
_u.DdeCreateStringHandleW.argtypes = [wt.DWORD, wt.LPCWSTR, ctypes.c_int]
_u.DdeCreateStringHandleW.restype = ctypes.c_void_p
_u.DdeFreeStringHandle.argtypes = [wt.DWORD, ctypes.c_void_p]
_u.DdeConnect.argtypes = [wt.DWORD, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
_u.DdeConnect.restype = ctypes.c_void_p
_u.DdeDisconnect.argtypes = [ctypes.c_void_p]
_u.DdeClientTransaction.argtypes = [ctypes.c_void_p, wt.DWORD, ctypes.c_void_p, ctypes.c_void_p,
                                    wt.UINT, wt.UINT, wt.DWORD, ctypes.POINTER(wt.DWORD)]
_u.DdeClientTransaction.restype = ctypes.c_void_p
_u.DdeGetData.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, wt.DWORD]
_u.DdeFreeDataHandle.argtypes = [ctypes.c_void_p]
_u.DdeGetLastError.argtypes = [wt.DWORD]


class _Dde:
    """單一執行緒內使用的 DDE client。"""

    def __init__(self) -> None:
        inst = wt.DWORD(0)
        if _u.DdeInitializeW(ctypes.byref(inst), _cb, APPCMD_CLIENTONLY, 0) != 0:
            raise RuntimeError("DdeInitialize 失敗")
        self.inst = inst.value
        self.conv = None

    def _hsz(self, s: str):
        return _u.DdeCreateStringHandleW(self.inst, s, CP_WINUNICODE)

    def _connect(self):
        if self.conv:
            return self.conv
        hs, ht = self._hsz(SERVICE), self._hsz(TOPIC)
        self.conv = _u.DdeConnect(self.inst, hs, ht, None)
        _u.DdeFreeStringHandle(self.inst, hs)
        _u.DdeFreeStringHandle(self.inst, ht)
        if not self.conv:
            raise RuntimeError("連不到 XQ 的 DDE 服務：請確認 XQ 已開啟並登入")
        return self.conv

    def request(self, item: str) -> str | None:
        """回傳欄位文字；失敗回 None。連線斷掉會重連一次。"""
        for attempt in range(2):
            conv = self._connect()
            hi = self._hsz(item)
            try:
                for fmt in (CF_TEXT, CF_UNICODETEXT):
                    res = wt.DWORD(0)
                    hd = _u.DdeClientTransaction(None, 0, conv, hi, fmt, XTYP_REQUEST, TIMEOUT_MS, ctypes.byref(res))
                    if hd:
                        n = _u.DdeGetData(hd, None, 0, 0)
                        buf = ctypes.create_string_buffer(n)
                        _u.DdeGetData(hd, buf, n, 0)
                        _u.DdeFreeDataHandle(hd)
                        return _decode(buf.raw, fmt)
            finally:
                _u.DdeFreeStringHandle(self.inst, hi)
            if attempt == 0:  # 可能 XQ 重啟過，丟掉舊連線再試
                _u.DdeDisconnect(conv)
                self.conv = None
        return None


def _decode(raw: bytes, fmt: int) -> str:
    if fmt == CF_UNICODETEXT:
        return raw.decode("utf-16-le", "replace").rstrip("\x00").strip()
    raw = raw.rstrip(b"\x00")
    for enc in ("cp950", "utf-8"):
        try:
            return raw.decode(enc).strip()
        except UnicodeDecodeError:
            pass
    return raw.decode("cp950", "replace").strip()


def _num(s: str | None):
    """數字字串轉 int/float；`--` 或非數字原樣回傳。"""
    if s is None:
        return None
    try:
        f = float(s.replace(",", ""))
    except ValueError:
        return s
    return int(f) if f.is_integer() else f


_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="dde")
_client: list[_Dde] = []


def _on_dde_thread(fn):
    def run():
        if not _client:
            _client.append(_Dde())
        return fn(_client[0])
    return _pool.submit(run).result()


def _symbol(code: str) -> str:
    code = code.strip().upper()
    return code if "." in code else f"{code}.TW"


mcp = MCPServer("xq")


@mcp.tool()
def xq_quote(codes: list[str], fields: list[str] | None = None) -> dict:
    """查 XQ 即時報價（本機 XQ 必須開著）。

    codes: 股票代號，例如 ["2330", "2454"]；沒寫市場後綴會自動補 `.TW`（上市、上櫃都用 .TW）。
    fields: 要的欄位，預設 Name/Price/PreClose/Open/High/Low/Bid/Ask/TotalVolume/Time。
      休市或尚未成交時 Price 會是 "--"；XQ 不認得的欄位也回 "--"。None 代表代號格式 XQ 不接受。
    """
    flds = fields or DEFAULT_FIELDS

    def work(c: _Dde):
        out = {}
        for code in codes:
            sym = _symbol(code)
            out[sym] = {f: _num(c.request(f"{sym}-{f}")) for f in flds}
        return out

    return _on_dde_thread(work)


@mcp.tool()
def xq_raw(items: list[str]) -> dict:
    """直接向 XQ DDE 要任意 item（用來探索欄位或指數代號），例如 ["2330.TW-Price"]。
    回傳原始文字；None 代表 XQ 不認得或連線失敗。"""
    return _on_dde_thread(lambda c: {it: c.request(it) for it in items})


if __name__ == "__main__":
    mcp.run()
