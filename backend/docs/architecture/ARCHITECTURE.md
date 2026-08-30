# Backend architecture

DataVest's retained backend is a research, market-data, backtest, Indicator, alert, paper-portfolio, and Agent/MCP service.

| Component | Location | Responsibility |
| --- | --- | --- |
| Human API | `backend_api_python/app/routes`, `app/openapi` | Authentication, settings, research workspaces, backtests, Indicators, alerts, paper portfolio, and the free source library |
| Agent Gateway | `backend_api_python/app/routes/agent_v1` | Tenant-scoped R/W/B/N research APIs |
| Market data | `backend_api_python/app/data_sources`, `app/data_providers` | Public K-lines, quotes, symbols, fundamentals, macro data, and news |
| Strategy research | `backend_api_python/app/services/strategy_v2` | Source contracts, validation, point-in-time data, simulation, and backtests |
| Background work | `app/tasks`, `app/commands/scheduler.py` | Finite Celery jobs and scheduled research/notification maintenance |
| MCP | `mcp_server` | Curated adapter over the Agent Gateway |

PostgreSQL is the system of record. Redis cache is evictable; the job Redis instance backs Celery. HTTP processes validate and delegate. Finite retryable work belongs to Celery, and scheduled maintenance belongs to the scheduler process.

Public market-data adapters are uncredentialed. Provider API keys, when required for a read-only provider, are server-side configuration and are not user account credentials.
