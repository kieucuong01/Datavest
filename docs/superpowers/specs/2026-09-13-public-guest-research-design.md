# Public guest research reports

## Goal

Anonymous visitors can read the latest common research for BTC, VNINDEX and
XAU without receiving any user's watchlist, report history, prompts, provider
configuration or TradingAgents artifact. Signed-in users continue to see only
the assets in their own watchlist and their own reports.

The public catalogue publishes one quick report per asset per Vietnam calendar
day and one deep report per asset per Vietnam calendar week. Reports are
Vietnamese (`vi-VN`) in this first release; the API records the locale so later
locale-specific publishing does not require a schema change.

## Ownership and data boundary

Add a dedicated `public_research_reports` store. A report has an immutable
public asset key, report kind (`quick` or `deep`), locale, effective period,
status, safe payload, generated timestamp and an optional internal source-run
reference. The unique key is `(asset_key, report_kind, locale, effective_date)`.

No endpoint reads `analysis_memory`, `qd_analysis_tasks`, `trading_agents_runs`
or `trading_agents_artifacts` on behalf of a guest. The public worker copies a
sanitized final projection into this store only after a report completes. It
never exposes prompts, raw model output, provider credentials, event streams,
native graph state, account IDs, private storage paths or run IDs.

The deep-report worker uses a dedicated non-login system principal, created by
the migration, to satisfy the existing owner-scoped TradingAgents contract. Its
tenant workspace is not assigned to a human account. The public endpoint still
serves only the copied safe projection, never that principal's private route or
artifact path.

## Scheduling and recovery

Celery Beat runs in `Asia/Ho_Chi_Minh`:

- Daily public quick reports at 07:15 for BTC, VNINDEX and XAU.
- Weekly public deep reports at 08:00 every Monday for the same assets.

Each job is idempotent for its report period. It creates a pending public
record, writes `complete` only after validation, and records a bounded failure
reason on error. A failed new job does not replace the last completed report;
guest reads fall back to that completed report and receive its actual effective
date. An explicit internal backfill command uses the same code path and creates
the first current quick and deep set after deployment.

## HTTP contract

Add read-only unauthenticated routes under `/api/smart-insights/public/reports`:

- list latest reports for the fixed public asset scope;
- retrieve the latest completed report for one allowed asset and kind.

The routes validate asset key and report kind against the fixed BTC, VNINDEX,
XAU catalogue. They return only a stable projection: title, asset, kind,
locale, effective date, generated time, summary/structured content and
provenance. They do not accept a `user_id`, `run_id`, arbitrary symbol or write
method.

Existing authenticated quick-analysis and TradingAgents endpoints remain
owner-scoped. Smart Insights' authenticated asset-opinion rows continue to be
constructed from the requesting account's watchlist.

## UI behavior

Guest Smart Insights uses the fixed asset set and shows two read-only actions:
`Xem báo cáo nhanh` and `Xem phân tích chuyên sâu`. Both open the latest public
report with effective date, generated time and a public-data label. A missing
or failed current report shows a truthful empty state and, when present, the
latest completed report rather than a fabricated recommendation.

The authenticated view preserves the current quick-analysis and TradingAgents
flows, including creation, monitoring, history and account-specific controls.
No guest component calls their write endpoints.

## Verification

- Repository/service tests prove public scope filtering, idempotency, safe
  projections and fallback to the latest completed record.
- Route tests prove guest reads are allowed only for BTC/VNINDEX/XAU and prove
  private report fields cannot be returned.
- Scheduler tests prove daily and weekly jobs target exactly the three public
  assets and do not enumerate user watchlists.
- Frontend contract tests prove guest uses only public report APIs and has no
  create/monitor action; authenticated rows still derive from its watchlist.
- Targeted backend and frontend suites plus a production-style HTTP check run
  before release.
