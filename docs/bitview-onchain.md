# Free BTC on-chain data — Bitview

Provider: https://bitview.space/llms.txt and `/api/series/<identifier>` metadata.
Verified from the public API on 2026-09-11. No key, subscription, browser worker,
LLM, or self-hosted Bitcoin node is required. Hosted uptime is not guaranteed.

## Data contract

- Daily NUPL, MVRV, Supply in Profit (already percent; do not multiply by 100), trailing-24h SOPR.
- LTH/STH supply in BTC; aggregate and cohort realized prices in USD/BTC.
- BRK LTH is **at least 150 days**; STH is younger than 150 days.
- HODL Waves are seven non-overlapping bands: 0–30, 30–90, 90–180,
  180–365, 365–730, 730–1095, and 1095+ days. Compute adjacent differences
  of cumulative age supply, divided by the same day's total UTXO supply.
  Persist the input series and values with each observation.
- Only BTC. Do not reuse these series as ETH/SOL data or silently substitute
  a provider with another holder definition.
- Fetch provider `date/day1`; all numeric arrays must have matching start/end indexes.
  Exclude the current unfinished UTC day. VN timezone is for scheduling/display,
  not for relabeling the provider's measurement day.
- Strict bounded requests; bad schema/values fail the run before import. Nulls
  stay missing. Every record has source URL, effective/observed time, checksum,
  and methodology `bitview-daily-v1`. Repeated unchanged imports dedupe.

## Operations

Migration `20260911_bitview_onchain.sql` registers the enabled source; normal
deployment migrations load it automatically. It preserves subsequent manual disablement.
Celery Beat (TZ=Asia/Ho_Chi_Minh): 10:00 daily plus 14:00 second attempt.
The six-hour bulk refresh excludes Bitview. Both daily attempts fetch and import
in one job through RefreshCoordinator. The second attempt may also pick up revisions.
Default history is 370 days; API failures retain prior persisted data, labeled by actual date.

Manual backfill from the backend directory with its existing runtime/env:

```sh
python -m app.tools.refresh_bitview --days 370
```

Inspect `collector_runs` status/warnings and observations joined to `data_sources`
where code=`bitview-onchain`; verify maximum effective date per metric, not only
process health. The UI source links expose provider definitions/data; evidence
identities remain in the Smart Insights response.

Rollback: disable data_sources.enabled for bitview-onchain and disable its two
Beat entries; do not delete historical observations. No other provider is changed.
