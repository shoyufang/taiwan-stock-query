@echo off
chcp 65001 >nul
cd /d "G:\我的雲端硬碟\Claude專區\永豐金API"
rem 固定用 Python 3.13（套件裝在 3.13；系統預設 3.14 沒裝套件）
py -3.13 sinopac_query.py
pause
