# Concurrency model

Concurrency is bounded at retained state-changing boundaries.

| Operation | Identity | Guard |
| --- | --- | --- |
| Agent jobs | token, kind, idempotency key | unique idempotency record and bounded worker pool |
| Backtests | job id or request key | durable job state and retry-safe writes |
| Strategy-source versions | source id and version | tenant ownership and explicit restore confirmation |
| Watchlist writes | user, market, symbol | canonical symbol and database uniqueness |
| Indicator alerts | task id | tenant ownership, status transitions, and delivery confirmation |
| Scheduler work | lease key | renewable PostgreSQL process lease |

In-process locks are used only as local optimizations. Cross-process ownership relies on PostgreSQL or Redis-backed primitives. External network reads use bounded retries and fail-open/fail-closed behavior appropriate to each read-only provider.
