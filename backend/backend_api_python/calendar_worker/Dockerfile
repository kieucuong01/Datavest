FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY calendar_worker/requirements.txt /tmp/calendar-worker-requirements.txt
RUN pip install --no-cache-dir -r /tmp/calendar-worker-requirements.txt

COPY calendar_worker /app/calendar_worker

RUN useradd --create-home --shell /usr/sbin/nologin calendarworker \
    && mkdir -p /app/data \
    && chown -R calendarworker:calendarworker /app

USER calendarworker
ENV PYTHONUNBUFFERED=1
ENV INVESTING_BROWSER_EXECUTABLE_PATH=/usr/bin/chromium
ENV INVESTING_CALENDAR_SNAPSHOT_PATH=/app/data/economic-calendar/investing-browser.json
ENV INVESTING_BROWSER_USER_DATA_DIR=/app/data/browser-profiles/investing

CMD ["python", "-m", "calendar_worker.investing_calendar_browser"]
