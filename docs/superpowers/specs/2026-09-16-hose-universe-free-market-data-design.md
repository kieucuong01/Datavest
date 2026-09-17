# HOSE Universe and Free Market Data Design

## Scope

This change makes HOSE a validated, database-backed market universe and replaces the unsupported KB Securities price feed. It does not add order execution or paid data.

## Provider policy

- VNDIRECT public endpoints are the primary provider for the HOSE universe and OHLCV. They are keyless but are treated as best-effort because no public endpoint-specific contract or SLA is available.
- Yahoo Finance (`<symbol>.VN`) is a keyless fallback for OHLCV only.
- KB Securities is removed from the production provider chain.
- If VNDIRECT is unavailable, universe synchronization fails closed and preserves the last successful database snapshot. Static rows remain bootstrap-only.

## Universe contract

`qd_market_symbols` stores exchange, asset class, sector, first/last trading dates, trading status, source, and source update time. A successful full HOSE snapshot upserts current rows and deactivates missing rows. A provider error or empty/implausibly small snapshot never deactivates existing rows.

Only active HOSE equities and ETFs are accepted for TradingAgents VNStock runs. Unknown, inactive, or delisted symbols are rejected before a job is created.

## Price contract

The VN adapter supports daily and intraday OHLCV. It converts VNDIRECT equity/ETF prices from thousands of VND to absolute VND while preserving index points, normalizes provider records to DataVest bars, validates prices and volume, caches successful results, applies a local request-rate gate and timeout, rejects stale live responses, and tries Yahoo next. Historical requests are evaluated against the requested period rather than the current clock.

Provider provenance is retained in `last_kline_provider`. No credential value is logged.

## Operations

No provider credential is required. Operators may tune `VN_MARKET_DATA_TIMEOUT_SEC`, `VNDIRECT_MARKET_DATA_RPM`, `HOSE_SNAPSHOT_MIN_ROWS`, and `VN_DAILY_MAX_STALENESS_DAYS`. Provider failures never replace the database catalog with the curated seed.
