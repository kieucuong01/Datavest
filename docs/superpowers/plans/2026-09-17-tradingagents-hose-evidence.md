# TradingAgents HOSE Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every HOSE TradingAgents run consume one immutable point-in-time Vietnam Evidence DTO.

**Architecture:** The backend worker builds and stores the snapshot once, sends it over the signed private boundary, and the TradingAgents service validates and injects a bounded authoritative context into the pinned graph. Existing non-Vietnam runs retain their current provider and prompt behavior.

**Tech Stack:** Python 3, Flask/Celery, PostgreSQL JSONB, FastAPI, vendored TradingAgents/LangGraph, pytest.

**Spec:** `docs/superpowers/specs/2026-09-17-tradingagents-hose-evidence-design.md`

## Global Constraints

- Use only free VNDIRECT and Yahoo Vietnam data.
- A VNStock run must fail closed when its point-in-time price evidence is unavailable or invalid.
- Evidence is write-once per TradingAgents run and reused on resume.
- Full raw evidence never appears in public route responses or callback events.
- Crypto and Gold behavior must remain unchanged.
- Do not push or deploy without an explicit user request.

---

### Task 1: Point-in-time TradingAgents evidence builder

**Files:**
- Create: `backend/backend_api_python/app/services/trading_agents_vietnam.py`
- Test: `backend/backend_api_python/tests/test_trading_agents_vietnam.py`

**Interfaces:**
- Produces `build_trading_agents_vietnam_evidence(symbol: str, analysis_date: str) -> dict[str, Any]`.
- Consumes `DataSourceFactory.get_kline(..., price_mode="adjusted")`, `calculate_indicators`, and `VietnamEvidenceService.build`.

- [ ] Write failing tests for adjusted bar requests, analysis-date cutoff, deterministic price/technical payloads, and fail-closed missing prices.
- [ ] Run the tests and confirm the missing builder causes the failures.
- [ ] Implement the builder with a Vietnam end-of-day cutoff and no current-data fallback.
- [ ] Run the focused tests.

### Task 2: Immutable run evidence persistence

**Files:**
- Modify: `backend/backend_api_python/migrations/20260905_trading_agents.sql`
- Modify: `backend/backend_api_python/app/services/trading_agents_repository.py`
- Modify: `backend/backend_api_python/tests/test_trading_agents_repository.py`

**Interfaces:**
- Produces `TradingAgentsRepository.store_evidence(run_id, evidence)`.
- `get_run_for_worker` and owner-scoped readers expose checksum/as-of metadata; only the worker reader exposes `evidence_json`.

- [ ] Write failing migration/repository tests for the evidence columns, write-once update, and worker retrieval.
- [ ] Verify the tests fail for the missing schema and method.
- [ ] Add idempotent schema changes and guarded persistence.
- [ ] Run repository and DB bootstrap regressions.

### Task 3: Worker dispatch and resume reuse

**Files:**
- Modify: `backend/backend_api_python/app/tasks/trading_agents.py`
- Modify: `backend/backend_api_python/tests/test_trading_agents_tasks.py`

**Interfaces:**
- Produces signed payload key `vietnam_evidence` for VNStock only.
- Reuses stored `evidence_json`; otherwise builds and persists exactly once.

- [ ] Write failing tests for first-run construction, resume reuse, non-Vietnam isolation, and safe evidence failure.
- [ ] Verify expected failures.
- [ ] Implement snapshot resolution and dispatch failure handling.
- [ ] Run task tests.

### Task 4: Private-service validation and context injection

**Files:**
- Create: `backend/trading_agents_service/app/vietnam_evidence.py`
- Modify: `backend/trading_agents_service/app/main.py`
- Modify: `backend/trading_agents_service/app/runner.py`
- Test: `backend/trading_agents_service/tests/test_vietnam_evidence.py`
- Test: `backend/trading_agents_service/tests/test_private_run_endpoint.py`
- Test: `backend/trading_agents_service/tests/test_full_graph_runner.py`

**Interfaces:**
- Produces `validate_vietnam_evidence(...)`, `format_vietnam_evidence_context(...)`, and `evidence_provenance(...)`.
- `TradingAgentsRunRequest` gains `vietnam_evidence: Mapping[str, Any] | None`.

- [ ] Write failing tests for checksum/symbol/cutoff/size validation and non-Vietnam rejection.
- [ ] Write a failing runner test proving validated evidence reaches `instrument_context`.
- [ ] Implement bounded validation, formatting, request propagation, and one provenance event.
- [ ] Run private-service tests.

### Task 5: HOSE source-priority prompts

**Files:**
- Modify: `backend/third_party/tradingagents/tradingagents/agents/analysts/market_analyst.py`
- Modify: `backend/third_party/tradingagents/tradingagents/agents/analysts/fundamentals_analyst.py`
- Modify: `backend/third_party/tradingagents/tests/test_structured_agent_prompts.py`

**Interfaces:**
- Consumes the `DATAVEST_VIETNAM_EVIDENCE` marker embedded in `instrument_context`.

- [ ] Add failing source-contract tests for conditional DataVest evidence precedence.
- [ ] Verify the prompt tests fail before the instruction exists.
- [ ] Add the minimal conditional source-priority language to both analysts.
- [ ] Run the vendored prompt and analyst regressions.

### Task 6: Public provenance and integrated verification

**Files:**
- Modify: `backend/backend_api_python/app/routes/trading_agents.py`
- Modify: `backend/backend_api_python/tests/test_trading_agents_routes.py`
- Verify all earlier files.

**Interfaces:**
- Public run responses expose `evidence: {version, checksum, asOf, providers, gapCount}` only.

- [ ] Add a failing route test proving public provenance is exposed without raw evidence.
- [ ] Implement the bounded public projection.
- [ ] Run backend TradingAgents, Vietnam Evidence, route, callback and quality suites.
- [ ] Run private-service and vendored TradingAgents focused suites, `py_compile`, and `git diff --check`.
