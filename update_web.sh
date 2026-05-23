#!/bin/sh
# =========================================================
# NAS 快速部署腳本（git pull + docker restart，無需 rebuild）
# 適用條件：requirements.txt 無變動時使用
# =========================================================
cd /volume1/docker/sinopac

echo "=== 正在拉取 GitHub 最新程式碼 ==="
git pull origin main

echo "=== 重啟 Streamlit 容器（無需 rebuild，volume 掛載即時生效）==="
sudo docker restart sinopac-web

echo "=== 完成！網站已在 NAS Port 8502 背景運行 ==="
echo "=== 請使用 http://您的NAS內網IP:8502 連線查看 ==="
