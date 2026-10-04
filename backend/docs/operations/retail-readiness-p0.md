# Retail readiness P0 delivery

Implement the three approved audit priorities sequentially, with one commit per task. Do not include unrelated dirty Graphify files or local artifacts. No new provider/model dependencies or deployment are required for these commits.

## Task 1 — Portfolio valuation

Native VND, USD and USDT amounts are grouped separately; the API does not infer an FX rate. The portfolio UI selects one currency group for totals, allocation and concentration. Crypto quantity is tokens, Vietnamese equities use shares, and XAUUSD uses troy ounces (not SJC taels).

Missing, non-finite, non-positive or explicitly unavailable quotes produce null current value/P&L. Incomplete groups expose priced position coverage and the sum of priced values separately; total NAV/P&L remains unavailable. Stale quotes retain their value with a warning and provider timestamps. Empty and fully priced single-currency portfolios retain numeric totals.

Regression checks cover mixed currencies, missing/partial quotes, stale quotes and single-currency compatibility. Verify optimizer-to-manual-position compatibility. FX conversion can be added only with a verified rate source and an explicit USD/USDT policy.

## Task 2 — Research output lifecycle

Trace observation-to-snapshot and weekly publication wiring, repair safe job recovery, and expose report expiry. Verify period deduplication, retry boundaries and preservation of watchlist authorization. Test faults without creating live AI runs.

## Task 3 — Data freshness and comparison periods

Validate source age and effective period per widget. Mismatched/expired whale and exchange observations must not produce a conflicting directional interpretation. Preserve unavailable values as null, including UI formatting. Keep auxiliary sources out of the default refresh scope when they cannot contribute reliable current evidence.

## Release boundary

These are local code commits. Existing production snapshots and failed jobs are not repaired merely by committing; after deployment, verify current output and any approved reconciliation separately.
