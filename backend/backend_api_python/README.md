# QuantDinger Python backend

The backend provides public market data, research workspaces, Strategy API V2 validation and backtests, Indicator IDE services, alerts, manual and paper portfolios, and the R/W/B/N Agent Gateway.

## Process model

| Role | Command | Purpose |
| --- | --- | --- |
| API | `gunicorn -c gunicorn_config.py run:app` | HTTP, authentication, validation, and synchronous services |
| Migration | `python -m app.commands.migrate` | Apply the PostgreSQL schema before services start |
| Scheduler | `python -m app.commands.scheduler` | Scheduled portfolio, research, and signal maintenance |
| Celery worker | `celery -A app.celery_app:celery_app worker` | Finite AI, backtest, report, experiment, and maintenance jobs |
| Celery beat | `celery -A app.celery_app:celery_app beat` | Periodic task dispatch |

PostgreSQL is the system of record. Cache Redis is evictable; job Redis backs Celery and uses durable settings.

## Boundaries

- Crypto and other market-data adapters are read-only.
- Provider API keys are server-side provider configuration, not user account secrets.
- Strategy sources own research contracts and backtest provenance.
- Indicators are chart-only.
- Manual positions and Agent paper orders remain separate from external accounts.
- Agent scopes are exactly `R/W/B/N`.
- MCP is a curated adapter over `/api/agent/v1`.

## Local workflow

From `backend_api_python`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-local
.\.venv\Scripts\python.exe -m compileall -q app
```

Use `requirements.txt` for the main environment and `requirements-windows.txt` for Windows-specific constraints. Configuration comes from environment variables; do not commit secrets.

## Health and operations

| Endpoint | Purpose |
| --- | --- |
| `GET /` | Application identity and version |
| `GET /api/health` | Liveness |
| `GET /api/health/ready` | PostgreSQL and Celery readiness |
| `GET /api/health/workers` | Scheduler and Celery heartbeat summary |
| `GET /metrics` | Prometheus metrics; keep private |

## Quality checks

Run focused tests for changed modules, then the full backend suite with a repository-local `--basetemp`. Also run syntax/import smoke checks, deterministic scope inventory when applicable, and `git diff --check`.

## Legacy Smart Insights migration

The old DataVest evidence importer is `app.tools.migrate_smart_insights`.
`SOURCE_DATABASE_URL` is read-only input and the command is dry-run by
default. Use `--apply` only for an approved local/staging destination after
reviewing the redacted report. See
`../docs/operations/smart-insights-migration.md` for the cutover checklist.

## License

See the repository license and notices.
