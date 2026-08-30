# Process roles and tasks

| Role | Command | Ownership |
| --- | --- | --- |
| API | `gunicorn -c gunicorn_config.py run:app` | HTTP, authentication, validation, and synchronous service calls |
| Migration | `python -m app.commands.migrate` | Fail-fast schema application |
| Scheduler | `python -m app.commands.scheduler` | Portfolio monitoring, payment scans, research maintenance, and signal alerts |
| Celery worker | `celery -A app.celery_app:celery_app worker` | Finite AI, backtest, experiment, report, and maintenance jobs |
| Celery beat | `celery -A app.celery_app:celery_app beat` | Periodic task dispatch |

HTTP processes do not start background loops. Celery tasks must be finite, retryable, and idempotent. Scheduler singleton work uses `qd_process_leases`; process health uses `qd_worker_heartbeats`.

The supported runtime roles are `api`, `scheduler`, `celery`, and `celery-beat`.
