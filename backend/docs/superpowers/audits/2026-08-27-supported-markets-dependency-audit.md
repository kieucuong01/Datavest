# Supported-market dependency audit

Date: 2026-08-27

## Scope

The active DataVest market universe is deliberately limited to:

- `USStock` — US equities and ETFs
- `VNStock` — Vietnamese equities on HOSE, HNX, and UPCOM
- `Crypto` — spot and swap research through supported public exchange adapters
- `Forex` — `XAUUSD` only, used as the gold provider namespace

`CNStock`, `HKStock`, generic FX pairs, `Futures`, and `MOEX` are rejected by the
shared market contract and are not returned by active market catalogs.

## Audit method

Graphify was not available for the QuantDinger checkout in this environment.
The equivalent static audit used `rg` across backend app/scripts/migrations and
frontend source, followed by the full backend test suite and runtime smoke
checks. Generated locale dictionaries and historical SQL are treated as
compatibility/history artifacts, not active product registries.

## Active dependency results

- `app/markets/registry.py`, `app/data_sources/factory.py`, market visibility,
  search, watchlist, agent markets, AI symbol detection, Strategy V2, optimizer,
  heatmap, global overview, and frontend selectors all use the four-market
  allowlist.
- Gold aliases (`Gold`, `XAU`, `XAU/USD`, `XAUUSD`) canonicalize to
  `Forex:XAUUSD`; other Forex symbols are rejected.
- Old data-source adapter modules for CN/HK stocks, generic Futures, MOEX,
  Tencent, and the old Asia K-line path were removed.
- Old catalog rows and historical/user records are not physically deleted.
  Migration `20260827_supported_markets_scope.sql` deactivates old catalog
  rows and archives retired system universes; application serializers also
  hide retired rows from watchlists, universes, portfolios, and quotes.
- The public-universe and market-symbol generator scripts no longer fetch or
  emit retired markets.
- Macro/sentiment series remain contextual research inputs only; no unsupported
  tradable market is exposed as a selectable market or provider instrument.

## Follow-up note

The large historical `migrations/init.sql` and `migrations/market_symbols_master.sql`
files still contain the original seed/history rows by design. They are followed
by the supported-market migration on startup, so a fresh or existing local DB
ends with only the supported active catalog. This preserves reproducibility and
audit history without re-enabling retired markets.
