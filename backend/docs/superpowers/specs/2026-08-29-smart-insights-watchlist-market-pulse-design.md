# Smart Insights watchlist and Market Pulse design

## Goal

Refine the QuantDinger-first DataVest Smart Insights page so it uses the
application shell cleanly, shows source-backed live market context, limits
Asset Opinions to the AI Assistant watchlist, and renders every supported
Market Pulse dataset instead of reusing the same two charts for all tabs.

BTC/Kronos forecasting is explicitly out of scope and must be removed from
the Smart Insights navigation, API design, UI copy, and tests.

## Product layout

The page order is:

1. Application shell header managed by the existing DataVest layout.
2. Live Data Sources strip.
3. Analysis date, market and LIVE/DEMO controls.
4. Decision Brief hero and risk alerts.
5. Asset Opinions driven by the AI Assistant watchlist.
6. Market Pulse tabs and charts.
7. Economic calendar, evidence drawer, data-health drawer and footer.

The local `legacy-header` and the `legacy-card portfolio-changes` section are
deleted. Portfolio changes remain available in persisted/imported data for
lineage, but are not rendered on this page.

## Live Data Sources

Add an authenticated endpoint:

`GET /api/smart-insights/live-assets`

The endpoint uses the existing market quote service and a server-owned asset
catalog. The initial catalog is:

| Display symbol | Market | Provider symbol |
|---|---|---|
| BTC | Crypto | BTC/USDT |
| ETH | Crypto | ETH/USDT |
| SOL | Crypto | SOL/USDT |
| XRP | Crypto | XRP/USDT |
| LINK | Crypto | LINK/USDT |
| VNINDEX | VNStock | VNINDEX |
| VN30 | VNStock | VN30 |
| XAU | Forex | XAUUSD |

Each row returns display symbol, market, provider symbol, price, absolute and
percentage change, actual source/provider context, cache state, status and
`fetchedAt`. Unavailable rows remain in the response with an explicit status;
the endpoint never fabricates or silently substitutes a price.

The frontend displays the strip immediately below the application header,
refreshes every 30 seconds while mounted, pauses when destroyed, and keeps the
last valid row visible with a stale badge when the backend reports stale cache.

## Asset Opinions

Smart Insights reads the same `/api/market/watchlist/get` contract used by the
AI Assistant. It does not maintain a second list.

The visible row order follows the watchlist. An existing briefing opinion is
joined by canonical market and symbol identity. A watchlist item without an
opinion still appears with an explicit pending/unavailable analysis state.
Opinions for assets that are not in the watchlist are never rendered.

An empty watchlist shows an empty state and a route action to the AI Assistant.
Adding or removing symbols remains owned by the AI Assistant; Smart Insights
does not introduce another watchlist editor.

LIVE/DEMO truth is retained. Missing evidence, missing opinion generation, or
legacy imported evidence remains visibly PARTIAL/UNAVAILABLE and is not
promoted to verified data.

## Market Pulse

The backend already returns persisted data for seven useful groups. The
frontend must render each group with a dedicated Vue component and must not
show a chart from another tab as a fallback.

| Tab | Data rendered |
|---|---|
| Tổng quan | Fear & Greed, ETF summaries and high-level source coverage |
| Dòng tiền | ETF and fund-flow history, grouped by BTC/ETH/SOL where available |
| Tâm lý | Fear & Greed history and sentiment metrics |
| Phái sinh | Margin borrow, liquidation pressure and derivative metric trends |
| Chu kỳ | Altcoin Season, CBBI and cycle component trends |
| Chuỗi khối | Stablecoin, TVL and other persisted on-chain metric trends |
| Cá voi BTC | Large-address, concentration and exchange-flow trends |

The existing combined `sentimentDerivatives` backend payload can feed separate
Tâm lý and Phái sinh frontend tabs. No schema migration is required. Generic
metric cards and series are normalized by pure frontend helpers so imported
production payloads and locally persisted observations share one renderer.

Charts use SVG already supported by the Vue application. They display axes,
zero lines where appropriate, latest values, source, effective time and an
empty state when fewer than one valid point exists. One-point series remain
visible as a dot. Evidence actions open the existing evidence drawer when an
evidence identifier exists.

There is no Dự báo BTC/Kronos tab. The misleading `btcBottom`/forecast label is
not exposed in the UI. Existing historical payload fields may remain stored for
backward-compatible reads, but they are not a supported Smart Insights module.

## Error handling and security

- Both live-assets and existing Smart Insights workspace calls require JWT.
- Server errors return bounded public messages; provider keys, environment and
  raw exceptions never reach the browser.
- A failure in one surface does not blank the page: live assets, watchlist,
  overview, pulse and data health have independent loading/error states.
- Timers are cleared on component destruction.
- Only supported DataVest markets and canonical symbols enter the quote service.

## Testing and acceptance

Backend tests cover the exact live asset catalog, supported canonical symbols,
status/provenance normalization, unavailable rows and authentication.

Frontend tests first fail for these contracts:

- no `legacy-header` or `portfolio-changes` markup;
- Live Data Sources appears before page controls and contains the eight assets;
- visible opinions are the watchlist-driven join only;
- empty watchlist links to AI Assistant;
- seven Market Pulse tabs exist, with no forecast/Kronos tab;
- each tab selects its own panel and series normalizer;
- one-point and unavailable series render truthfully;
- the 30-second refresh interval is started and cleaned up.

Acceptance requires focused frontend/backend tests, full backend regression,
frontend production build, Docker Compose health, authenticated API smoke and
browser verification in English and Vietnamese at `http://127.0.0.1:8888/`.
