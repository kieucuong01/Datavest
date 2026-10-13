# QuantDinger selective update — 2026-10-13

DataVest reviewed upstream changes against its original backend baseline
`366ea33c276b5307ce8428da6dcca160532635ea` and frontend baseline
`6f9ce97fe4730355c39a72610f5dbda3f05d3db7`.

Fetched heads: backend `ba8cd667acca3e934bbc1cb354922eff413393dc` (167 commits
after the baseline), frontend `d05c131aabe440eec5f4a8a73b25bb83dfc6a6bc`
(90 commits after the baseline). These are review references, not claims that
DataVest has adopted the complete upstream release.

## Adopted changes

| Source commit | DataVest change |
| --- | --- |
| Backend `db49a4c6568b43642d43aa66b507488b0adc1a42` | Increment the token version atomically on password reset, invalidating existing sessions. |
| Backend `19a9e8b7084f5614c2728e78ab41f2e2935d0734` | Ignore forwarded client IP headers from public peers; prefer the reverse proxy's overwritten `X-Real-IP`. |
| Backend `b59352b45482462891d154f1e13af5c946f39b95` | Preserve provider precision for candle prices instead of rounding to four decimals. |
| Backend `13f2cdab958b421402130eceef956768bec84653` | Filter dynamic universe members against loaded market data so missing symbols do not abort a backtest; retain skipped-symbol diagnostics. |
| Backend `f76396fc35bd38c8ee34103339287b36d40099e6` | Use UTC ISO timestamps for Finnhub news and retain headlines with malformed timestamps. Only the news collector portion is adopted; DataVest has no upstream `professional_report` module. |
| Frontend `a5f3d39a9ecc4aa72c4902aa835c93050b757fb5` | Display confidence only when the API supplies a finite number; preserve zero confidence in both streamed and fallback responses. |
| Backend `a5a9f4c79a263113504e882531585a9f2d3b24f9`, `ba8cd667acca3e934bbc1cb354922eff413393dc` | Update security baselines and lock versions to pypdf 6.19.0, Werkzeug 3.1.9 and multidict 6.9.1. |

Upstream tests accompany the backend fixes. The Finnhub tests are adapted to
simulate a non-UTC server on Windows without changing the host timezone or
calling external search providers. Frontend tests exercise confidence
expressions from both actual response paths.

DataVest compatibility adaptations also sort mixed-source news by the parsed
instant (instead of comparing ISO and legacy date strings), and clear the
local session before returning to login after a successful password change.
Ordinary logout still contacts the backend; cleanup also runs if that call
fails. Both adaptations have behavioral regression coverage.

## Validation

- Full backend suite: 1,249 passed, 4 skipped. After the final compatibility
  adjustments, the 50 affected authentication, market-data, backtest and PDF
  tests also passed with the upgraded dependency versions.
- Final frontend suite: 363 passed.
- Changed frontend source files: ESLint passed; final Vite production build passed.
- Requirements lock validation: all 35 direct dependencies passed.
- Code review: both identified compatibility issues were fixed and re-reviewed.
- Graphify AST graph refreshed; existing SQL-parser and unrelated Vue/JSX
  extraction warnings remain.

No production deployment or authenticated browser smoke was performed.

## Deferred upstream work

Distributed strategy workers, native exchange clients, live-order recovery,
billing, marketplace, event radar, strategy evolution and virtual-account UI
require separate compatibility reviews. This update leaves DataVest's
branding, Smart Insights, HOSE integration and portfolio modules in place.
Original source pins in `backend/deploy/datavest-release.json` remain the
import baselines; this ledger records the individual backports.

## Future updates

Run from the DataVest repository:

```powershell
git fetch --no-tags upstream-backend
git fetch --no-tags upstream-frontend
```

The original repository roots map to DataVest's `backend/` and `frontend/`
directories. Review patches against the latest source references and this
ledger before applying them. A direct pull of either upstream branch into the
monorepo does not preserve this directory mapping or DataVest customizations.
