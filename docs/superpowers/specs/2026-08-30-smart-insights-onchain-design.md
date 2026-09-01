# Smart Insights On-chain Design

## Goal

Turn the currently generic, runtime-backed On-chain tab into a source-attributed terminal for the free data already collected by DataVest, while keeping CBBI and Altcoin Season exclusively in the Cycle tab.

## Scope

- Use existing immutable LIVE observations only: CoinMetrics Community, DefiLlama Stablecoins and DefiLlama Chains.
- Present the available data in four user-facing groups: valuation and profitability, network activity, on-chain liquidity, and protocol/DeFi activity.
- Preserve the existing Cycle terminal as the only full CBBI and Altcoin Season experience.
- Do not introduce new data providers, API keys, browser scraping, subscription content, buy/sell recommendations, or synthetic history.

## Taxonomy

| Surface | Metrics in this change | Explicit exclusions |
|---|---|---|
| On-chain: valuation and profitability | BTC MVRV | CBBI and its normalized MVRV component |
| On-chain: network activity | BTC active addresses | Google Trends, Fear and Greed |
| On-chain: liquidity | total stablecoin supply | ETF/GBTC flows and Coinbase Premium |
| On-chain: protocol and DeFi | chain TVL, with the chain symbol preserved | team wallets and GitHub activity |
| Cycle | Existing CBBI, CBBI components, Altcoin Season | exchange and whale flow metrics |

## Data Flow

`CoinMetricsCollector`, `DefiLlamaStablecoinsCollector`, and `DefiLlamaChainsCollector` persist validated observations. `build_crypto_market_pulse` already classifies their source codes as `onchain`. The production read-model merge must preserve that runtime tab when the imported legacy snapshot marks On-chain unavailable. The frontend receives only the existing tab contract: status, sources, metrics, and time series.

Each UI card must show its latest value, source-backed history when available, and a short methodology caveat. A missing metric remains unavailable; it is never converted to zero or a trading signal.

## UI Behaviour

Create an `OnchainTerminal` rendered only for the On-chain tab. It contains:

1. A concise header explaining that the tab reports network, valuation and liquidity evidence rather than trade calls.
2. Four data groups in a stable order. Empty groups are omitted; if every group is empty, retain the existing unavailable state.
3. Latest-value cards and interactive ECharts histories. Each chart keeps hover tooltips, its source label, and uses the existing 90D/1Y/ALL range controls when sufficient history exists.
4. MVRV, active addresses, stablecoin supply, and chain TVL are labelled from their real metric code and unit. The Cycle tab does not render these same raw metrics.

## Error Handling and Security

- Reuse existing collector host validation, bounded requests, schema validation, and fail-closed `CollectorUnavailable` behavior.
- Do not add a new provider, secret, URL parameter, or client-controlled fetch target.
- Evidence links and source labels originate from persisted source metadata, not user content.

## Testing

- Backend: test that `build_crypto_market_pulse` puts CoinMetrics and DefiLlama rows into On-chain, preserves exact metric identity and creates no Cycle duplication.
- Backend: test the imported-plus-runtime merge keeps an AVAILABLE On-chain runtime tab without overwriting imported overview data.
- Frontend: test that Market Pulse mounts `OnchainTerminal` only for the On-chain tab and that the component groups source-backed metrics without inventing values.
- Run scoped Python tests, the Smart Insights frontend unit test, scoped ESLint, frontend build, and local HTTP health checks.

## Non-goals and Follow-up

NUPL, SOPR, supply in profit, holder cohorts, exchange net flows, miner data, ETH burn/staking, and verified entity labels require additional source contracts. They belong in the stated taxonomy, but are deliberately deferred until their provider coverage, licensing, update cadence and schema can be validated.
