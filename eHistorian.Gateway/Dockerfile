FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl unixodbc unixodbc-dev gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ehistorian_gateway ./ehistorian_gateway
COPY example.config.json ./example.config.json

RUN mkdir -p /data

ENV EHG_BOOTSTRAP_CONFIG=/app/example.config.json
ENV EHG_SQLITE_PATH=/data/offline-buffer.db

CMD ["python", "-m", "ehistorian_gateway.main"]