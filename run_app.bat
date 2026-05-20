@echo off
chcp 65001 > /dev/null
echo 啟動券商提供查詢工具...
cd /d "%~dp0"
python -m streamlit run app.py --logger.level=error
pause
