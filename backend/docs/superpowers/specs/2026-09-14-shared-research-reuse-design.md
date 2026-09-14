# Shared research reuse for Smart Insights

## Goal

Prevent duplicate LLM analysis for the same asset while preserving account
watchlists and an explicit user action to create a report when no reusable
report is available.

## Report scopes

Every report is keyed by normalized market, symbol, report kind, report period,
canonical locale, and engine version.

- `public_common`: reports for the fixed guest asset catalog. Guests and every
  authenticated account can read these reports.
- `shared_watchlist`: reports for assets outside that catalog. A logged-in user
  may create one, and it is readable only by authenticated users whose
  watchlist contains the same normalized market and symbol.

Published payloads never expose the initiating user, private prompt content,
private TradingAgents run IDs, storage paths, or account-specific portfolio
data.

## Freshness and creation rules

| Report kind | Reuse period | Common assets | Other watched assets |
| --- | --- | --- | --- |
| Quick | Vietnam calendar day | Scheduled once daily | User requests once when absent for the day |
| Deep | Vietnam calendar week | Scheduled once weekly | User requests once when absent for the week |

For a matching completed or pending report in its reuse period, the UI renders
the shared result or its pending state and does not render a create button.
The backend enforces the same deduplication so simultaneous user requests
enqueue exactly one job.

## Scheduling

- Keep the public common quick schedule.
- Keep the public common weekly deep schedule.
- Remove the daily task that loops through every account watchlist and creates
  account-owned Fast Analysis reports.
- Do not schedule reports for non-common assets. They are created only by an
  authenticated user request after the server confirms no reusable report
  exists for the current period.

## Access model

- Guest routes can request only `public_common` reports for the fixed common
  asset catalog.
- Authenticated routes return the union of public common assets and the
  current user's watchlist.
- Authenticated users can read `shared_watchlist` reports only when they still
  follow the corresponding asset. The check is performed server-side for list,
  detail, PDF, and artifact-style endpoints.
- An authenticated user may request a report only for a common asset or an
  asset in that user's watchlist.

## UI behavior

The Asset Opinions list for an authenticated user begins with the public common
assets and then adds non-duplicate watchlist assets. Each row labels the report
as common or watchlist-shared, shows its report period and status, and exposes
one action:

- completed and current: read the report;
- pending: show progress, without a create action;
- absent or expired: show the appropriate create action to logged-in users.

Guests retain a fixed common catalog and can only read public common reports.

## Migration and compatibility

Existing account-owned quick history and TradingAgents runs remain private
historical records. New shared reports use a separate shared research store;
they do not mutate or broaden access to legacy private runs. Public reports are
migrated into the common scope without exposing their system service account.

## Verification

Tests cover period calculation, request coalescing, visibility after watchlist
membership changes, guest denial for non-common assets, removal of the
per-watchlist scheduler, and UI creation-button state. API smoke tests verify
that private identifiers cannot appear in shared responses.
