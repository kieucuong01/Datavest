# HOSE watchlist research pilot

The discovery registry is `app/services/hose_research.py`: FPT (technology), HPG (steel), VCB (banking). These are representative sectors with existing adapters, not a current liquidity ranking or buy recommendation. `GET /api/smart-insights/public/hose-pilot` returns only this registry and the VNINDEX/VN30 benchmark names. It reads no account history and launches no jobs. The fixed guest report and weekly public scheduling scope remains unchanged.

Smart Insights offers add-to-watchlist and open-research actions. Adding uses the existing authenticated, catalog-validated watchlist endpoint; unavailable/inactive symbols are rejected. Research continues through the existing TradingAgents run flow or an already published shared watchlist report. No AI job is started by viewing this pilot section.

New VNStock runs include point-in-time daily VNINDEX/VN30 context. Future bars are excluded and unavailable benchmarks add explicit gaps. These indices are reference context, never pilot positions. The evidence checksum is resealed before write-once persistence and private-service dispatch.

The reader shows an allowlisted projection of that same frozen snapshot: daily VND price/volume, trade date/retrieval date, financial period/availability/source/scope, like-for-like YoY growth, captured events, and gaps. Bank operating income remains separate from revenue. Unknown statement scope is partial. P/E may derive from a positive, dated annual EPS in VND with verified scope; P/B without verified inputs remains unavailable. Provider availability dates are proxies, not verified exchange filing timestamps. Daily prices more than three Vietnamese weekdays behind the report cutoff are stale; holiday coverage is approximate.

Old reports without the projection are retained without current-data backfill. The task is validated locally with controlled providers and UI fixtures; production provider availability, authenticated end-to-end runs and a stable publication week must still be verified after release.
