# DataVest

DataVest is a research and paper-investing workspace for Vietnamese equities,
crypto, and gold (XAU). It is built on QuantDinger source with the required
upstream licences, notices, and `Powered by QuantDinger` attribution retained
inside each component.

## Repository layout

- `frontend/` — Vue web application.
- `backend/` — Flask, Celery, PostgreSQL, Redis, market data, Smart Insights,
  Portfolio Optimizer, Indicator IDE, backtest, and paper portfolio.

## Local stack

Create local environment files from the documented examples, set secrets only
outside Git, then run Compose from this repository root:

```powershell
$Compose = @(
  '-f', 'backend/docker-compose.yml',
  '-f', 'backend/docker-compose.datavest.yml',
  '-f', 'backend/docker-compose.production.yml'
)
docker compose @Compose up --build
```

The product is research and simulation only. Live broker execution, billing,
and paid marketplace surfaces remain disabled.

## Source provenance

This monorepo preserves the current DataVest working snapshot. QuantDinger
upstream source provenance is documented in `backend/deploy/` and the
component-level modification notices.
