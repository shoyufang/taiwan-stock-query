#!/bin/sh
cd /volume1/docker/sinopac

echo "=== 正在拉取 GitHub 最新程式碼 ==="
git pull origin main

echo "=== 停止並移除舊的 Streamlit 網站容器 ==="
sudo docker stop sinopac-web 2>/dev/null
sudo docker rm sinopac-web 2>/dev/null

echo "=== 啟動全新的 Streamlit 網站容器 ==="
sudo docker run -d --name sinopac-web \
  --restart unless-stopped \
  -v /volume1/docker/sinopac:/app \
  -w /app \
  -p 8501:8501 \
  -e GEMINI_API_KEY="請在此填入您的_Gemini_API_Key" \
  -e FINMIND_TOKEN="請在此填入您的_FinMind_Token_如果有的話" \
  python:3.11-slim bash -c "pip install -q -r requirements.txt && streamlit run app.py --server.port=8501 --server.address=0.0.0.0"

echo "=== 更新完成！網站已在 NAS Port 8501 背景運行 ==="
echo "=== 請使用 http://您的NAS內網IP:8501 連線查看 ==="
