# Crypto Insights Browser Snapshots Design

## Goal

Provide reliable, locally persisted Smart Insights data for Fear & Greed,
BTC/ETH/SOL ETF flows, CoinShares Fund Flows, Altcoin Season Index, and CBBI
Confidence. Data must be collected before dashboard reads, not by user-facing
requests.

## Scope

The existing Smart Insights observation and evidence pipeline remains the
system of record. This change replaces fragile source-specific HTML/OCR fetches
with a Browser Use snapshot worker and a validated import path. It does not
change score calculations, investment copy, user settings, or non-crypto
collectors.

## Sources and collection schedule

All times are `Asia/Ho_Chi_Minh` and are configurable through environment
variables. The deployment must set `TZ=Asia/Ho_Chi_Minh` so Celery Beat uses
that explicit timezone instead of its current generic default. The schedule
defaults intentionally leave time after a normal source update window.

| Source | Snapshot contents | Ongoing schedule |
|---|---|---|
| Alternative Fear & Greed | Every historical daily value the public source exposes | Daily, 08:15 |
| Farside BTC ETF | All rows visible in the BTC fund-flow table | Daily, 08:30 |
| Farside ETH ETF | All rows visible in the ETH fund-flow table | Daily, 08:35 |
| Farside SOL ETF | All rows visible in the SOL fund-flow table | Daily, 08:40 |
| BlockchainCenter Altcoin Season | Current 90-day, month, and year values | Daily, 08:45 |
| CBBI Confidence | Every historical confidence/component value the public data view exposes | Daily, 08:50 |
| CoinShares Fund Flows | Every report available in the public research archive | Monday and Tuesday, 18:00 |

CoinShares runs twice because a report can arrive early or late. Repeated
values are harmless because observation checksums make persistence idempotent.

## Initial backfill

Before enabling recurring jobs, one local Browser Use backfill runs sources
serially with a small delay between navigations. It records the fullest public
history available without guessing missing dates:

- Fear & Greed: every historical daily item returned by its public source.
- Farside: every dated row rendered in each BTC, ETH, and SOL flow table.
- CoinShares: each weekly report reachable from its public research archive.
- CBBI: every confidence and component point exposed by the public data view.
- Altcoin Season: the currently published 90-day, monthly, and yearly values;
  the upstream page is a current-value page and does not provide a reliable
  historical archive.

Each source produces its own snapshot and import result. A failed or
incomplete source preserves that source's last valid snapshot and cannot erase
or downgrade another source's data. The backfill report lists source coverage,
oldest and newest effective times, and failures.

## Architecture

1. A Browser Use worker opens public source pages with one local browser
   session. It captures only the tables or structured page data needed for the
   metrics above.
2. The worker validates the extracted result, adds `fetchedAt`, source URL,
   schema version, and coverage metadata, then atomically writes a per-source
   JSON snapshot beneath the existing backend data volume.
3. Smart Insights collectors load only validated snapshots, convert them into
   `Observation` records, and keep the current `observations`,
   `collector_runs`, and evidence/snapshot pipeline unchanged.
4. Celery Beat queues the daily jobs and the two CoinShares jobs. A distributed
   run lock prevents overlapping Browser Use work; a skipped overlapping run is
   recorded as a non-destructive warning.
5. Data Health reports the last successful snapshot time, coverage, and the
   last source-specific failure. The UI keeps showing the most recent valid
   observation when a later crawl fails.

## Validation and failure handling

- No snapshot is published unless it has a source-specific identity, at least
  one valid record, valid timestamps and numeric values, and required columns
  or fields.
- Farside must include a dated total-flow value. CoinShares must include an
  effective report date and at least one asset or regional flow. Altcoin Season
  must include all three horizons. CBBI and Fear & Greed must include a valid
  index value.
- Parser or page-layout changes are surfaced as `SCHEMA_DRIFT`; network and
  browser problems are surfaced as `SOURCE_UNAVAILABLE`. Both leave the last
  successful data in place.
- The worker performs sources serially, has bounded retries, and never invokes
  upstream pages from a dashboard request.

## Testing and acceptance criteria

Automated tests are written before implementation. They cover schedule routing,
snapshot validation, per-source atomic publish behavior, idempotent imports,
and preserving an old valid snapshot when a new crawl fails. Existing collector
contract tests remain green.

The implementation is accepted only when all seven source codes have a
validated local snapshot, the initial backfill reports its real coverage, and
the local Smart Insights API/health data proves fresh observations for each
source where the upstream publishes data. For CoinShares, a successful crawl
must either persist archived report values or clearly report that the public
archive exposed no report; it must not create a placeholder event.
