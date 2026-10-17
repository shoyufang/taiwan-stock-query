FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 安裝基本編譯工具（防範 shioaji 的部分依賴在極簡版 Linux 下需要編譯）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# 複製並在鏡像內部直接安裝所有依賴（避免每次重啟容器都要重新下載）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 啟動 Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
