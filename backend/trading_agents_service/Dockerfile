FROM ghcr.io/astral-sh/uv:0.11.22 AS uv

FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=uv /uv /uvx /bin/

WORKDIR /workspace/backend
COPY third_party/tradingagents ./third_party/tradingagents
COPY trading_agents_service ./trading_agents_service

WORKDIR /workspace/backend/trading_agents_service
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    HOME=/var/lib/tradingagents

RUN groupadd --gid 10002 tradingagents \
    && useradd --uid 10002 --gid tradingagents --home-dir /var/lib/tradingagents \
        --create-home --shell /usr/sbin/nologin tradingagents \
    && install -d --owner=tradingagents --group=tradingagents /app /var/lib/tradingagents

COPY --from=builder /workspace/backend/trading_agents_service/.venv /opt/venv
COPY --chown=tradingagents:tradingagents trading_agents_service/app /app/app

USER 10002:10002
WORKDIR /app

EXPOSE 8080

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
