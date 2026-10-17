import os
import tempfile

# 測試時快取檔放暫存資料夾，不碰 /data（在 Windows 會變成磁碟根目錄）
os.environ.setdefault("STORE_PATH", os.path.join(tempfile.mkdtemp(prefix="twstock-test-"), "store.db"))
# 警示背景工作在測試中不自動啟動（需要的測試自行呼叫）
os.environ.setdefault("ALERTS_ENABLED", "0")
