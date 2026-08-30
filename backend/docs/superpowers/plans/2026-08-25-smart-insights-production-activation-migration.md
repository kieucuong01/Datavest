# Smart Insights production-source activation and legacy migration plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the QuantDinger-first DataVest stack consume the Smart Insights sources that were verified in the old DataVest production runbook, while importing old source-backed evidence into the new schema without touching the old production database or migrating authentication secrets.

**Architecture:** Keep the new QuantDinger PostgreSQL schema as the destination of truth. Add an explicit production-source manifest with activation metadata, enable only the old DataVest allowlist that has documented production evidence, and keep unsupported runtime adapters visible as `IMPORT_ONLY` until their parser is ported. Add a read-only source PostgreSQL importer with dry-run default, checksum dedupe, LIVE/DEMO classification, and a single target transaction for apply. Auto-refresh must continue to run only registered runtime collectors and report import-only sources as explicit partial warnings.

**Tech Stack:** Flask/Celery, Python 3.12, psycopg2, PostgreSQL, pytest, Docker Compose, existing Smart Insights `Observation`/snapshot contracts.

**Spec:**

- Production-verified activation set is the old DataVest `ENABLED_SOURCE_CODES`: `alternative-fng`, `bis-statistics`, `bitinfocharts-top-addresses`, `blockchaincenter-altcoin-season`, `cbbi-public`, `cftc-disaggregated`, `coinglass-liquidation-maxpain`, `coinglass-margin-borrow`, `coinmetrics-community`, `coinshares-weekly`, `cryptocraft`, `defillama-chains`, `defillama-stablecoins`, `farside-btc-etf`, `farside-eth-etf`, `farside-sol-etf`, `fred`, `gdacs-events`, `mempool-space`, `nasa-eonet`, `openbb-deribit`, and `usgs-earthquakes`.
- Do not enable `mempool-btc-large-addresses`, `cftc-legacy`, or `eia-energy`; the old production runbook explicitly says they were disabled or not qualified.
- `SOURCE_DATABASE_URL` is read-only input and must come from the environment or an operator-provided dump. Never write, migrate, or delete in the source database.
- The importer defaults to dry-run. `--apply` is required to write local destination rows. It must never log DSNs, tokens, raw secrets, or full provider payloads.
- Import only source evidence, runs, events-as-evidence, and optional same-email user preferences. Do not import `app_users`, password hashes, organizations, sessions, broker credentials, portfolio ledger, or raw AI secrets.
- A source is `LIVE` only when its source snapshot is `validated`, its provider run is `succeeded`, and its quality is `passed` or `warning`; all other rows are skipped or classified `DEMO` with a visible reason.
- Every imported row is idempotent by destination source/checksum. Restore is additive and never rewrites immutable history.

**Global Constraints:** Preserve unrelated dirty work in `quant-insight-radar`; do not use its uncommitted production collector changes as a destructive source of truth. Keep secrets out of command output. Graphify was already attempted and failed on this Windows workspace with the documented `uv trampoline failed to canonicalize script path`; deterministic registry/import inventories are the fallback evidence.

---

## Task 1: Add the production activation manifest and schema metadata

**Files:**

- Modify: `backend_api_python/migrations/20260824_smart_insights_foundation.sql`
- Create: `backend_api_python/migrations/20260825_smart_insights_production_sources.sql`
- Modify: `backend_api_python/app/services/smart_insights/sources.py`
- Test: `backend_api_python/tests/test_smart_insights_sources.py`

- [x] Add all 22 verified source definitions with URL, terms URL, schedule, SLA, and `activationMode` metadata.
- [x] Add `activation_mode`, `verified_at`, and `disabled_reason` columns additively; do not change existing row IDs or historical checksums.
- [x] Upsert the 22 verified sources as enabled and the three unqualified sources as disabled with explicit reasons.
- [x] Keep source enablement separate from runtime collector availability so an imported production source cannot be mistaken for a local parser.
- [x] Test manifest membership, unqualified exclusions, idempotent migration text, and secret-free metadata.

## Task 2: Make refresh honest when the enabled manifest contains import-only sources

**Files:**

- Modify: `backend_api_python/app/services/smart_insights/collectors.py`
- Modify: `backend_api_python/app/services/smart_insights/repository.py`
- Modify: `backend_api_python/app/tasks/smart_insights.py`
- Modify: `backend_api_python/migrations/20260825_smart_insights_production_sources.sql`
- Test: `backend_api_python/tests/test_smart_insights_collectors.py`

- [x] Register the existing `openbb-deribit`, `fred`, and `defillama-stablecoins` runtime collectors without changing their contracts.
- [x] Make refresh process every requested source, collect registered sources, and record explicit `SOURCE_NOT_IMPLEMENTED` warnings for import-only sources instead of aborting before useful data is persisted.
- [x] Add a `PARTIAL` run status and return it when at least one source succeeds while one or more import-only sources are unavailable; a request containing no runnable sources remains `FAILED`.
- [x] Make the Celery auto-refresh source list configurable with `SMART_INSIGHTS_AUTO_REFRESH_SOURCE_CODES`; default it to the enabled manifest but preserve explicit warnings.
- [x] Add worker/beat/backend Compose environment wiring for the feature flag, interval, and source list.
- [x] Test partial, all-failed, dedupe, and snapshot publication behavior.

## Task 3: Build the production PostgreSQL evidence importer

**Files:**

- Create: `backend_api_python/app/tools/migrate_smart_insights.py`
- Create: `backend_api_python/tests/test_migrate_smart_insights.py`
- Modify: `backend_api_python/README.md`
- Create: `docs/operations/smart-insights-migration.md`

- [x] Read old DataVest `data_providers`, `provider_runs`, `insight_raw_snapshots`, `metric_definitions`, `metric_observations`, `economic_events`, and optional preference rows with parameterized queries.
- [x] Map providers/runs/raw snapshots/metrics to destination `data_sources`, `collector_runs`, and `observations`, preserving source IDs where valid and recording the original ID in provenance JSON.
- [x] Convert metric rows to the destination evidence contract (`metric`, `value`, `unit`, `dimensions`, quality, natural key, revision), resolve symbols only when the source asset catalog has a safe match, and map economic events to explicit macro evidence rows rather than silently dropping them.
- [x] Classify LIVE/DEMO fail-closed using validated raw snapshots, succeeded provider runs, and quality status. Report skipped rows and reasons.
- [x] Compute destination checksums through the same `Observation.create` contract, dedupe on `(data_source_id, checksum)`, and keep source rows untouched.
- [x] Support `--dry-run` (default), `--apply`, `--limit`, and a JSON report path. Refuse `--apply` when source and destination DSNs resolve to the same database.
- [ ] Keep an optional same-email preference migration behind an explicit flag; never copy password hashes or sessions. Deferred because account migration is outside this source-evidence cutover.
- [x] Test classification, source/metric/event mapping, same-DB refusal, dry-run no-write, idempotent apply, and redacted reporting.

## Task 4: Configure and verify the local stack

**Files:**

- Modify: `docker-compose.datavest.yml`
- Modify: `.env.example`
- Modify: `docs/deployment/DATAVEST_DEPLOY_ROLLBACK.md`
- Create: `scripts/verify-smart-insights-production.ps1`

- [x] Enable Smart Insights and auto-refresh in the DataVest local override, but keep the source-code list explicit and reviewable.
- [ ] Run migration, inspect source activation counts, run one refresh, and verify the API returns provenance and a non-empty LIVE snapshot after runtime data or imported rows exist. Blocked by missing Docker daemon and source DSN.
- [x] Run the importer contract tests and dry-run safety checks; a real source dry-run remains pending the production DSN/dump.
- [ ] Verify all services, worker logs, data-health rows, source statuses, and no secret leakage in logs. Blocked by missing Docker daemon.
- [x] Run focused Python tests, existing Smart Insights tests, frontend scope tests, and lint; full backend suite is green.

## Task 5: Operator handoff and production cutover gate

- [x] Report the exact 22-source activation set and the three exclusions with evidence dates.
- [ ] Consume a read-only source DSN/dump only through `SOURCE_DATABASE_URL`/secure file; no credential exists in this workspace.
- [ ] Produce a dry-run JSON report with row counts, checksum collisions, unmapped sources, and skipped classifications.
- [ ] Apply only to local/staging first, verify rollback backup and row counts, then provide the production cutover command for an operator-approved window.
- [ ] Do not claim future runtime parity for import-only sources until their collector smoke passes in the QuantDinger deployment environment.
