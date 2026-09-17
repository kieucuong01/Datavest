# Vietnam Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shared, point-in-time Vietnam equity evidence DTO and make Fast Analysis and AI Chat consume it.

**Architecture:** Extend the existing VNDIRECT adapter with normalized non-price evidence, then assemble it in a focused service that owns point-in-time filtering and compatibility mapping. Consumers receive one DTO; unavailable free datasets remain explicit gaps.

**Tech Stack:** Python 3.12, Flask, requests, PostgreSQL, pytest.

**Spec:** `docs/superpowers/specs/2026-09-17-vietnam-evidence-design.md`

## Global Constraints

- Use only free VNDIRECT and Yahoo endpoints; Yahoo is price fallback only.
- Preserve the research/paper-investing-only product boundary.
- Do not emit financial observations that were unavailable at the requested analysis time.
- Do not fabricate foreign room or ownership data.
- Preserve unrelated dirty working-tree changes and do not create a commit unless requested.

---

### Task 1: VNDIRECT evidence normalization

**Files:**
- Modify: `backend/backend_api_python/app/data_sources/vn_market_providers.py`
- Test: `backend/backend_api_python/tests/test_vietnam_evidence.py`

**Interfaces:**
- Produces: `fetch_financial_statements(symbol)`, `fetch_company_profile(symbol)`, and `fetch_events(symbol)` returning normalized dictionaries with source metadata.

- [ ] Write tests with complete VNDIRECT response fixtures for consolidated/separate statements, profile, dividends, and disclosures.
- [ ] Run the tests and confirm they fail because the provider methods do not exist.
- [ ] Implement paged VNDIRECT reads, timestamp normalization, report-scope normalization, and malformed-row filtering.
- [ ] Run the provider tests and confirm they pass.

### Task 2: Shared point-in-time DTO and persistence schema

**Files:**
- Create: `backend/backend_api_python/app/services/vietnam_evidence.py`
- Create: `backend/backend_api_python/migrations/20260917_vietnam_evidence.sql`
- Modify: `backend/backend_api_python/migrations/init.sql`
- Test: `backend/backend_api_python/tests/test_vietnam_evidence.py`

**Interfaces:**
- Produces: `VietnamEvidenceService.build(symbol, price, technical, as_of)` and `get_vietnam_evidence_service()`.

- [ ] Write tests proving future observations are excluded, report scope is preserved, percentage units are normalized, and unavailable room/ownership become gaps.
- [ ] Run the tests and confirm the service import or behavior fails.
- [ ] Implement immutable contract assembly, derived metrics, source registry, market context, and best-effort repository persistence.
- [ ] Add idempotent PostgreSQL tables for observations and events to both migration paths.
- [ ] Run the service tests and confirm they pass.

### Task 3: Fast Analysis compatibility

**Files:**
- Modify: `backend/backend_api_python/app/services/market_data_collector.py`
- Modify: `backend/backend_api_python/app/services/fast_analysis.py`
- Modify: `backend/backend_api_python/app/services/fast_analysis_scoring.py`
- Test: `backend/backend_api_python/tests/test_vietnam_evidence.py`
- Test: `backend/backend_api_python/tests/test_fast_analysis_scoring.py`

**Interfaces:**
- Consumes: `VietnamEvidenceService.build(...)`.
- Produces: `data.vietnam_evidence`, legacy `fundamental`, `company`, and evidence-aware provenance.

- [ ] Write failing tests for VN collector compatibility and provenance components.
- [ ] Attach evidence after price/technical collection and map canonical metrics into the legacy Fast Analysis shape.
- [ ] Include evidence checksum, provider sources, fundamental/actions/disclosures components, and data gaps in input provenance.
- [ ] Run focused Fast Analysis tests.

### Task 4: AI Chat shared evidence and inferred-symbol validation

**Files:**
- Modify: `backend/backend_api_python/app/routes/ai_chat.py`
- Test: `backend/backend_api_python/tests/test_vietnam_evidence.py`

**Interfaces:**
- Consumes: `VietnamEvidenceService.build(...)`.
- Produces: `research_context.vietnamEvidence` and structured VN `fundamentals`.

- [ ] Write failing tests proving VN chat uses structured evidence and rejects an inferred non-HOSE symbol before provider calls.
- [ ] Build evidence from selected/inferred VN context, merge its gaps, and retain search as supplemental news only.
- [ ] Validate inferred VN candidates through `validate_hose_ai_target`.
- [ ] Run focused AI Chat tests.

### Task 5: Provider provenance and regression verification

**Files:**
- Modify: `backend/backend_api_python/app/services/kline.py`
- Test: `backend/backend_api_python/tests/test_vietnam_evidence.py`

**Interfaces:**
- Produces: realtime price `source` equal to the actual adapter provider when available.

- [ ] Write a failing test showing VNDIRECT/Yahoo provider names are lost behind the generic `ticker` source.
- [ ] Preserve `ticker.provider` or bar provider in realtime price results while keeping generic fallback names for other markets.
- [ ] Run the Vietnam Evidence, VN market data, Fast Analysis, AI Chat, and fundamental-data suites.
- [ ] Run Ruff/compile checks on modified Python files and update Graphify incrementally.
