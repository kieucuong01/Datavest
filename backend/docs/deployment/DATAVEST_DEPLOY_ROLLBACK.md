# DataVest deploy, smoke, and rollback runbook

This runbook covers the QuantDinger-first DataVest pair. It separates source and
manifest truth, container health, HTTP behavior, provider truth, and browser
acceptance. A green check at one boundary does not prove the next boundary.

## Safety contracts

- Production is research-and-paper-only. Every optimizer apply must remain
  `executionMode=SIMULATED`; there is no live-order fallback.
- The backend flags are fail-closed when absent. Set
  `DATAVEST_SMART_INSIGHTS_ENABLED` and
  `DATAVEST_PORTFOLIO_OPTIMIZER_ENABLED` explicitly for every enabled rollout.
  The DataVest Compose override defaults both to `false`.
- `LIVE` means provider-backed data with provenance, freshness, and checksum.
  `DEMO` is synthetic/seeded and is allowed only when the request explicitly
  uses `mode=demo`. Never use DEMO evidence in production opinions, AI context,
  optimizer inputs, alerts, or paper orders.
- Do not print `.env`, JWTs, provider keys, database URLs, or container
  environments. Put smoke credentials in the operator's secure environment and
  clear them after use.
- Never use `docker compose down -v` during deploy or ordinary rollback.

Use one Compose prefix throughout:

```powershell
$Compose = @(
  '-f', 'backend/docker-compose.yml',
  '-f', 'backend/docker-compose.datavest.yml',
  '-f', 'backend/docker-compose.production.yml'
)
```

For a local or canary rollout, opt in explicitly. Enable only the feature being
tested when validating independence; enable both only when that is the intended
rollout state:

```powershell
$env:DATAVEST_SMART_INSIGHTS_ENABLED = 'true'
$env:DATAVEST_PORTFOLIO_OPTIMIZER_ENABLED = 'true'
docker compose @Compose config
```

Without those assignments, both feature routes must remain unmounted and return
404. Do not rely on values left in an operator shell from an earlier rollout.

## Pin the release pair

`deploy/datavest-release.json` is the release manifest. The release wrapper,
not an implementation commit, updates it after both repository commits exist.
This avoids a backend commit that tries to contain its own SHA.

1. Record the full 40-character backend and frontend commits.
2. Update each `fullCommit`; set `commit` to a 7-40 character prefix of the same
   value. Do not change `tradingMode=SIMULATED_ONLY`.
3. Check out those exact commits in their respective repositories.
4. Choose an immutable image tag and export it as `DATAVEST_RELEASE`. Record the
   built image digests beside the manifest in the release evidence.
5. Validate structure without comparing against a hard-coded historical SHA:

```powershell
Set-Location backend_api_python
& '.\.venv\Scripts\python.exe' -m pytest tests\test_datavest_release_contract.py -q
Set-Location ..
docker compose @Compose config
```

The rendered Compose config must contain exactly the approved DataVest services,
and `migration` and `backend` must resolve to the same
`datavest-backend:<DATAVEST_RELEASE>` image.

## Deploy

Before promotion, take a database backup using the platform's normal protected
backup mechanism and record its identifier without copying credentials into the
release log.

```powershell
docker compose @Compose build backend frontend
docker compose @Compose up -d postgres redis redis-jobs
docker compose @Compose up -d migration backend scheduler-worker celery-worker celery-beat frontend
docker compose @Compose ps
```

Stop if migration exits non-zero, a required service is restarting/unhealthy, or
the resolved backend/migration images differ. Do not force the API past a failed
migration.

## Health and HTTP evidence

Set the externally reachable origins without a trailing slash:

```powershell
$Api = 'https://api.example.invalid'
$Web = 'https://app.example.invalid'
curl.exe -fsS "$Api/api/health"
curl.exe -fsS "$Api/api/health/ready"
curl.exe -fsS "$Api/api/health/workers"
curl.exe -fsS "$Api/metrics"
curl.exe -fsSI "$Web/"
```

Required evidence:

- liveness is HTTP 200 and identifies the API role/version;
- readiness is HTTP 200 with PostgreSQL and the configured Celery broker ready;
- scheduler/Celery heartbeats are fresh;
- `/metrics` exposes `datavest_feature_requests_total` and
  `datavest_feature_outcomes_total` after feature requests;
- the public frontend returns HTTP 200 from the intended origin/CDN.

Verify each feature flag independently. With no Authorization header, an enabled
route returns 401; a disabled route returns 404. A 401 proves the route is
mounted and auth is still active. Test all four combinations in staging before
production promotion.

```powershell
curl.exe -sS -o NUL -w "%{http_code}`n" "$Api/api/smart-insights/overview"
curl.exe -sS -o NUL -w "%{http_code}`n" -X POST -H "Content-Type: application/json" -d "{}" "$Api/api/portfolio/optimizer/runs"
```

## Authenticated LIVE/DEMO smoke

Load an ordinary-user JWT and an admin JWT from the approved secret store into
`DATAVEST_SMOKE_JWT` and `DATAVEST_SMOKE_ADMIN_JWT`. Never echo them or include
request headers in artifacts.

```powershell
$UserHeaders = @{ Authorization = "Bearer $env:DATAVEST_SMOKE_JWT" }
$AdminHeaders = @{ Authorization = "Bearer $env:DATAVEST_SMOKE_ADMIN_JWT" }

$Live = Invoke-RestMethod "$Api/api/smart-insights/overview?mode=live" -Headers $UserHeaders
$Health = Invoke-RestMethod "$Api/api/smart-insights/data-health" -Headers $UserHeaders
$Demo = Invoke-RestMethod "$Api/api/smart-insights/overview?mode=demo" -Headers $UserHeaders
```

For LIVE, retain only sanitized evidence showing source code/URL,
`observedAt`/`effectiveAt`, methodology version, checksum, freshness, and
`dataClass=LIVE`. Fail promotion if LIVE output contains a DEMO evidence ID or
lacks provenance. DEMO must appear only after `mode=demo` and must be visibly
identified as demo data in browser acceptance.

Queue one admin refresh per configured specialty provider, then use Data Health
to verify the terminal collector outcome and freshness. A 202 response proves
only queueing, not collection success.

```powershell
$RefreshBody = @{ market = 'crypto'; sourceCodes = @('defillama-stablecoins', 'openbb-deribit') } | ConvertTo-Json
Invoke-RestMethod "$Api/api/smart-insights/refresh" -Method Post -Headers $AdminHeaders -ContentType 'application/json' -Body $RefreshBody

$MacroBody = @{ market = 'macro'; sourceCodes = @('fred') } | ConvertTo-Json
Invoke-RestMethod "$Api/api/smart-insights/refresh" -Method Post -Headers $AdminHeaders -ContentType 'application/json' -Body $MacroBody
```

Provider outcomes must be recorded as LIVE, unavailable, or failed with a
sanitized error code. Hermetic pytest fixtures are contract evidence, not a live
provider smoke.

## Market-provider smoke: VN, Crypto, and US

Use at least 120 calendar days so the optimizer can align 31 or more prices.
The smoke request needs two instruments because it exercises the actual
portfolio boundary, not only a quote endpoint.

```powershell
$End = (Get-Date).ToUniversalTime().Date.AddDays(-1)
$Start = $End.AddDays(-120)

function Invoke-OptimizerSmoke($BaseCurrency, $Instruments) {
  $Body = @{
    method = 'minimum_variance'
    baseCurrency = $BaseCurrency
    startDate = $Start.ToString('yyyy-MM-dd')
    endDate = $End.ToString('yyyy-MM-dd')
    maxWeight = 0.8
    instruments = $Instruments
  } | ConvertTo-Json -Depth 5
  Invoke-RestMethod "$Api/api/portfolio/optimizer/runs" -Method Post -Headers $UserHeaders -ContentType 'application/json' -Body $Body
}

$UsRun = Invoke-OptimizerSmoke 'USD' @(
  @{ market = 'USStock'; symbol = 'AAPL'; currency = 'USD' },
  @{ market = 'USStock'; symbol = 'MSFT'; currency = 'USD' }
)
$CryptoRun = Invoke-OptimizerSmoke 'USDT' @(
  @{ market = 'Crypto'; symbol = 'BTC/USDT'; currency = 'USDT'; exchangeId = 'binance'; marketType = 'spot' },
  @{ market = 'Crypto'; symbol = 'ETH/USDT'; currency = 'USDT'; exchangeId = 'binance'; marketType = 'spot' }
)
$VnRun = Invoke-OptimizerSmoke 'VND' @(
  @{ market = 'VNStock'; symbol = 'FPT'; currency = 'VND' },
  @{ market = 'VNStock'; symbol = 'VCB'; currency = 'VND' }
)
```

For every successful run, GET `/api/portfolio/optimizer/runs/<id>` and verify
each input series is `LIVE`, has a non-empty provider and checksum, contains at
least 31 synchronized closes, and records the actual fallback winner. Never
label a seeded catalog row or mocked test as provider proof.

If the pinned release includes an approved read-only VN adapter, the VN smoke
above must succeed with LIVE provenance. Otherwise VN remains a promotion
blocker. Do not relabel an unavailable response as DEMO or silently substitute
another market.

## Browser acceptance

Use the pinned frontend build against the pinned backend. Capture screenshots
and sanitized Network evidence for:

1. login succeeds and unrelated authenticated pages still load;
2. Smart Insights LIVE shows provenance and Data Health, with no demo watermark;
3. explicit Demo Mode shows a visible DEMO watermark;
4. optimizer create, preview, and two-step apply finish with `SIMULATED` visible;
5. disabled features receive backend 404 and do not expose usable feature data;
6. no billing, broker credential, live order, grid/copy trading, or mobile route
   appears in the tested production bundle.

Browser evidence supplements health/HTTP/provider proof; it does not replace
them. Remove tokens, cookies, user identifiers, run IDs, and plan IDs from saved
artifacts.

## Rollback

Rollback selects the previous complete manifest pair and immutable image tag.
Do not mix a previous frontend with a current backend unless that exact pair is
already pinned and verified.

```powershell
$env:DATAVEST_RELEASE = '<previous-immutable-release-tag>'
docker compose @Compose config
docker compose @Compose up -d migration backend scheduler-worker celery-worker celery-beat frontend
docker compose @Compose ps
```

Then repeat health, independent flag, authenticated HTTP, provider, and browser
evidence. Migrations in this release are additive; application rollback does not
drop tables. If a future release requires data restoration, stop writes and use
the approved backup/restore procedure with explicit authorization rather than
adding destructive SQL to this runbook.

Record the rollback manifest, image digests, reason, timestamps, and each
evidence boundary. Clear `DATAVEST_SMOKE_JWT` and
`DATAVEST_SMOKE_ADMIN_JWT` from the operator environment when finished.
