# TradingAgents Full Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the complete pinned TradingAgents framework as a private DataVest service and expose every research capability through AI Assistant and Smart Insights without weakening the upstream agent graph.

**Architecture:** Vendor the upstream source unchanged at commit `9dee508c44662702281a8dbaad1f7b42179b5ba7` and run it in an isolated Python 3.12 container. Flask owns public JWT routes and DataVest records; the service owns exact upstream runtime, vendors, checkpoints, memory and report files, and reports lifecycle events through a signed internal callback.

**Tech Stack:** Vue 2.7, Flask, Celery, Redis, PostgreSQL, Docker Compose, Python 3.12, LangGraph, TradingAgents, DeepSeek and upstream vendor clients.

**Spec:** `docs/superpowers/specs/2026-09-05-trading-agents-full-integration-design.md`

## Global Constraints

- Vendor the complete upstream source unchanged under `backend/third_party/tradingagents/`, preserving Apache-2.0 license and upstream test files.
- Pin upstream to `9dee508c44662702281a8dbaad1f7b42179b5ba7`; no floating branch, tag or unpinned package dependency.
- Keep all upstream graph roles, tools, provider options, checkpoint/resume, memory/reflection, report artifacts and CLI available.
- DataVest is research and paper-only: no broker credential, live order or new execution path absent from upstream.
- The TradingAgents service has no public port. Flask is the only public API gateway.
- Do not expose LLM/provider credentials, internal service credentials, raw exception stack traces or another user’s state.
- Preserve existing Fast Analysis and its 07:00 Vietnam monitor unchanged.
- All new database migrations are additive and reversible by feature-flag disablement.

---

## File structure

- `backend/third_party/tradingagents/` — full upstream git subtree, code and tests unchanged.
- `backend/trading_agents_service/` — DataVest-only service adapter, Dockerfile, Python lock, internal HTTP API and state isolation.
- `backend/backend_api_python/app/services/trading_agents.py` — Flask gateway service and persistence orchestration.
- `backend/backend_api_python/app/routes/trading_agents.py` — authenticated public API.
- `backend/backend_api_python/app/tasks/trading_agents.py` — Celery dispatch/retry task.
- `backend/backend_api_python/migrations/20260905_trading_agents.sql` — additive durable-run schema.
- `frontend/src/api/trading-agents.js` — API/SSE client.
- `frontend/src/views/ai-analysis/components/TradingAgentsLauncher.vue` — AI Assistant launch/configuration surface.
- `frontend/src/views/ai-analysis/components/TradingAgentsRunView.vue` — full report, stream and controls.
- `frontend/src/views/smart-insights/components/AssetOpinionsSection.vue` — dated deep-analysis action.
- `frontend/src/views/smart-insights/analysisReport.js` — links a dated opinion to a matching run only.
- `backend/docker-compose.datavest.yml`, `backend/docker-compose.production.yml`, `backend/.env.example` — service, volume, feature flags and resource limits.

### Task 1: Vendor upstream source and lock its provenance

**Files:**
- Create: `backend/third_party/tradingagents/` from the full upstream git subtree.
- Create: `backend/third_party/tradingagents/UPSTREAM.md`.
- Modify: `LICENSES.md`, `backend/NOTICE`, `backend/.dockerignore`.
- Test: `backend/trading_agents_service/tests/test_upstream_provenance.py`.

**Interfaces:**
- Produces `UPSTREAM_COMMIT = "9dee508c44662702281a8dbaad1f7b42179b5ba7"` for service startup validation.
- Consumes no DataVest runtime APIs.

- [ ] **Step 1: Write the failing provenance test**

```python
def test_vendored_tradingagents_is_complete_and_pinned():
    assert upstream_commit() == "9dee508c44662702281a8dbaad1f7b42179b5ba7"
    assert upstream_path("tradingagents/graph/trading_graph.py").is_file()
    assert upstream_path("tradingagents/agents/analysts/fundamentals_analyst.py").is_file()
    assert upstream_path("cli/main.py").is_file()
    assert upstream_path("LICENSE").is_file()
```

- [ ] **Step 2: Run the provenance test and verify failure**

Run: `pytest backend/trading_agents_service/tests/test_upstream_provenance.py -v`

Expected: FAIL because no vendored upstream source exists.

- [ ] **Step 3: Import the upstream git subtree and write provenance metadata**

Use a squash subtree import of exactly the pinned commit. `UPSTREAM.md` records
repository URL, commit, import date, Apache-2.0 license, upstream test command
and the rule that modifications belong outside the vendored tree. Add the
required notices without replacing existing QuantDinger notices.

- [ ] **Step 4: Run provenance test and upstream import integrity check**

Run: `pytest backend/trading_agents_service/tests/test_upstream_provenance.py -v`

Expected: PASS. Also run `git diff --exit-code -- backend/third_party/tradingagents/tradingagents` after the subtree import; later DataVest adapter work must not modify this path.

- [ ] **Step 5: Commit the isolated upstream import**

```powershell
git add backend/third_party/tradingagents LICENSES.md backend/NOTICE backend/.dockerignore backend/trading_agents_service/tests/test_upstream_provenance.py
git commit -m "chore: vendor pinned TradingAgents upstream"
```

### Task 2: Build the private TradingAgents service with exact dependencies

**Files:**
- Create: `backend/trading_agents_service/pyproject.toml`.
- Create: `backend/trading_agents_service/uv.lock`.
- Create: `backend/trading_agents_service/Dockerfile`.
- Create: `backend/trading_agents_service/app/config.py`.
- Create: `backend/trading_agents_service/app/main.py`.
- Test: `backend/trading_agents_service/tests/test_service_config.py`.

**Interfaces:**
- Produces `GET /internal/health` and configuration validation before importing `TradingAgentsGraph`.
- Consumes `TRADINGAGENTS_*`, `DEEPSEEK_*`, `DATAVEST_TRADING_AGENTS_CALLBACK_SECRET`, and state-root configuration only from the container environment.

- [ ] **Step 1: Write failing configuration tests**

```python
def test_service_rejects_missing_callback_secret(monkeypatch):
    monkeypatch.delenv("DATAVEST_TRADING_AGENTS_CALLBACK_SECRET", raising=False)
    with pytest.raises(ConfigurationError):
        load_settings()

def test_service_preserves_upstream_provider_config(monkeypatch):
    monkeypatch.setenv("TRADINGAGENTS_LLM_PROVIDER", "deepseek")
    assert load_settings().upstream_env["TRADINGAGENTS_LLM_PROVIDER"] == "deepseek"
```

- [ ] **Step 2: Run the test and verify failure**

Run: `pytest backend/trading_agents_service/tests/test_service_config.py -v`

Expected: FAIL because the service package and settings loader do not exist.

- [ ] **Step 3: Implement a Python 3.12 service image**

Install the vendored project with its exact `pyproject.toml`, generate a lock
inside `backend/trading_agents_service`, and expose only a private HTTP bind.
Run non-root with a read-only root filesystem and writable `/var/lib/tradingagents`
plus `/tmp`. `config.py` must pass all native `TRADINGAGENTS_*` settings through
unchanged and must reject missing internal credentials at startup.

- [ ] **Step 4: Run tests and container health check**

Run: `pytest backend/trading_agents_service/tests/test_service_config.py -v`

Expected: PASS.

Run: `docker compose -f backend/docker-compose.yml -f backend/docker-compose.datavest.yml config`

Expected: Compose config is valid before the new service is enabled.

- [ ] **Step 5: Commit the service runtime boundary**

```powershell
git add backend/trading_agents_service
git commit -m "feat: add private TradingAgents service runtime"
```

### Task 3: Run the unmodified full agent graph and persist native state

**Files:**
- Create: `backend/trading_agents_service/app/runner.py`.
- Create: `backend/trading_agents_service/app/state.py`.
- Create: `backend/trading_agents_service/app/events.py`.
- Create: `backend/trading_agents_service/app/reporting.py`.
- Test: `backend/trading_agents_service/tests/test_full_graph_runner.py`.
- Test: `backend/trading_agents_service/tests/test_state_isolation.py`.

**Interfaces:**
- Consumes `TradingAgentsRunRequest` with `run_id`, `user_id`, `ticker`, `asset_type`, `analysis_date`, selected analysts and native upstream config.
- Produces ordered `RunEvent` records and `RunArtifact` metadata; invokes the original `TradingAgentsGraph` without replacing nodes or prompts.

- [ ] **Step 1: Write failing graph-completeness test**

```python
def test_full_run_uses_every_upstream_role(fake_upstream_graph):
    result = run_full_graph(full_request(), graph_factory=fake_upstream_graph)
    assert result.executed_roles == {
        "market", "social", "news", "fundamentals", "bull", "bear",
        "research_manager", "trader", "aggressive", "neutral",
        "conservative", "portfolio_manager",
    }
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest backend/trading_agents_service/tests/test_full_graph_runner.py backend/trading_agents_service/tests/test_state_isolation.py -v`

Expected: FAIL because the runner and per-user state resolver do not exist.

- [ ] **Step 3: Implement the thin upstream runner adapter**

Call `TradingAgentsGraph(selected_analysts=("market", "social", "news", "fundamentals"), config=native_config)` and stream its native LangGraph chunks. Map each chunk to an event without modifying original prompts, agent code or tool nodes. Use the original `begin_checkpoint`, `checkpoint_input`, stream, `clear_checkpoint_on_success` and `end_checkpoint` lifecycle. Set upstream `results_dir`, `data_cache_dir` and `memory_log_path` inside a sanitized `/var/lib/tradingagents/users/{user_id}/` root; never accept a path from a request.

- [ ] **Step 4: Run complete runner tests**

Run: `pytest backend/trading_agents_service/tests/test_full_graph_runner.py backend/trading_agents_service/tests/test_state_isolation.py -v`

Expected: PASS. Verify user A cannot resolve user B’s memory, report or checkpoint path.

- [ ] **Step 5: Commit native graph integration**

```powershell
git add backend/trading_agents_service/app backend/trading_agents_service/tests
git commit -m "feat: run full TradingAgents graph in isolated service"
```

### Task 4: Preserve all upstream data tools and provider settings

**Files:**
- Create: `backend/trading_agents_service/app/instruments.py`.
- Create: `backend/trading_agents_service/app/upstream_config.py`.
- Create: `backend/trading_agents_service/tests/test_upstream_tools_contract.py`.
- Create: `backend/trading_agents_service/tests/test_instrument_mapping.py`.

**Interfaces:**
- Produces upstream ticker and asset type from `(market, datavest_symbol)`.
- Produces vendor status for `core_stock_apis`, `technical_indicators`, `fundamental_data`, `news_data`, `macro_data`, and `prediction_markets`.

- [ ] **Step 1: Write failing mapping and tool-contract tests**

```python
@pytest.mark.parametrize(("market", "symbol", "ticker", "asset_type"), [
    ("Crypto", "BTC/USDT", "BTC-USD", "crypto"),
    ("VNStock", "VCB", "VCB.VN", "stock"),
    ("Gold", "XAU", "XAUUSD", "stock"),
])
def test_maps_datavest_instrument_to_upstream(market, symbol, ticker, asset_type):
    assert resolve_instrument(market, symbol) == (ticker, asset_type)

def test_all_native_tool_groups_are_reported():
    assert upstream_tool_groups() == {
        "market", "social", "news", "fundamentals",
        "core_stock_apis", "technical_indicators", "fundamental_data",
        "news_data", "macro_data", "prediction_markets",
    }
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest backend/trading_agents_service/tests/test_upstream_tools_contract.py backend/trading_agents_service/tests/test_instrument_mapping.py -v`

Expected: FAIL because mapping and tool provenance are not implemented.

- [ ] **Step 3: Implement only boundary adapters**

Implement DataVest-to-upstream ticker mapping and reject unknown mappings.
Pass native `TRADINGAGENTS_*` vendor configuration unchanged. Capture native tool
calls, selected vendor, timing, result checksum and configured/unavailable/error
status as events. Do not substitute DataVest values for the original upstream
tools. Optionally attach DataVest evidence as a separate, labeled context
artifact.

- [ ] **Step 4: Run tool tests plus upstream vendor tests**

Run: `pytest backend/trading_agents_service/tests/test_upstream_tools_contract.py backend/trading_agents_service/tests/test_instrument_mapping.py -v`

Expected: PASS.

Run: `pytest backend/third_party/tradingagents/tests/test_vendor_routing.py backend/third_party/tradingagents/tests/test_crypto_asset_mode.py backend/third_party/tradingagents/tests/test_no_data_handling.py -v`

Expected: PASS.

- [ ] **Step 5: Commit tool preservation and market identity work**

```powershell
git add backend/trading_agents_service/app/instruments.py backend/trading_agents_service/app/upstream_config.py backend/trading_agents_service/tests
git commit -m "feat: preserve TradingAgents tools and market mapping"
```

### Task 5: Add durable DataVest run records and internal callback verification

**Files:**
- Create: `backend/backend_api_python/migrations/20260905_trading_agents.sql`.
- Create: `backend/backend_api_python/app/services/trading_agents.py`.
- Create: `backend/backend_api_python/app/services/trading_agents_repository.py`.
- Test: `backend/backend_api_python/tests/test_trading_agents_repository.py`.
- Test: `backend/backend_api_python/tests/test_trading_agents_callback_auth.py`.

**Interfaces:**
- Produces `create_run`, `append_event`, `store_artifact`, `transition_run`, and `get_owned_run`.
- Consumes a signed callback containing `run_id`, sequence number, event type and redacted payload.

- [ ] **Step 1: Write failing migration and callback tests**

```python
def test_event_sequence_is_unique_per_run(db):
    run = create_run(db, user_id=7, request=sample_request())
    append_event(db, run.id, 1, "agent_started", {})
    with pytest.raises(IntegrityError):
        append_event(db, run.id, 1, "agent_started", {})

def test_callback_rejects_invalid_signature(client):
    response = client.post("/api/internal/trading-agents/callback", json={"run_id": "r1"})
    assert response.status_code == 401
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest backend/backend_api_python/tests/test_trading_agents_repository.py backend/backend_api_python/tests/test_trading_agents_callback_auth.py -v --basetemp .pytest-tmp/trading-agents`

Expected: FAIL because migration, repository and callback do not exist.

- [ ] **Step 3: Implement additive schema and authenticated callback**

Create the four tables specified in the design, foreign keys to the DataVest
user record, owner indexes, unique `(run_id, sequence)` event key, artifact
checksum and immutable config/source-pin fields. Verify HMAC and timestamp on
each callback before persisting a redacted event. Raw secrets, headers and
tracebacks are never stored.

- [ ] **Step 4: Run repository and migration tests**

Run: `pytest backend/backend_api_python/tests/test_trading_agents_repository.py backend/backend_api_python/tests/test_trading_agents_callback_auth.py -v --basetemp .pytest-tmp/trading-agents`

Expected: PASS.

- [ ] **Step 5: Commit persistence boundary**

```powershell
git add backend/backend_api_python/migrations/20260905_trading_agents.sql backend/backend_api_python/app/services/trading_agents.py backend/backend_api_python/app/services/trading_agents_repository.py backend/backend_api_python/tests
git commit -m "feat: persist TradingAgents runs and artifacts"
```

### Task 6: Expose authenticated public APIs and Celery dispatch

**Files:**
- Create: `backend/backend_api_python/app/routes/trading_agents.py`.
- Create: `backend/backend_api_python/app/tasks/trading_agents.py`.
- Modify: `backend/backend_api_python/app/openapi/register.py`.
- Modify: `backend/backend_api_python/app/celery_app.py`.
- Test: `backend/backend_api_python/tests/test_trading_agents_routes.py`.
- Test: `backend/backend_api_python/tests/test_trading_agents_tasks.py`.

**Interfaces:**
- Produces owner-scoped `/api/trading-agents/runs`, run detail, SSE events,
  resume, cancel, clear-checkpoint and artifact routes.
- Consumes the repository methods from Task 5 and service URL from environment.

- [ ] **Step 1: Write failing route and ownership tests**

```python
def test_user_cannot_read_another_users_run(client, other_user_run):
    response = client.get(f"/api/trading-agents/runs/{other_user_run.id}")
    assert response.status_code == 404

def test_run_is_queued_without_exposing_service_secret(client):
    response = client.post("/api/trading-agents/runs", json=full_run_payload())
    assert response.status_code == 202
    assert "DATAVEST_TRADING_AGENTS" not in response.get_data(as_text=True)
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest backend/backend_api_python/tests/test_trading_agents_routes.py backend/backend_api_python/tests/test_trading_agents_tasks.py -v --basetemp .pytest-tmp/trading-agents-routes`

Expected: FAIL because routes and dispatch task do not exist.

- [ ] **Step 3: Implement routes using existing Fast Analysis conventions**

Use `login_required`, `g.user_id`, rate-limited inflight locks, `HumanBlueprint`
and `app/openapi/register.py`. Enqueue a dedicated `trading-agents` Celery queue
only after the durable record exists. The dispatch task signs the service
request. Resume uses the original run config; cancel and clear-checkpoint are
idempotent. SSE sends stored events after a cursor and falls back to polling.

- [ ] **Step 4: Run API and task tests**

Run: `pytest backend/backend_api_python/tests/test_trading_agents_routes.py backend/backend_api_python/tests/test_trading_agents_tasks.py -v --basetemp .pytest-tmp/trading-agents-routes`

Expected: PASS.

- [ ] **Step 5: Commit public gateway**

```powershell
git add backend/backend_api_python/app/routes/trading_agents.py backend/backend_api_python/app/tasks/trading_agents.py backend/backend_api_python/app/openapi/register.py backend/backend_api_python/app/celery_app.py backend/backend_api_python/tests
git commit -m "feat: expose TradingAgents run API"
```

### Task 7: Add Compose, feature flag, least privilege and health integration

**Files:**
- Modify: `backend/docker-compose.datavest.yml`.
- Modify: `backend/docker-compose.production.yml`.
- Modify: `backend/.env.example`.
- Create: `backend/trading_agents_service/tests/test_compose_contract.py`.
- Modify: `backend/backend_api_python/app/openapi/routes/health.py`.

**Interfaces:**
- Produces `datavest-trading-agents` on the private Compose network and a named
  state volume with no published port.
- Consumes `DATAVEST_TRADING_AGENTS_ENABLED` and resource limit variables.

- [ ] **Step 1: Write failing Compose-security tests**

```python
def test_trading_agents_has_no_host_port_and_is_non_root(compose):
    service = compose["services"]["trading-agents"]
    assert "ports" not in service
    assert service["user"] != "0:0"
    assert service["read_only"] is True

def test_feature_disabled_keeps_public_routes_hidden(client):
    assert client.post("/api/trading-agents/runs", json={}).status_code == 404
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest backend/trading_agents_service/tests/test_compose_contract.py -v`

Expected: FAIL because Compose lacks the private service and feature flag.

- [ ] **Step 3: Implement locked Compose service**

Add the service with `depends_on` health conditions, read-only root, non-root
user, bounded CPU/memory, internal state volume and no `ports`. Add only the
provider credentials required by configured upstream tools. Add a health
dependency to the DataVest health response without revealing config values.

- [ ] **Step 4: Validate Compose and security tests**

Run: `pytest backend/trading_agents_service/tests/test_compose_contract.py -v`

Expected: PASS.

Run: `docker compose -f backend/docker-compose.yml -f backend/docker-compose.datavest.yml -f backend/docker-compose.production.yml config`

Expected: valid Compose configuration; service has no host port.

- [ ] **Step 5: Commit deployment wiring**

```powershell
git add backend/docker-compose.datavest.yml backend/docker-compose.production.yml backend/.env.example backend/backend_api_python/app/openapi/routes/health.py backend/trading_agents_service/tests
git commit -m "feat: deploy TradingAgents as private service"
```

### Task 8: Build the complete AI Assistant experience

**Files:**
- Create: `frontend/src/api/trading-agents.js`.
- Create: `frontend/src/views/ai-analysis/components/TradingAgentsLauncher.vue`.
- Create: `frontend/src/views/ai-analysis/components/TradingAgentsRunView.vue`.
- Modify: `frontend/src/views/ai-analysis/index.vue`.
- Modify: `frontend/src/views/ai-analysis/components/CopilotWorkbench.vue`.
- Modify: `frontend/src/locales/lang/vi-VN.js`, `frontend/src/locales/lang/en-US.js`.
- Test: `frontend/tests/unit/tradingAgentsLauncher.test.mjs`.
- Test: `frontend/tests/unit/tradingAgentsRunView.test.mjs`.

**Interfaces:**
- Consumes the Task 6 API.
- Produces a button labelled `PHÂN TÍCH CHUYÊN SÂU MÃ`, an advanced native
  TradingAgents configuration form, event progress, full raw report sections
  and resume/cancel actions.

- [ ] **Step 1: Write failing UI contract tests**

```javascript
test('AI Assistant exposes the full TradingAgents launch configuration', () => {
  const source = read('src/views/ai-analysis/components/TradingAgentsLauncher.vue')
  assert.match(source, /market.*social.*news.*fundamentals/su)
  assert.match(source, /maxDebateRounds/u)
  assert.match(source, /checkpointEnabled/u)
})
```

- [ ] **Step 2: Run tests and verify failure**

Run: `npm run test:unit -- tradingAgentsLauncher.test.mjs tradingAgentsRunView.test.mjs`

Expected: FAIL because the API client and components do not exist.

- [ ] **Step 3: Implement a thin full-capability UI**

Keep Chẩn đoán mã and Chẩn đoán biểu đồ unchanged. Add a separate deep-analysis
entry point that defaults to all four analysts and exposes every upstream
runtime choice permitted by the server. Render each stored upstream section
without truncating it, include source/vendor events and explicit unavailable
states, and use Vietnamese/English-only strings. Build responsive 360px layout
with a full-screen report modal on mobile.

- [ ] **Step 4: Run UI unit tests and production build**

Run: `npm run test:unit -- tradingAgentsLauncher.test.mjs tradingAgentsRunView.test.mjs`

Expected: PASS.

Run: `npm run build`

Expected: production build succeeds.

- [ ] **Step 5: Commit AI Assistant integration**

```powershell
git add frontend/src/api/trading-agents.js frontend/src/views/ai-analysis frontend/src/locales/lang frontend/tests/unit
git commit -m "feat: add full TradingAgents analysis to AI Assistant"
```

### Task 9: Link dated Smart Insights opinions without latest-report fallback

**Files:**
- Modify: `frontend/src/views/smart-insights/components/AssetOpinionsSection.vue`.
- Modify: `frontend/src/views/smart-insights/analysisReport.js`.
- Modify: `frontend/src/views/smart-insights/index.vue`.
- Test: `frontend/tests/unit/smartInsightsTradingAgentsLink.test.mjs`.

**Interfaces:**
- Consumes owner-scoped TradingAgents run lookup with `market`, `symbol` and
  `analysisDate`.
- Produces `Phân tích chuyên sâu` action for the exact selected Smart Insights day.

- [ ] **Step 1: Write failing dated-run test**

```javascript
test('Smart Insights never opens a deep report from another date', () => {
  const run = matchingRun({ symbol: 'BTC', asOf: '2026-09-05' })
  assert.equal(resolveDeepRun(run, 'BTC', '2026-09-04'), null)
})
```

- [ ] **Step 2: Run test and verify failure**

Run: `npm run test:unit -- smartInsightsTradingAgentsLink.test.mjs`

Expected: FAIL because dated deep-run resolution is absent.

- [ ] **Step 3: Implement exact-date action and modal navigation**

Use the existing Asset Opinions table and modal pattern. The action opens an
existing matching run or offers to create a new run for the selected date. It
shows the upstream source pin, data date and report status; it never displays
the latest run as a substitute.

- [ ] **Step 4: Run unit test and mobile browser check**

Run: `npm run test:unit -- smartInsightsTradingAgentsLink.test.mjs`

Expected: PASS.

Run: Playwright viewport checks at `360x800` and `390x844` for Smart Insights
Asset Opinions and the full report modal.

Expected: no horizontal overflow, clipped actions or inaccessible close button.

- [ ] **Step 5: Commit Smart Insights linking**

```powershell
git add frontend/src/views/smart-insights frontend/tests/unit/smartInsightsTradingAgentsLink.test.mjs
git commit -m "feat: link dated Smart Insights opinions to TradingAgents"
```

### Task 10: Run upstream regression, DataVest contracts and end-to-end verification

**Files:**
- Create: `backend/trading_agents_service/tests/test_e2e_full_run.py`.
- Create: `frontend/tests/e2e/trading-agents.spec.mjs`.
- Create: `backend/docs/operations/TRADING_AGENTS_RUNBOOK.md`.

**Interfaces:**
- Consumes the full local Compose stack with feature flag enabled and test LLM/vendor adapters.
- Produces verified proof for every capability, security boundary and user flow.

- [ ] **Step 1: Write failing end-to-end contracts**

```python
def test_full_run_stream_contains_all_agent_sections(local_stack):
    run = create_full_run(local_stack, symbol="BTC/USDT")
    assert wait_for_status(run.id) == "completed"
    assert required_artifact_names(run.id) >= {
        "market", "social", "news", "fundamentals", "bull", "bear",
        "research_manager", "trader", "aggressive", "neutral",
        "conservative", "portfolio_manager",
    }
```

- [ ] **Step 2: Run end-to-end contract and verify failure**

Run: `pytest backend/trading_agents_service/tests/test_e2e_full_run.py -v`

Expected: FAIL until the local Compose service and full run flow are complete.

- [ ] **Step 3: Add test doubles and runbook**

Provide deterministic LLM/tool fakes for CI while retaining a manual live
canary for configured DeepSeek and native vendors. The runbook documents local
startup, health, feature enable/disable, service logs, checkpoint recovery,
vendor failure interpretation, retention, rollback and source-pin upgrade.

- [ ] **Step 4: Execute all verification gates**

Run:

```powershell
pytest backend/third_party/tradingagents/tests -v
pytest backend/trading_agents_service/tests -v
pytest backend/backend_api_python/tests/test_trading_agents_*.py -v --basetemp .pytest-tmp/trading-agents-final
npm run test:unit
npm run build
```

Expected: all pass.

Run Playwright for desktop and 360px/390px mobile: launch a full deep analysis,
watch events, reload/resume, view every report section, use a dated Smart
Insights run and retry an unavailable vendor.

- [ ] **Step 5: Commit verification and operations documentation**

```powershell
git add backend/trading_agents_service/tests frontend/tests/e2e backend/docs/operations/TRADING_AGENTS_RUNBOOK.md
git commit -m "test: verify full TradingAgents integration"
```

### Task 11: Stage release and canary safely

**Files:**
- Modify: `backend/.env.example`.
- Modify: `backend/docs/operations/TRADING_AGENTS_RUNBOOK.md`.
- Test: `backend/trading_agents_service/tests/test_release_manifest.py`.

**Interfaces:**
- Consumes immutable DataVest release SHA, upstream source pin and feature flag.
- Produces a staged canary with a reversible feature disable path.

- [ ] **Step 1: Write failing release-manifest test**

```python
def test_release_manifest_requires_upstream_pin_and_service_image():
    manifest = load_release_manifest()
    assert manifest["tradingAgentsUpstreamCommit"] == "9dee508c44662702281a8dbaad1f7b42179b5ba7"
    assert manifest["services"]["trading-agents"]
```

- [ ] **Step 2: Run test and verify failure**

Run: `pytest backend/trading_agents_service/tests/test_release_manifest.py -v`

Expected: FAIL because the release manifest lacks a TradingAgents entry.

- [ ] **Step 3: Add staged feature controls**

Set `DATAVEST_TRADING_AGENTS_ENABLED=false` by default. Roll out local Compose,
then staging with BTC, one mapped VN symbol and XAU, then admin canary. Track
run success, role completion, vendor availability, LLM retries, checkpoint
resume, per-user isolation and proposal audit. Disable only the feature flag
for rollback; retain additive run records and state volume for diagnosis.

- [ ] **Step 4: Run manifest test and release smoke**

Run: `pytest backend/trading_agents_service/tests/test_release_manifest.py -v`

Expected: PASS.

Run the documented staging smoke commands and verify service health, Flask
health, one full run, report retrieval, no public port and a disabled-feature
404 response.

- [ ] **Step 5: Commit release controls**

```powershell
git add backend/.env.example backend/docs/operations/TRADING_AGENTS_RUNBOOK.md backend/trading_agents_service/tests/test_release_manifest.py
git commit -m "docs: add TradingAgents rollout controls"
```

## Plan self-review

- Full upstream graph, agents, tools, providers, checkpoints, memory,
  reflection, raw reports and CLI are covered by Tasks 1–4 and 11.
- DataVest auth, persistence, service security, public API, UI, Smart Insights,
  Compose and rollout are covered by Tasks 5–11.
- No task edits upstream agent/prompt/dataflow code; all DataVest behavior is a
  wrapper boundary.
- No placeholder, floating version or unowned endpoint remains in the plan.
