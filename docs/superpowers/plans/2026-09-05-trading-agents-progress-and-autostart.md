# TradingAgents autostart and progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Deep Analysis modal start a TradingAgents run after a bounded history lookup and show honest upstream stage progress with a percentage.

**Architecture:** Keep TauricResearch/TradingAgents as the execution engine. The private runtime emits only allowlisted stage/tool metadata; Flask derives a public progress snapshot and never exposes raw tool input or model output in status events. The Vue modal restores one exact saved run, otherwise starts one run automatically and presents retry/error recovery instead of an infinite spinner.

**Tech Stack:** Flask/Python, PostgreSQL, FastAPI private runtime, Celery, Vue 2, Ant Design Vue, Node test runner.

**Spec:** Approved behavior in the current task conversation: one-click deep analysis, bounded restore, per-stage status and percentage, no fake progress.

## Global Constraints

- Preserve the pinned upstream TradingAgents graph, prompts, tools and report generation.
- Only owner-scoped run metadata is returned to the browser; raw tool input, environment values and secrets remain private.
- Progress percentage advances only from observed upstream events and reaches 100 only after report persistence.
- Vietnamese and English labels must be provided for every new UI state.
- Preserve unrelated dirty files and do not stage existing user changes.

### Task 1: Public progress contract

**Files:**
- Create: `backend/backend_api_python/app/services/trading_agents_progress.py`
- Modify: `backend/backend_api_python/app/routes/trading_agents.py`
- Modify: `backend/backend_api_python/app/services/trading_agents_repository.py`
- Test: `backend/backend_api_python/tests/test_trading_agents_progress.py`

- [x] Write failing tests for stage derivation, terminal completion, and redaction of raw event payloads.
- [x] Run the focused Python test and verify it fails for the missing progress contract.
- [x] Implement a pure allowlisted progress helper and public event serializer.
- [x] Return `progress` and safe `events` from `_public_run`; mark `report` complete only when an artifact exists.
- [x] Add owner-scoped active-run lookup for the exact user/market/symbol/date request.
- [x] Run the focused tests and repository route regression tests.

### Task 2: Runtime stage events

**Files:**
- Modify: `backend/trading_agents_service/app/events.py`
- Modify: `backend/trading_agents_service/app/runner.py`
- Modify: `backend/trading_agents_service/app/main.py`
- Modify: `backend/trading_agents_service/app/upstream_config.py`
- Test: `backend/trading_agents_service/tests/test_full_graph_runner.py`
- Test: `backend/trading_agents_service/tests/test_upstream_tools_contract.py`

- [x] Write failing tests for stage metadata from native graph chunks and live tool start metadata.
- [x] Run the focused service tests and verify they fail.
- [x] Emit allowlisted stage identifiers from observed chunks without changing upstream graph behavior.
- [x] Forward safe tool-start/tool-complete progress events during execution.
- [x] Run the focused service tests and Python compile checks.

### Task 3: One-click Vue flow

**Files:**
- Modify: `frontend/src/api/trading-agents.js`
- Modify: `frontend/src/components/TradingAgents/DeepAnalysisPanel.vue`
- Modify: `frontend/src/locales/trading-agents.js`
- Test: `frontend/tests/unit/trading-agents-progress.test.mjs`

- [x] Write failing tests for auto-start after empty history, explicit retry after history failure, and stage labels.
- [x] Run the focused Node tests and verify they fail.
- [x] Add an 8-second history request timeout and request guards; auto-start exactly once after an empty history result.
- [x] Render percentage, current stage, completed/remaining steps and recovery actions using mobile-safe layout.
- [x] Run frontend unit tests and lint. Production build is blocked by the sandbox/esbuild path permission error; the escalation retry was rejected by the current usage limit.

### Task 4: Verification

- [x] Run the focused backend and service suites with the repository-local pytest basetemp.
- [x] Run `node --test tests/unit/*.test.mjs`; production build remains blocked by the environment limitation above.
- [x] Inspect the diff and preserve unrelated dirty files; no commit or push was performed in this turn.
