"""
台股與港美股查詢工具箱 — 向後相容墊片。
此模組原有的資料查詢邏輯已拆分至 datasources 套件中，互動選單移至 cli 模組。
為了向後相容與便於單元測試 Mock，此檔案會重新匯出 datasources 的所有符號。
"""

from datasources import *
from datasources.shioaji_client import HAS_SHIOAJI
import cli

if __name__ == "__main__":
    cli.main()
