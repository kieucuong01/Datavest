#!/usr/bin/env python3
"""Create DataVest production env files without evaluating shell syntax."""
from __future__ import annotations

import secrets
import sys
from pathlib import Path


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key.replace("_", "").isalnum():
            values[key] = value
    return values


def write_env(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(f"{key}={value}\n" for key, value in sorted(values.items()))
    path.write_text(body, encoding="utf-8")
    path.chmod(0o600)


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: configure_env.py SOURCE_ENV APP_ENV", file=sys.stderr)
        return 2
    source_path, app_path = map(Path, sys.argv[1:])
    source = read_env(source_path)
    app = read_env(app_path)

    app.setdefault("SECRET_KEY", secrets.token_hex(32))
    app.setdefault("MFA_ENCRYPTION_KEY", secrets.token_hex(32))
    app.setdefault("ADMIN_USER", "kieucuong01@gmail.com")
    app.setdefault("ADMIN_EMAIL", "kieucuong01@gmail.com")
    app.setdefault("ADMIN_PASSWORD", secrets.token_urlsafe(24))
    app.setdefault("POSTGRES_PASSWORD", secrets.token_urlsafe(32))
    app.setdefault("PGPASSWORD", app["POSTGRES_PASSWORD"])
    app.setdefault(
        "DATABASE_URL",
        f"postgresql://datavest:{app['POSTGRES_PASSWORD']}@127.0.0.1:5432/datavest",
    )
    app.setdefault("DB_TYPE", "postgresql")
    app.setdefault("REDIS_HOST", "127.0.0.1")
    app.setdefault("REDIS_PORT", "6379")
    app.setdefault("REDIS_CACHE_NAMESPACE", "datavest:cache:v1")
    app.setdefault("CACHE_ENABLED", "true")
    app.setdefault("CELERY_TASKS_ENABLED", "true")
    app.setdefault("CELERY_REDIS_HOST", "127.0.0.1")
    app.setdefault("CELERY_REDIS_PORT", "6379")
    app.setdefault("CELERY_BROKER_DB", "8")
    app.setdefault("CELERY_RESULT_DB", "9")
    app.setdefault("SKIP_AUTO_MIGRATE", "true")
    app.setdefault("PYTHON_API_HOST", "127.0.0.1")
    app.setdefault("PYTHON_API_PORT", "5100")
    app.setdefault("GUNICORN_WORKERS", "1")
    app.setdefault("GUNICORN_THREADS", "2")
    app.setdefault("MARKET_EXECUTOR_WORKERS", "2")
    app.setdefault("PORTFOLIO_EXECUTOR_WORKERS", "1")
    app.setdefault("CHROME_BIN", "/usr/bin/google-chrome")
    app.setdefault("LOG_DIR", "/opt/datavest/shared/logs")
    app.setdefault("FRONTEND_URL", "https://datavest.vn,https://www.datavest.vn")
    app.setdefault("PYTHON_API_DEBUG", "false")
    app.setdefault("DATAVEST_SMART_INSIGHTS_ENABLED", "true")
    app.setdefault("DATAVEST_PORTFOLIO_OPTIMIZER_ENABLED", "true")
    app.setdefault("DATAVEST_COMMUNITY_ENABLED", "false")
    app.setdefault("STRATEGY_COMMANDS_ENABLED", "false")
    app.setdefault("SMART_INSIGHTS_AUTO_REFRESH", "true")
    app.setdefault("SMART_INSIGHTS_REFRESH_INTERVAL_SEC", "21600")
    app.setdefault(
        "SMART_INSIGHTS_AUTO_REFRESH_SOURCE_CODES",
        "bitinfocharts-top-addresses,coinmetrics-community,coinglass-liquidation-maxpain,"
        "coinglass-margin-borrow,defillama-chains,defillama-stablecoins,mempool-space",
    )
    for key in ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL"):
        if source.get(key) and not app.get(key):
            app[key] = source[key]
    if app.get("DEEPSEEK_API_KEY"):
        app.setdefault("LLM_PROVIDER", "deepseek")

    write_env(app_path, app)
    print(f"deepseek_configured={'true' if app.get('DEEPSEEK_API_KEY') else 'false'}")
    print("environment_status=ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
