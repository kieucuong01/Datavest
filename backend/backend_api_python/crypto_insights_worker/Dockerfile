FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY crypto_insights_worker/requirements.txt /tmp/worker-requirements.txt
RUN pip install --no-cache-dir -r /tmp/worker-requirements.txt

COPY app /app/app
COPY crypto_insights_worker /app/crypto_insights_worker

RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin cryptoworker \
    && mkdir -p /app/data \
    && chown -R cryptoworker:cryptoworker /app

USER cryptoworker
ENV PYTHONUNBUFFERED=1
ENV CRYPTO_INSIGHTS_BROWSER_EXECUTABLE_PATH=/usr/bin/chromium
ENV CRYPTO_INSIGHTS_SNAPSHOT_ROOT=/app/data/crypto-insights
ENV CRYPTO_INSIGHTS_BROWSER_USER_DATA_DIR=/app/data/browser-profiles/crypto-insights

CMD ["python", "-m", "crypto_insights_worker.browser_snapshots"]
