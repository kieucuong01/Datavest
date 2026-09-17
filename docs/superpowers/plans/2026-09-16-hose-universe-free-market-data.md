# HOSE Universe and Free Market Data Implementation Plan

1. Add failing provider-contract tests for VNDIRECT universe normalization and daily/intraday OHLCV in absolute VND.
2. Add failing orchestration tests for cache, timeout/rate gate, freshness, VNDIRECT-to-Yahoo fallback, and no KB requests.
3. Add failing catalog tests for metadata persistence, safe full-snapshot deactivation, and active-HOSE validation.
4. Add failing TradingAgents route tests proving unknown and inactive VN symbols are rejected before enqueue.
5. Implement the keyless VNDIRECT adapter, Yahoo fallback, and VN data-source orchestration.
6. Extend the market-symbol schema and synchronizer, then wire validation into TradingAgents.
7. Run focused tests, relevant regression tests, lint/compile checks, and refresh the Graphify graph.
