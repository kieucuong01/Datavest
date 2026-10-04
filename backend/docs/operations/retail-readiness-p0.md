# Retail readiness P0 delivery

Implement the three approved audit priorities sequentially, with one commit per task. Do not include unrelated dirty Graphify files or local artifacts. No new provider/model dependencies or deployment are required for these commits.

## Task 1 — Portfolio valuation

Native VND, USD and USDT amounts are grouped separately; the API does not infer an FX rate. The portfolio UI selects one currency group for totals, allocation and concentration. Crypto quantity is tokens, Vietnamese equities use shares, and XAUUSD uses troy ounces (not SJC taels).

Missing, non-finite, non-positive or explicitly unavailable quotes produce null current value/P&L. Incomplete groups expose priced position coverage and the sum of priced values separately; total NAV/P&L remains unavailable. Stale quotes retain their value with a warning and provider timestamps. Empty and fully priced single-currency portfolios retain numeric totals.

Regression checks cover mixed currencies, missing/partial quotes, stale quotes and single-currency compatibility. Verify optimizer-to-manual-position compatibility. FX conversion can be added only with a verified rate source and an explicit USD/USDT policy.

## Task 2 — Research output lifecycle

Trace observation-to-snapshot and weekly publication wiring, repair safe job recovery, and expose report expiry. Verify period deduplication, retry boundaries and preservation of watchlist authorization. Test faults without creating live AI runs.

Collector refresh now materializes evidence snapshots with a distinct v2 methodology and no synthetic opinion/confidence rows. Market bars are not forced into crypto-only refresh metadata. Weekly public jobs claim the Vietnamese Monday period before creating a run; worker redelivery must atomically reserve its source run. Sync retries artifact transport against the same run, and checks current-period public gaps every 15 minutes after Monday 08:00.

Apply `20261005_research_report_recovery.sql` before using the new code (included in startup migrations). Claims are capped at three per period, with a 15-minute cooldown. Only confirmed failed/cancelled TradingAgents runs, pre-generation dispatch failures, and pending rows without a source run older than three hours can be reclaimed. Active runs and ambiguous `enqueue_failed`/old `sync_failed` rows require operator reconciliation against the original run; do not generate a replacement blindly. Old workers cannot overwrite a newer source run.

Reports expire at the next Vietnamese Monday 00:00, based on evidence period rather than generation time. API exposes validity; the list suppresses expired recommendation/action cards while the reader retains a historical-context warning. Prometheus monitors output age and probe failure independently of worker heartbeats. Regression checks use fake queues/artifacts and do not trigger paid AI calls. PostgreSQL migration/concurrency and production freshness still require release-time verification.

## Task 3 — Data freshness and comparison periods

Validate source age and effective period per widget. Mismatched/expired whale and exchange observations must not produce a conflicting directional interpretation. Preserve unavailable values as null, including UI formatting. Keep auxiliary sources out of the default refresh scope when they cannot contribute reliable current evidence.

## Release boundary

These are local code commits. Existing production snapshots and failed jobs are not repaired merely by committing; after deployment, verify current output and any approved reconciliation separately.
