# HOSE Copilot parity implementation plan

> **For Codex:** Execute this plan inline, task by task, using test-driven development. Do not merge, push, or deploy unless the user asks for it after the implementation is verified.

## Goal

Bring HOSE analysis in Fast Analysis and AI Copilot to the same evidence-aware
reporting contract as US stocks, while retaining VNDIRECT as the free Vietnam
fundamental/event source and Yahoo only as the bounded OHLCV fallback.

## Architecture

```text
Fast Analysis / Copilot target
  -> active-market instrument resolver
  -> normalized market research evidence
  -> coverage policy and score eligibility
  -> shared analysis report contract
  -> shared presentation, localized by market provenance
```

The normalized evidence layer is deliberately narrow. It wraps existing US/Crypto
data without changing their public payload and projects the existing Vietnam
Evidence DTO plus HOSE provenance into the same coverage contract. Scoring and
presentation consume that contract; they do not infer availability from a numeric
field alone.

## Tech stack

- Python/FastAPI services and pytest for research collection, coverage and scoring.
- Existing VNDIRECT adapter for HOSE fundamentals/events; Yahoo for OHLCV fallback.
- Vue 3 component presentation with node unit tests.
- Existing active-HOSE symbol master and resolver; no static Vietnamese ticker map.

## Approved design

`docs/superpowers/specs/2026-09-21-hose-copilot-parity-design.md`

## Global constraints

- Research only: no broker execution, trading advice guarantee, paid provider, or SSI API.
- Never present free EOD/delayed data as real time; retain provider, observation time,
  fetch time and latency class.
- Every Vietnam financial/event observation must preserve `period_end`,
  `available_at`, and `source`.
- A coverage state of `partial`, `missing`, or `unavailable` makes the related
  score `null`; it must never become a synthetic 50 or 100.
- Preserve USStock and Crypto report schemas and numerical behavior unless a
  shared, explicitly tested coverage field is additive.
- Do not make client aliases authoritative for Vietnamese companies. The active
  HOSE catalog is the sole authority for code, name, accentless name and aliases.

## Review focus

Each task below must explicitly test its relevant failure mode:

1. A company-name collision must return candidates, never silently choose a HOSE
   or US ticker.
2. An inactive, delisted or non-HOSE code must remain rejected even when the
   client suggests it.
3. A partial BCTC (for example unknown reporting scope or incomplete point-in-
   time observations) must not generate a fundamental score.
4. A Yahoo daily quote must retain `eod`/delayed provenance and never render as
   real-time Vietnam data.
5. USStock and Crypto scoring/report behavior must stay regression-compatible.

---

### Task 1: Create the normalized research-evidence and coverage policy

**Files**

- Create: `backend/backend_api_python/app/services/market_research_evidence.py`
- Modify: `backend/backend_api_python/app/services/vietnam_provenance.py`
- Create: `backend/backend_api_python/tests/test_market_research_evidence.py`
- Modify: `backend/backend_api_python/tests/test_vietnam_provenance.py`

**Implementation**

1. Start with deterministic pytest fixtures that cover an EOD Yahoo price, a
   complete VNDIRECT observation, an unknown report scope, missing news, and a
   non-VN generic market payload. Assert the intended `coverage`,
   `scoreEligibility`, source and time fields before adding service code.
2. Add `build_market_research_evidence(market, data, *, fetched_at,
   news_requested)` that returns a stable dict containing `instrument`, `price`,
   `technical`, `fundamentals`, `corporateActions`, `disclosures`, `news`,
   `marketContext`, `coverage`, `scoreEligibility`, `dataGaps`, and `sources`.
   It must be a projection only: no provider calls and no mutation of `data`.
3. For `VNStock`, call `build_hose_provenance` and map its coverage into a
   three-state score policy. Technical requires usable price plus indicators;
   fundamentals require point-in-time observations with a known report scope and
   no fundamental provider gap; sentiment requires captured non-empty news;
   macro requires a populated market-context observation. Set each non-eligible
   component to `partial`, `missing`, or `unavailable` with a machine-readable
   reason.
4. Extend `build_hose_provenance` so a present but incomplete financial payload is
   `partial` rather than `available`; preserve existing provider-unavailable,
   point-in-time, source, observation and latency behavior. Do not classify a
   bare derived metric as complete BCTC evidence.
5. For USStock/Crypto, emit the same additive evidence keys from already-collected
   data, but leave their current score eligibility permissive so existing scoring
   output does not change. Tests must snapshot this compatibility behavior.

**Verification**

```powershell
pytest tests/test_market_research_evidence.py tests/test_vietnam_provenance.py -q
```

**Review checkpoints**

- Partial VNDIRECT evidence has a null fundamental eligibility decision.
- Daily Yahoo provenance remains `eod`, includes observation/fetch time, and is
  not upgraded to real-time.
- The generic US/Crypto projection does not alter input data or existing scores.

**Commit**

```powershell
git add backend/backend_api_python/app/services/market_research_evidence.py backend/backend_api_python/app/services/vietnam_provenance.py backend/backend_api_python/tests/test_market_research_evidence.py backend/backend_api_python/tests/test_vietnam_provenance.py
git commit -m "feat: normalize market research evidence coverage"
```

---

### Task 2: Gate HOSE scores and serialize the shared Fast Analysis report

**Files**

- Modify: `backend/backend_api_python/app/services/fast_analysis.py`
- Modify: `backend/backend_api_python/app/services/fast_analysis_scoring.py`
- Modify: `backend/backend_api_python/tests/test_fast_analysis_scoring.py`
- Create: `backend/backend_api_python/tests/test_fast_analysis_hose_contract.py`

**Implementation**

1. First add tests for the current failure: partial HOSE BCTC plus valid technical
   data must yield a technical score but `fundamental_score is None`; absent news
   must yield `sentiment_score is None`; the report must retain the coverage
   reasons and must not contain calculated action levels requiring unavailable
   inputs. Add companion USStock/Crypto regression cases for unchanged score
   fields.
2. Extend `_calculate_objective_score` with an optional normalized-evidence/
   coverage argument. Apply the policy only for `VNStock`: calculate a component
   only when `scoreEligibility[component]` is eligible, then recompute the
   weighted overall score from eligible components. Keep the existing call path
   and exact defaults for USStock/Crypto.
3. In `FastAnalysisService`, build normalized evidence once after market data is
   collected. Replace the reduced HOSE-only report construction with a
   coverage-aware serializer that produces the same top-level report sections
   consumed by the common report renderer: summary, scores, detailed analysis,
   reasons, trading plan, provenance, `score_coverage`, sources and data gaps.
   Use market-neutral section construction; use HOSE-specific text only for
   currency, exchange and source/latency facts.
4. Populate a narrative section only from its eligible evidence. For a missing or
   partial component emit an explicit unavailable section and reason instead of a
   blank string, default sentiment, fundamental score, or fabricated action plan.
   Retain the existing Vietnamese-safe LLM policy, and only request narrative
   expansion when the corresponding evidence is eligible.
5. Make entry, stop-loss, take-profit and final decision conditional on the
   required technical coverage; serialize them as absent/unavailable otherwise.
   Preserve the standard response keys so FastAnalysisReport does not need a
   separate HOSE layout.

**Verification**

```powershell
pytest tests/test_fast_analysis_scoring.py tests/test_fast_analysis_hose_contract.py -q
```

**Review checkpoints**

- The former FPT-style scenario cannot display a 100 fundamental score when BCTC
  scope/evidence is incomplete.
- A valid HOSE technical-only report has an explicit fundamental/news gap, not a
  weakened or synthetic “neutral” score.
- USStock and Crypto snapshots preserve their score values and payload keys.

**Commit**

```powershell
git add backend/backend_api_python/app/services/fast_analysis.py backend/backend_api_python/app/services/fast_analysis_scoring.py backend/backend_api_python/tests/test_fast_analysis_scoring.py backend/backend_api_python/tests/test_fast_analysis_hose_contract.py
git commit -m "feat: gate HOSE fast analysis by evidence coverage"
```

---

### Task 3: Make server-side HOSE resolution authoritative in Copilot

**Files**

- Modify: `backend/backend_api_python/app/services/hose_entity_resolution.py`
- Modify: `backend/backend_api_python/app/routes/ai_chat.py`
- Modify: `backend/backend_api_python/tests/test_hose_entity_resolution.py`
- Modify: `backend/backend_api_python/tests/test_ai_chat_snapshot_quality.py`
- Modify: `frontend/src/views/ai-analysis/components/CopilotWorkbench.vue`
- Modify: `frontend/tests/unit/hosePresentation.test.mjs`

**Implementation**

1. Add resolver fixtures first for active code, official company name, accentless
   Vietnamese name, stored alias, ambiguous name, inactive/delisted code and a
   US/HOSE collision. Assert the resolver returns `resolved`, `ambiguous`, or
   `none` with candidates; never a guessed target.
2. Tighten `resolve_hose_request` and its `ai_chat` projection so every accepted
   HOSE target includes the canonical symbol-master instrument and every
   ambiguity/missing result becomes a structured research gap visible to the
   prompt and response. Retain server-side validation immediately before data
   collection.
3. Remove FPT/VCB and every other VNStock entry from
   `CopilotWorkbench.commonSymbolAliases`. Keep only explicit market syntax,
   selected symbol-picker values, and non-Vietnam convenience hints client-side.
   For natural Vietnamese language, leave the context unresolved so the server
   resolver can use the active HOSE master; never select the first generic search
   result merely because it looks plausible.
4. Ensure a server-resolved canonical HOSE instrument is reflected in the Copilot
   context and response metadata. The prompt must use normalized evidence and
   coverage and must state unresolved/ambiguous data gaps rather than assuming
   USD, SEC filings, real-time quote or missing BCTC/news facts.

**Verification**

```powershell
pytest tests/test_hose_entity_resolution.py tests/test_ai_chat_snapshot_quality.py -q
npm run test:unit -- --runInBand tests/unit/hosePresentation.test.mjs
```

**Review checkpoints**

- No static Vietnamese alias can override a delisted or non-HOSE catalog result.
- Accentless name and stored alias resolve through the catalog fixture.
- An ambiguous query provides selectable candidates rather than an automatic FPT,
  VCB, USStock or Crypto context.

**Commit**

```powershell
git add backend/backend_api_python/app/services/hose_entity_resolution.py backend/backend_api_python/app/routes/ai_chat.py backend/backend_api_python/tests/test_hose_entity_resolution.py backend/backend_api_python/tests/test_ai_chat_snapshot_quality.py frontend/src/views/ai-analysis/components/CopilotWorkbench.vue frontend/tests/unit/hosePresentation.test.mjs
git commit -m "feat: resolve HOSE Copilot targets from symbol master"
```

---

### Task 4: Render coverage, provenance and unavailable sections consistently

**Files**

- Modify: `frontend/src/utils/hosePresentation.js`
- Modify: `frontend/src/views/ai-analysis/components/FastAnalysisReport.vue`
- Modify: `frontend/tests/unit/hosePresentation.test.mjs`

**Implementation**

1. Begin with unit cases for available, partial, missing and unavailable coverage
   in Vietnamese and English. Assert that null scores render as an explicit
   unavailable state, never `0`, `50`, `100`, `N/A` without reason, or a USD
   amount for a HOSE instrument.
2. Extend the presentation helper with stable label/status functions for coverage
   and score eligibility. Keep `hosePriceLabel` and `hoseLatencyLabel` as the
   only currency/latency specializations; normalize all other display decisions
   from the shared `score_coverage` contract.
3. Update FastAnalysisReport’s existing common template to show exchange, VND,
   source, observation time, fetch time and latency together with each coverage
   state/reason. For unavailable analysis dimensions, render an explicit data-gap
   section and suppress unsupported decision/action values. Do not create a
   separate HOSE report component.
4. Keep USStock/Crypto visual paths intact. The additional coverage display must
   be conditional on contract data and must not replace valid generic score cards.

**Verification**

```powershell
npm run test:unit -- --runInBand tests/unit/hosePresentation.test.mjs
npm run build
```

**Review checkpoints**

- A delayed/EOD HOSE report visibly distinguishes price freshness from source
  fetch time.
- Partial BCTC/news appears as a reasoned data gap and removes the associated
  score/action claim.
- The component uses the shared renderer, not a market-specific duplicate.

**Commit**

```powershell
git add frontend/src/utils/hosePresentation.js frontend/src/views/ai-analysis/components/FastAnalysisReport.vue frontend/tests/unit/hosePresentation.test.mjs
git commit -m "feat: show HOSE evidence coverage in analysis reports"
```

---

### Task 5: Run end-to-end regression and perform a non-mutating acceptance smoke

**Files**

- Modify only if a concrete failing test proves a defect in one of the files
  above. Do not broaden provider scope in this task.

**Implementation and verification**

1. Run the focused backend tests from Tasks 1–3, frontend unit test and production
   build. Fix only proven regressions using a new red test before implementation.
2. Run the relevant broader backend suite if it is deterministic in this worktree.
   Record any pre-existing environmental failures separately from code failures.
3. Start/use the local application only if required for a rendered smoke. Inspect
   symbol search for a known active HOSE name/code and an existing saved HOSE
   report. Do not submit a new Copilot/LLM request or consume user credits.
4. Before reporting completion, inspect `git diff --check`, `git status --short`,
   the commits created by this plan, and the final test/build output. Preserve
   unrelated files; do not stage Graphify cache/output or test artifacts.

**Verification**

```powershell
pytest tests/test_market_research_evidence.py tests/test_vietnam_provenance.py tests/test_fast_analysis_scoring.py tests/test_fast_analysis_hose_contract.py tests/test_hose_entity_resolution.py tests/test_ai_chat_snapshot_quality.py -q
npm run test:unit -- --runInBand tests/unit/hosePresentation.test.mjs
npm run build
git diff --check
git status --short
```

**Review checkpoints**

- No paid/SSI dependency or new live provider call was introduced.
- Tests cover every Review focus item and no report claims data outside its
  normalized evidence.
- The final branch contains only the intended commits and no incidental cache,
  Graphify or test-output artifacts.

**Commit**

Create a final corrective commit only if Task 5 fixes a verified defect:

```powershell
git add <only-intended-files>
git commit -m "fix: verify HOSE Copilot parity regressions"
```

