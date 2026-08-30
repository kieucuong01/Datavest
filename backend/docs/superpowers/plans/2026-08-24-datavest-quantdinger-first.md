# DataVest QuantDinger-First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans task-by-task. Every behavioral change uses RED-GREEN-REFACTOR.

**Goal:** Turn the pinned QuantDinger backend and Vue frontend into a DataVest-branded, research-and-paper-only quantitative workspace with Smart Insights and Portfolio Optimizer.

**Architecture:** Keep the Flask/PostgreSQL/Redis/Celery backend and Vue 2.7 frontend as separate repositories pinned by one release manifest. Use QuantDinger market data as the primary price/catalog source; port DataVest specialty evidence collectors and optimizer contracts into Python-native services. Start with a fresh database and per-user JWT ownership.

**Tech stack:** Python 3.12, Flask 3, PostgreSQL, Redis, Celery, Vue 2.7, Vite 5, Ant Design Vue, pytest, Node test runner.

**Source baselines:** Backend `366ea33c276b5307ce8428da6dcca160532635ea`; frontend `6f9ce97fe4730355c39a72610f5dbda3f05d3db7`; DataVest source `76e93056cc625df84015d67608755911e2a8fac7` plus the current Smart Insights/OpenBB working-tree changes.

## Global Constraints

- Do not edit or merge `quant-insight-radar` or its abandoned `feature/quantdinger-indicator-ide` worktree.
- Final branding is DataVest. Preserve frontend/backend licenses, modification notices, and visible `Powered by QuantDinger` attribution.
- Keep market data, catalog/search, watchlist, charts, Indicator IDE, alerts, backtest, strategy/factor research, analysis-only AI, paper portfolio, and free public libraries.
- Remove live broker credentials/orders, trading worker, live strategy deployment, Agent trading scope, grid/copy trading, paid marketplace/credits, hidden code, and mobile app. Market-data adapters remain read-only.
- Use a new PostgreSQL database and QuantDinger JWT ownership by `user_id`; do not port Better Auth, Prisma, organizations, users, or portfolios.
- DeepSeek and provider keys stay server-side. Never log or return secrets, environment values, raw stack traces, or cross-user data.
- `DEMO` evidence may render only in explicit Demo Mode and is forbidden in production opinions, AI context, optimizer inputs, alerts, and paper orders.
- Quick trade and optimizer apply always produce `SIMULATED`; there is no live-order compatibility route.
- QuantDinger providers are primary for bars/catalog. DataVest collectors are specialty sources for VN, macro, ETF flow, derivatives, on-chain, and events.
- Graphify was attempted on both repositories and failed with `uv trampoline failed to canonicalize script path`; deterministic route/import/dependency inventories are the required fallback evidence.

---

### Task 1: Dependency inventory, product scope, and release pinning

**Backend deliverable:** Add deterministic audit tests/scripts that inventory Flask routes, worker roles, Compose services, migrations, and forbidden production surfaces. Add a two-repository release manifest and DataVest modification notice.

**Frontend deliverable:** Add deterministic route/menu/API inventory tests for forbidden live/billing/mobile surfaces and preserved research surfaces.

**Verification:** Run the inventory tests red against the original source, then establish the explicit allow/deny contracts used by Tasks 2 and 4.

### Task 2: Research-and-paper-only backend

**Deliverable:** Remove live execution, broker credential management, grid/copy trading, live strategy deployment, Agent T scope, billing/credits/paid marketplace, mobile/trading Compose wiring, and their migrations/services/tests. Preserve read-only exchange market data, scheduler/Celery, indicator/backtest/research, alerts, JWT, and paper ledger.

**Verification:** Forbidden route/service inventory is empty; retained QuantDinger regression suites pass; request attempts to old live routes return 404.

### Task 3: Smart Insights backend

**Interfaces:**
- `GET /api/smart-insights/overview?as_of=&market=&mode=live|demo`
- `GET /api/smart-insights/dates`
- `GET /api/smart-insights/evidence/<id>`
- `GET /api/smart-insights/data-health`
- `POST /api/smart-insights/refresh` (admin only)

**Deliverable:** Add additive PostgreSQL migrations for `data_sources`, `collector_runs`, `observations`, `insight_snapshots`, `asset_opinions`, `insight_evidence_links`, and `user_insight_preferences`; port evidence models, source health, checksum dedupe, specialty collectors, scheduling, and evidence-gated DeepSeek explanations.

**Verification:** Provenance/freshness/collector failure/dedupe tests pass; ownership is enforced; `DEMO` IDs are rejected by live calculations and AI.

### Task 4: Portfolio Optimizer and paper rebalance backend

**Interfaces:**
- `POST /api/portfolio/optimizer/runs`
- `GET /api/portfolio/optimizer/runs/<id>`
- `POST /api/portfolio/optimizer/runs/<id>/preview`
- `POST /api/portfolio/optimizer/runs/<id>/apply`

**Deliverable:** Add Python-native risk parity, minimum variance, maximum Sharpe, target return, target volatility, and risk tolerance methods; VN/Crypto/US daily data, maximum 10 instruments, maximum 3,650 days, minimum 31 aligned prices, production FX conversion, immutable input snapshots, provenance/checksums, and idempotent simulated rebalance plans.

**Verification:** Numerical fixtures, missing data/FX, cross-currency, ownership, immutable snapshot, preview, idempotency, and `SIMULATED` ledger tests pass.

### Task 5: DataVest frontend foundation

**Deliverable:** Rebrand navigation/login/About/footer as DataVest with `Powered by QuantDinger`; remove live trading/broker/grid/copy/billing/mobile routes, menus, stores, API clients, and components; keep research, IDE, backtest, factors, alerts, watchlist, paper portfolio, and free libraries.

**Verification:** Route/menu inventory tests pass, Vietnamese/English and light/dark build, no removed API path is emitted by the production bundle.

### Task 6: Smart Insights and Optimizer Vue UI

**Deliverable:** Port modular Vue views for Asset Opinions, Decision Brief, Crypto/Macro Pulse, Portfolio Impact, Evidence Drawer, Data Health, explicit Demo Mode watermark, optimizer setup/results/correlation/frontier, and two-step paper rebalance confirmation.

**Verification:** Component tests cover live/demo/unavailable states, evidence provenance, provider errors, optimizer validation, preview/apply confirmation, and `SIMULATED` status.

### Task 7: Production wiring and full verification

**Deliverable:** Production Compose contains frontend, backend, PostgreSQL, cache Redis, durable Redis, scheduler, and Celery only. Add independent Smart Insights/Optimizer flags, observability events, release manifest validation, deployment/rollback runbook, and source/license inventory.

**Verification:** Backend full pytest, ruff, bandit, pip-audit assessment, frontend unit/lint/build, Compose config, provider contract tests, HTTP health, and browser acceptance all complete. Final review covers both repository diffs and the dependency inventory.
