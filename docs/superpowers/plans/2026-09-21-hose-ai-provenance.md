# HOSE AI Discovery and Provenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Make every active HOSE ticker discoverable in Copilot and make HOSE data availability, source, time, currency, and missing-score state truthful across Copilot, Fast Analysis, and TradingAgents.

**Architecture:** Preserve market=VNStock, treat exchange=HOSE as a validated filter, and use the existing symbol master and Vietnam Evidence DTO. Introduce focused provenance and entity-resolution helpers; derive source truth in backend responses and render it consistently in Vue and PDFs.

**Tech Stack:** Python, Flask, PostgreSQL, pytest, Vue 2, Vite, Node test runner, existing VNDIRECT/Yahoo free-provider adapters, ReportLab.

**Spec:** docs/superpowers/specs/2026-09-21-hose-ai-provenance-design.md

## Global Constraints

- Keep market=VNStock and use exchange=HOSE; no new market key or HNX/UPCoM support.
- Research/paper-investing only; no broker execution or paid provider.
- Retain VNDIRECT/Yahoo; do not reintroduce SSI.
- Never call a VN quote real_time or delayed from fetch recency alone. Unknown latency is unknown.
- Preserve point-in-time asOf/availableAt for statements and events.
- Preserve unrelated dirty files, especially graphify-out/. Stage only task files.
- Run ./tools/graphify.ps1 update . after product-code changes; leave generated graph artifacts out of scoped commits.

## Review Focus

1. Accentless Hoa Phat and accented Hòa Phát resolve to the same active HOSE row; neither resolves to a delisted row (Task 1).
2. Ambiguous company words or US/VN ticker collisions do not silently select a HOSE target (Task 2).
3. A quote fetched just now without latency metadata remains unknown, not real_time (Task 3).
4. Empty BCTC/news and absent technical data produce neither invented claims nor neutral 50 nor a directional verdict (Tasks 2 and 4).
5. Older TradingAgents runs without evidence show unknown provenance; new-run PDFs use stored immutable evidence (Task 6).

## File map

| Unit | Responsibility |
| --- | --- |
| app/data/market_symbols_seed.py, services/symbol_master_sync.py, services/market/symbol_search.py, routes/market.py | Active HOSE search and alias contract. |
| services/hose_entity_resolution.py, routes/ai_chat.py | Candidate ranking, ambiguity, market-specific prompt. |
| services/vietnam_provenance.py, services/vietnam_evidence.py | Shared deterministic provenance and coverage. |
| services/fast_analysis_scoring.py, services/fast_analysis.py | Nullable HOSE components and coverage-aware result. |
| frontend/utils/hosePresentation.js, CopilotWorkbench.vue, FastAnalysisReport.vue | Filter, VND, latency, source, time, missing-score rendering. |
| TradingAgents repository/route, services/ai_report_pdf.py, DeepAnalysisPanel.vue | Stored-evidence coverage in API, view, and PDFs. |

### Task 1: Search active HOSE symbols by ticker, name, and alias

**Files:** Modify backend/backend_api_python/app/data/market_symbols_seed.py, app/services/symbol_master_sync.py, app/services/market/symbol_search.py, app/routes/market.py. Create backend/backend_api_python/tests/test_hose_symbol_discovery.py.

**Interfaces:** search_symbols(market: str, keyword: str, limit: int = 20, exchange: str = "") -> list[dict]; search_market_symbols(..., exchange: str = "") -> list[dict]. HOSE results include market, symbol, name, exchange, asset_class, currency.

- [ ] **Step 1: Write failing tests.** Reuse the existing symbol-master fake DB fixture. Assert:

        assert normalize_vn_search("  Hòa   Phát ") == "hoa phat"
        assert normalize_vn_search("HOA PHAT") == "hoa phat"
        assert [r["symbol"] for r in search_symbols("VNStock", "Hoa Phat", exchange="HOSE")] == ["HPG"]
        assert search_symbols("VNStock", "DELISTED_ALIAS", exchange="HOSE") == []
        assert search_symbols("VNStock", "FPT", exchange="HNX") == []

- [ ] **Step 2: Run red tests.** From backend/backend_api_python run: python -m pytest tests/test_hose_symbol_discovery.py -q. Expect missing normalize_vn_search/exchange behavior.
- [ ] **Step 3: Implement.** Normalize Unicode with NFD, strip marks, special-case đ, case-fold, and collapse whitespace. During successful HOSE sync, upsert accentless company-name aliases in qd_market_symbol_aliases without deleting curated aliases. Apply the same active HOSE eligibility predicate as get_active_hose_symbol (including VNDIRECT source, source_updated_at, status and delisting). Return exchange/currency/asset class. Accept exchange in the route; do not uppercase the whole company-name query. Keep non-VN behavior.

        def normalize_vn_search(value: str) -> str:
            text = str(value or "").casefold().replace("đ", "d")
            text = "".join(ch for ch in unicodedata.normalize("NFD", text)
                           if unicodedata.category(ch) != "Mn")
            return " ".join(text.split())

- [ ] **Step 4: Run green/regression tests.** python -m pytest tests/test_hose_symbol_discovery.py tests/test_market_symbol_search_crypto_context.py tests/test_market_symbols_seed_generator.py -q. Expect pass.
- [ ] **Step 5: Commit exact task files.** git commit -m "feat: search active HOSE symbols and Vietnamese aliases".

### Task 2: Resolve Copilot HOSE entities from the symbol master

**Files:** Create backend/backend_api_python/app/services/hose_entity_resolution.py and tests/test_hose_entity_resolution.py. Modify app/routes/ai_chat.py. Extend tests/test_ai_chat_snapshot_quality.py and tests/test_vietnam_evidence.py.

**Interfaces:** rank_hose_candidates(message: str, rows: list[dict], selected_symbol: str = "") -> list[dict]; resolve_hose_request(message, selected, search_fn, validate_fn) -> dict with status resolved/ambiguous/none, target, candidates. No candidate bypasses validate_hose_ai_target.

- [ ] **Step 1: Write failing tests.** Use a ticker absent from the current five VN aliases; add accented-name, selected-context, ambiguous-name, inactive, and US-alias cases. Assert ambiguous/invalid requests never call Vietnam Evidence or quote fetch. Assert missing BCTC/news yields explicit gaps and a HOSE-specific prompt.

        assert resolve_hose_request("Phân tích ABC", {}, search_fn, validate_fn)["target"]["symbol"] == "ABC"
        assert resolve_hose_request("Ngân hàng", {}, ambiguous_search, validate_fn)["status"] == "ambiguous"
        assert resolve_hose_request("Phân tích FPT", {"market": "VNStock", "symbol": "FPT"},
                                    search_fn, validate_fn)["status"] == "resolved"

- [ ] **Step 2: Run red tests.** python -m pytest tests/test_hose_entity_resolution.py tests/test_ai_chat_snapshot_quality.py -q. Expect new resolver tests fail.
- [ ] **Step 3: Implement.** Extract ticker tokens and Vietnamese 2–6-word phrase windows; query Task 1 active catalog; rank explicit selection/exact ticker above name matches; return ambiguity on ties. Remove only the five VN entries from _COMMON_ENTITY_ALIASES. In _build_research_context stop before evidence fetch on ambiguity. In _build_system_prompt add Vietnam-specific policy for validated HOSE targets: VND, no US assumptions, no unsupported BCTC/headlines, cite gaps. Avoid default 50 on no-evidence HOSE parse fallback.

        if resolution["status"] == "ambiguous":
            return {"entities": {"candidates": resolution["candidates"]},
                    "data_gaps": [{"field": "instrument", "reason": "AMBIGUOUS_HOSE_TARGET"}]}

- [ ] **Step 4: Run green/regression tests.** python -m pytest tests/test_hose_entity_resolution.py tests/test_ai_chat_snapshot_quality.py tests/test_vietnam_evidence.py -q. Expect pass.
- [ ] **Step 5: Commit exact task files.** git commit -m "feat: resolve HOSE Copilot entities from symbol master".

### Task 3: Derive truthful HOSE provenance and coverage

**Files:** Create backend/backend_api_python/app/services/vietnam_provenance.py and tests/test_vietnam_provenance.py. Modify app/services/vietnam_evidence.py and app/services/market_data_collector.py only where source metadata must be carried; extend tests/test_vietnam_evidence.py.

**Interfaces:** build_hose_provenance(evidence: Mapping[str, Any], *, fetched_at: datetime | None = None, news: list[dict] | None = None, news_requested: bool = False) -> dict with exchange, currency, price {source, observedAt, fetchedAt, latencyClass, delayMinutes}, coverage {price, technical, fundamentals, news, corporateActions, disclosures}, dataGaps and sources. Each coverage entry has status available/missing/unavailable/not_requested and reason. None news plus news_requested=False means not_requested; a requested but uncaptured news feed is unavailable, not evidence that no news exists.

- [ ] **Step 1: Write failing tests.** Daily bar -> eod; provider-verified delay -> delayed; fresh quote without metadata -> unknown; fetchedAt is never substituted for observedAt; empty statements stay missing.

        assert build_hose_provenance({"instrument": {"exchange": "HOSE"},
            "price": {"source": "yahoo", "timeframe": "1D", "time": "2026-09-18T08:00:00Z"}})["price"]["latencyClass"] == "eod"
        assert build_hose_provenance({"instrument": {"exchange": "HOSE"},
            "price": {"source": "vndirect", "price": 120000}})["price"]["latencyClass"] == "unknown"

- [ ] **Step 2: Run red tests.** python -m pytest tests/test_vietnam_provenance.py -q. Expect import failure.
- [ ] **Step 3: Implement.** Derive actual source from observation; accept real_time/delayed only from verified normalized provider metadata, EOD only from known daily bars, otherwise unknown. Parse market observation time separately from fetch time. Derive news coverage from explicit news/news_requested inputs, never from disclosures. Attach provenance to HOSE Evidence/result envelopes without changing point-in-time filtering. Keep absent fields null and structured gap reasons.

        latency = ("eod" if price.get("timeframe") == "1D"
                   else explicit_latency if explicit_latency in {"real_time", "delayed"}
                   else "unknown")
        observed_at = parse_provider_instant(price.get("time") or price.get("timestamp"))

- [ ] **Step 4: Run green/regression tests.** python -m pytest tests/test_vietnam_provenance.py tests/test_vietnam_evidence.py tests/test_trading_agents_vietnam.py -q. Expect pass.
- [ ] **Step 5: Commit exact task files.** git commit -m "feat: expose verified HOSE data provenance".

### Task 4: Make HOSE Fast Analysis coverage-aware

**Files:** Modify backend/backend_api_python/app/services/fast_analysis_scoring.py and app/services/fast_analysis.py. Extend tests/test_fast_analysis_scoring.py, tests/test_fast_analysis_history_contract.py and tests/test_vietnam_evidence.py.

**Interfaces:** HOSE scores values are numeric only with matching evidence, otherwise None; score_coverage contains components, partial and dataGaps; provenance is Task 3 output. All-missing result: overall=None, decision=INSUFFICIENT_DATA, confidence=None. Non-HOSE numeric API remains backward-compatible.

- [ ] **Step 1: Write failing tests.** Pin no BCTC, no news, price-only, and no-price cases. Missing fundamental/sentiment may not return 50 or dilute weighted average; no-price case may not issue BUY/SELL/HOLD.

        result = service._calculate_objective_score(
            {"market": "VNStock", "indicators": {}, "fundamental": {},
             "news": [], "macro": {}, "price": {}}, 0)
        assert result["fundamental_score"] is None
        assert result["sentiment_score"] is None
        assert result["overall_score"] is None

- [ ] **Step 2: Run red tests.** python -m pytest tests/test_fast_analysis_scoring.py tests/test_fast_analysis_history_contract.py -q. Expect new HOSE assertions fail.
- [ ] **Step 3: Implement.** For market=VNStock, determine component presence from actual indicators, Evidence observations/derived metrics, news and macro. Keep objective -100..100 scale distinct from display score/confidence. Renormalize existing weights only over present components; skip unavailable timeframes in consensus; return insufficient data when no usable price/technical evidence. Map unavailable display scores to None instead of 50; attach Task 3 provenance and coverage before persistence. Keep US/Crypto/Forex branch unchanged.

        present = {k: v for k, v in component_scores.items() if v is not None}
        overall = (sum(present[k] * weights[k] for k in present)
                   / sum(weights[k] for k in present)) if present else None

- [ ] **Step 4: Run green/regression tests.** python -m pytest tests/test_fast_analysis_scoring.py tests/test_fast_analysis_history_contract.py tests/test_vietnam_evidence.py -q. Expect pass.
- [ ] **Step 5: Commit exact task files.** git commit -m "fix: mark missing HOSE analysis scores unavailable".

### Task 5: Render HOSE filter, VND, freshness and gaps in Copilot/Fast UI

**Files:** Create frontend/src/utils/hosePresentation.js and frontend/tests/unit/hosePresentation.test.mjs. Modify frontend/src/views/ai-analysis/components/CopilotWorkbench.vue, FastAnalysisReport.vue, and src/api/market.js only if query serialization needs it. Add focused strings in src/locales/lang/vi-VN.js and en-US.js where necessary.

**Interfaces:** hosePriceLabel(value), hoseLatencyLabel(provenance, language), hoseScoreLabel(score, language), and hoseCoverageRows(coverage) are pure helpers. Picker sends market=VNStock and exchange=HOSE; persisted context remains VNStock.

- [ ] **Step 1: Write failing Node tests.** Pin 120000 VND, no dollar sign, null score as Không đủ dữ liệu, unknown latency, and no manual HOSE fallback after search error. Add an existing-style component source-contract test asserting the visible HOSE tab and source/observed/fetched labels.

        assert.equal(hosePriceLabel(120000), '120.000 VND')
        assert.equal(hoseLatencyLabel({price: {latencyClass: 'unknown'}}, 'vi-VN'), 'Chưa xác định')
        assert.equal(hoseScoreLabel(null, 'vi-VN'), 'Không đủ dữ liệu')

- [ ] **Step 2: Run red tests.** From frontend run: node --test tests/unit/hosePresentation.test.mjs. Expect missing module.
- [ ] **Step 3: Implement.** Surface HOSE filter/tab in Copilot search/watchlist; send server filter and render exchange. Remove manual typed-symbol fallback for VNStock on empty/error. Carry Task 3 provenance into answer/quote cards. In Fast Analysis, replace hard-coded dollar sign for VNStock with VND and all display fallback expressions of the form score || 50 with null-aware rendering; hide numeric progress for missing scores and mark partial overall. Leave non-VN currency unchanged.

        const hasScore = score => score === 0 || (score != null && Number.isFinite(Number(score)))
        const displayedPrice = result.market === 'VNStock'
          ? hosePriceLabel(price) : '$' + formatPrice(price)

- [ ] **Step 4: Run green/regression tests.** node --test tests/unit/hosePresentation.test.mjs tests/unit/supportedMarkets.test.mjs tests/unit/tradingAgentsDeepAnalysis.test.mjs, then npm run build. Expect pass.
- [ ] **Step 5: Commit exact task files.** git commit -m "feat: show HOSE provenance and missing data in AI UI".

### Task 6: Show immutable TradingAgents coverage in API, view and PDF

**Files:** Modify backend/backend_api_python/app/services/trading_agents_repository.py, app/routes/trading_agents.py, app/services/ai_report_pdf.py, app/services/trading_agents_vietnam.py. Extend tests/test_trading_agents_routes.py, tests/test_trading_agents_report_pdf.py, tests/test_trading_agents_vietnam.py. Modify frontend/src/components/TradingAgents/DeepAnalysisPanel.vue and extend frontend/tests/unit/tradingAgentsDeepAnalysis.test.mjs.

**Interfaces:** _public_evidence_provenance(record) keeps old fields and adds Task 3 price, coverage, dataGaps, exchange and currency from stored evidence_json projection. build_trading_agents_report_pdf(..., evidence: dict | None = None) and summary variant accept that deterministic projection. Older records without evidence return unknown provenance.

- [ ] **Step 1: Write failing tests.** New stored HOSE run exposes source/time/coverage/gaps in API and both PDFs; old run shows unknown. PDF text extraction must contain HOSE, VND, source, data status and absent BCTC/news reasons. Confirm owned-run evidence and SHA-256 verified artifact are used, never browser-supplied content.

        assert public_run["evidence"]["coverage"]["fundamentals"]["status"] == "missing"
        pdf = build_trading_agents_report_pdf(
            content=report, market="VNStock", symbol="FPT",
            analysis_date="2026-09-21", language="vi-VN", run_id="run-1",
            evidence=provenance)
        assert "VND" in " ".join(page.extract_text() or ""
                                 for page in PdfReader(BytesIO(pdf)).pages)

- [ ] **Step 2: Run red tests.** python -m pytest tests/test_trading_agents_routes.py tests/test_trading_agents_report_pdf.py tests/test_trading_agents_vietnam.py -q. Expect new contract assertions fail.
- [ ] **Step 3: Implement.** Project only needed fields from persisted evidence_json; do not expose full filings or exceed response bounds. Generate deterministic coverage block in both PDFs apart from model-authored prose. Show same block in DeepAnalysisPanel.vue above PDF reader. Older records show unknown source/time. Replace assumed vndirect+yahoo source default in daily-bar builder with unknown when source is absent, and tag its known 1D price bar with timeframe=1D. Pass news_requested=True when the run searched news but its results were not captured in evidence.

        evidence = build_hose_provenance(stored_evidence) if stored_evidence else None
        pdf_bytes = build_trading_agents_report_pdf(
            content=report_text, market=market, symbol=symbol,
            analysis_date=analysis_date, language=language,
            run_id=run_id, evidence=evidence)

- [ ] **Step 4: Run green/regression tests.** From backend/backend_api_python: python -m pytest tests/test_trading_agents_routes.py tests/test_trading_agents_report_pdf.py tests/test_trading_agents_vietnam.py -q. From frontend: node --test tests/unit/tradingAgentsDeepAnalysis.test.mjs tests/unit/tradingAgentsReport.test.mjs; then npm run build. Expect pass.
- [ ] **Step 5: Commit exact task files.** git commit -m "feat: expose HOSE evidence coverage in deep reports".

## Final verification and handoff

- Run focused backend suites above, full backend suite if feasible, npm run test:unit, npm run build, and ./tools/graphify.ps1 update .; report each actual result.
- Run a read-only FPT HOSE free-provider smoke only if network is available; label it separately from mocked proof.
- Inspect git diff --check, git status --short and exact commit SHAs. Do not push or deploy without an explicit release request.
