# 新網站 API。建置內容根目錄為 repo 根（之後要一併複製 datasources/ 等既有模組）。
FROM python:3.13-slim

ENV PYTHONUTF8=1 \
    LANG=C.UTF-8 \
    TZ=Asia/Taipei \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 10001 app
WORKDIR /srv/backend

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app

USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
