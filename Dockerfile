FROM python:3.11-slim

WORKDIR /app

# System deps for pandas wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1 \
    C5_TRADING_MODE=paper \
    C5_DEMO_MODE=1 \
    C5_API_HOST=0.0.0.0 \
    C5_API_PORT=8000 \
    C5_DB_PATH=/data/c5_data.sqlite

VOLUME ["/data"]
EXPOSE 8000

CMD ["python", "-m", "api.app"]
