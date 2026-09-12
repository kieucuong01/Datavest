# DataVest Guest Market Access Design

## Goal

Allow unauthenticated visitors to explore Smart Insights and read indicator charts while keeping AI Assistant, personal portfolios, optimizer runs, alerts, indicator authoring, and Quant Room strategy workflows authenticated.

## Product Boundary

### Public

- `/smart-insights`: all source-backed, read-only Smart Insights modules.
- Shared asset opinions for exactly BTC, VNINDEX, and XAU.
- `/indicator-ide`: a guest chart experience with symbol, timeframe, and system indicator controls.
- Language, theme, source provenance, freshness, and stale/unavailable states.

### Authenticated

- AI Assistant and deep analysis.
- My Portfolio and Portfolio Optimizer.
- Indicator authoring, AI generation, persistence, version history, alerts, and conversion to strategy.
- Strategy IDE, backtests, and all other Quant Room strategy actions.
- Profile and administrative surfaces.

Protected functionality stays visible in navigation with a lock treatment. Activating it routes to login and preserves the intended destination in `redirect`.

## Architecture

### Routing and session behavior

Routes declare `meta.access` as `public` or `authenticated`. Guest route generation registers the normal shell and all non-admin navigation entries, but marks protected entries as locked. The global guard permits public routes without a token and redirects protected routes to `/user/login?redirect=<fullPath>`.

If an invalid token is discovered while the visitor is opening a public route, the client clears the stale session, installs guest routes, and remains on that public route. The fallback route after login is `/smart-insights` when no explicit redirect exists.

### Public Smart Insights read model

Public endpoints live under `/api/smart-insights/public/*`. They call a dedicated service configured with the fixed shared scope:

```text
Crypto:BTC/USDT -> BTC
VNStock:VNINDEX -> VNINDEX
Forex:XAUUSD -> XAU
```

The service reads shared LIVE snapshots and observations only. It never reads a user's watchlist, AI history, monitor state, portfolio, prompt, or production-account import. Public responses include the fixed asset scope so the frontend can render complete rows even when an opinion is unavailable.

Evidence and data-health responses use explicit field allowlists. Internal errors, request metadata, user identifiers, credentials, prompts, and tenant data are excluded. Public refresh remains forbidden; the existing admin-only refresh endpoint is unchanged.

### Economic calendar

The existing calendar loader is exposed through a read-only `/api/global-market/public/calendar` route. Force refresh is not accepted on the public route. Source selection remains allowlisted.

### Guest indicator chart

The guest chart reuses the existing K-line endpoint and client-side built-in indicator calculations. It does not call `/api/indicator/getIndicators`, `/chart-preview`, `/saveIndicator`, `/aiGenerate`, alert routes, or strategy routes. Guest controls are limited to allowlisted market/symbol presets, timeframe, and built-in visual indicators such as SMA, EMA, RSI, MACD, Bollinger Bands, and ATR.

The authenticated Indicator IDE remains unchanged behind the same route through an entry component that selects guest chart or full IDE based on session state.

## UX

- Header shows `Đăng nhập` for guests instead of avatar and notifications.
- Smart Insights shows a compact `Chế độ khách · dữ liệu thị trường chung` banner.
- Asset-opinion copy describes the common BTC/VNINDEX/XAU universe rather than a personal watchlist.
- Shared opinion detail remains readable; buttons that invoke AI/deep analysis become login actions.
- Guest chart has a focused, full-width data-dense layout and a non-blocking message explaining that strategy creation requires login.
- Locked routes use the existing icon system, visible keyboard focus, and at least 44px touch targets on mobile.

## Threat Model and Controls

- Spoofing/elevation: server decorators remain on every private route; UI visibility is not an authorization boundary.
- Information disclosure: public services never accept or resolve a user ID and never read tenant-owned imports or watchlists.
- Tampering/code execution: guest chart never accepts indicator code or an indicator ID owned by a user.
- Denial of service: public queries have bounded dates, IDs, symbols, timeframes, and result sizes; existing cache/guard helpers are reused.
- Enumeration: evidence IDs are length-bounded and responses expose only public observation fields.
- Financial-data integrity: unavailable data remains unavailable; no zero/default opinion is fabricated. Every rendered snapshot carries freshness and provenance where available.

## Verification Contract

- Anonymous requests receive 200 from every public Smart Insights route and calendar route.
- Existing private Smart Insights, AI, portfolio, indicator authoring, alert, optimizer, strategy, and refresh routes still return 401 without a token.
- Public overview contains only BTC, VNINDEX, and XAU and contains no user/private fields.
- Anonymous `/smart-insights` and `/indicator-ide` render without calling a private endpoint.
- Direct navigation to protected routes redirects to login with the original full path.
- Login, authenticated Indicator IDE, existing Smart Insights sections, responsive navigation, localization, build, and scoped backend tests remain functional.

## Non-goals

- Anonymous AI requests, strategy generation, backtests, alerts, saved indicators, portfolios, or optimizer runs.
- Temporary guest portfolios or browser-local strategies.
- Publishing tenant-owned production imports as public data.
- Changing provider collectors, CORS, authentication token format, or registration flow.
