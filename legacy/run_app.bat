@echo off
chcp 65001 >nul
echo 啟動券商提供查詢工具...
cd /d "%~dp0"
rem 固定用 Python 3.13（套件裝在 3.13；系統預設 3.14 沒裝套件）
py -3.13 -m streamlit run app.py --logger.level=error
pause
