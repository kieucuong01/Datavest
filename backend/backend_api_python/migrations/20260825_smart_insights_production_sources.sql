-- Production DataVest source activation manifest.
-- Additive and safe to re-run. Source evidence is imported separately.

ALTER TABLE data_sources
    ADD COLUMN IF NOT EXISTS activation_mode VARCHAR(24) NOT NULL DEFAULT 'IMPORT_ONLY',
    ADD COLUMN IF NOT EXISTS verified_at DATE,
    ADD COLUMN IF NOT EXISTS disabled_reason TEXT;

ALTER TABLE collector_runs
    DROP CONSTRAINT IF EXISTS collector_runs_status_check;

ALTER TABLE collector_runs
    ADD CONSTRAINT collector_runs_status_check
    CHECK (status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'PARTIAL', 'FAILED', 'QUARANTINED'));

INSERT INTO data_sources
    (code, name, market, source_url, collection_mode, methodology_version,
     freshness_sla_minutes, enabled, activation_mode, verified_at,
     disabled_reason, metadata_json)
VALUES
    ('alternative-fng', 'Alternative.me Crypto Fear and Greed', 'crypto', 'https://api.alternative.me/fng/?limit=0&format=json', 'API', 'alternative-fng-v1', 2880, TRUE, 'IMPORT_ONLY', '2026-08-17', NULL, '{"schedule":"daily","activationMode":"IMPORT_ONLY"}'::jsonb),
    ('bis-statistics', 'BIS Statistics', 'macro', 'https://stats.bis.org/api/v1/data', 'API', 'bis-statistics-v1', 20160, TRUE, 'IMPORT_ONLY', '2026-08-17', NULL, '{"schedule":"weekly","activationMode":"IMPORT_ONLY"}'::jsonb),
    ('bitinfocharts-top-addresses', 'BitInfoCharts Richest Bitcoin Addresses', 'crypto', 'https://bitinfocharts.com/top-100-richest-bitcoin-addresses.html', 'SCRAPING', 'bitinfocharts-v1', 2880, TRUE, 'IMPORT_ONLY', '2026-08-17', NULL, '{"schedule":"daily","activationMode":"IMPORT_ONLY"}'::jsonb),
    ('blockchaincenter-altcoin-season', 'BlockchainCenter Altcoin Season Index', 'crypto', 'https://www.blockchaincenter.net/altcoin-season-index/', 'SCRAPING', 'blockchaincenter-altseason-v1', 2880, TRUE, 'IMPORT_ONLY', '2026-08-17', NULL, '{"schedule":"daily","activationMode":"IMPORT_ONLY"}'::jsonb),
    ('cftc-disaggregated', 'CFTC Disaggregated Commitments of Traders', 'gold', 'https://publicreporting.cftc.gov/resource/72hh-3qpy.json', 'API', 'cftc-disaggregated-v1', 14400, TRUE, 'IMPORT_ONLY', '2026-08-17', NULL, '{"schedule":"weekly","activationMode":"IMPORT_ONLY"}'::jsonb),
    ('cftc-legacy', 'CFTC Legacy Commitments of Traders', 'gold', 'https://publicreporting.cftc.gov/resource/srt6-5q2f.json', 'API', 'cftc-legacy-v1', 14400, FALSE, 'DISABLED', NULL, 'no independent deployment-network smoke passed', '{"schedule":"weekly","activationMode":"DISABLED"}'::jsonb),
    ('coinglass-liquidation-maxpain', 'CoinGlass Liquidation Max Pain', 'crypto', 'https://www.coinglass.com/liquidation-maxpain', 'SCRAPING', 'coinglass-maxpain-v1', 2880, TRUE, 'IMPORT_ONLY', '2026-08-17', NULL, '{"schedule":"daily","activationMode":"IMPORT_ONLY"}'::jsonb),
    ('coinglass-margin-borrow', 'CoinGlass Binance USDT Margin Borrow Rates', 'crypto', 'https://www.coinglass.com/pro/i/MarginFeeChart', 'SCRAPING', 'coinglass-margin-v1', 2880, TRUE, 'IMPORT_ONLY', '2026-08-17', NULL, '{"schedule":"daily","activationMode":"IMPORT_ONLY"}'::jsonb),
    ('coinmetrics-community', 'Coin Metrics Community API', 'crypto', 'https://community-api.coinmetrics.io/v4/timeseries/asset-metrics', 'API', 'coinmetrics-v1', 2880, TRUE, 'IMPORT_ONLY', '2026-08-17', NULL, '{"schedule":"daily","activationMode":"IMPORT_ONLY"}'::jsonb),
    ('coinshares-weekly', 'CoinShares Digital Asset Fund Flows', 'crypto', 'https://coinshares.com/insights/research-data/', 'SCRAPING', 'coinshares-v1', 10080, TRUE, 'IMPORT_ONLY', '2026-08-17', NULL, '{"schedule":"weekly","activationMode":"IMPORT_ONLY"}'::jsonb),
    ('cryptocraft', 'CryptoCraft Economic Calendar', 'macro', 'https://www.cryptocraft.com/calendar?week=this', 'SCRAPING', 'cryptocraft-v1', 120, TRUE, 'IMPORT_ONLY', '2026-08-17', NULL, '{"schedule":"calendar","activationMode":"IMPORT_ONLY"}'::jsonb),
    ('defillama-chains', 'DefiLlama Chains', 'crypto', 'https://api.llama.fi/v2/chains', 'API', 'defillama-chains-v1', 1440, TRUE, 'IMPORT_ONLY', '2026-08-17', NULL, '{"schedule":"daily","activationMode":"IMPORT_ONLY"}'::jsonb),
    ('defillama-stablecoins', 'DefiLlama Stablecoins', 'crypto', 'https://stablecoins.llama.fi/stablecoincharts/all', 'API', 'defillama-stablecoins-v1', 2880, TRUE, 'RUNTIME', '2026-08-17', NULL, '{"schedule":"daily","activationMode":"RUNTIME"}'::jsonb),
    ('eia-energy', 'U.S. EIA Energy', 'macro', 'https://api.eia.gov/v2/', 'API', 'eia-energy-v1', 11520, FALSE, 'DISABLED', NULL, 'no successful production publication evidence in the verified runbook', '{"schedule":"daily","activationMode":"DISABLED"}'::jsonb),
    ('farside-btc-etf', 'Farside Bitcoin ETF Flows', 'crypto', 'https://farside.co.uk/btc/', 'SCRAPING', 'farside-btc-v1', 2880, TRUE, 'IMPORT_ONLY', '2026-08-17', NULL, '{"schedule":"daily","activationMode":"IMPORT_ONLY"}'::jsonb),
    ('farside-eth-etf', 'Farside Ethereum ETF Flows', 'crypto', 'https://farside.co.uk/eth/', 'SCRAPING', 'farside-eth-v1', 2880, TRUE, 'IMPORT_ONLY', '2026-08-17', NULL, '{"schedule":"daily","activationMode":"IMPORT_ONLY"}'::jsonb),
    ('farside-sol-etf', 'Farside Solana ETF Flows', 'crypto', 'https://farside.co.uk/sol/', 'SCRAPING', 'farside-sol-v1', 2880, TRUE, 'IMPORT_ONLY', '2026-08-17', NULL, '{"schedule":"daily","activationMode":"IMPORT_ONLY"}'::jsonb),
    ('fred', 'Federal Reserve Economic Data', 'macro', 'https://fred.stlouisfed.org/graph/fredgraph.csv', 'API', 'fred-v1', 4320, TRUE, 'RUNTIME', '2026-08-17', NULL, '{"schedule":"daily","activationMode":"RUNTIME"}'::jsonb),
    ('gdacs-events', 'GDACS Events', 'macro', 'https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH', 'API', 'gdacs-events-v1', 360, TRUE, 'IMPORT_ONLY', '2026-08-17', NULL, '{"schedule":"daily","activationMode":"IMPORT_ONLY"}'::jsonb),
    ('mempool-btc-large-addresses', 'mempool.space BTC Large Addresses', 'crypto', 'https://mempool.space/api/address/', 'API', 'mempool-btc-large-addresses-v1', 2880, FALSE, 'DISABLED', NULL, 'production smoke failed closed with MISSING_WATCHLIST', '{"schedule":"daily","activationMode":"DISABLED"}'::jsonb),
    ('mempool-space', 'mempool.space', 'crypto', 'https://mempool.space/api/mempool', 'API', 'mempool-v1', 1440, TRUE, 'IMPORT_ONLY', '2026-08-17', NULL, '{"schedule":"daily","activationMode":"IMPORT_ONLY"}'::jsonb),
    ('nasa-eonet', 'NASA EONET', 'macro', 'https://eonet.gsfc.nasa.gov/api/v3/events', 'API', 'nasa-eonet-v1', 360, TRUE, 'IMPORT_ONLY', '2026-08-17', NULL, '{"schedule":"daily","activationMode":"IMPORT_ONLY"}'::jsonb),
    ('openbb-deribit', 'OpenBB Deribit', 'crypto', 'https://docs.openbb.co/odp/python/extensions/providers', 'API', 'openbb-deribit-v1', 1440, TRUE, 'RUNTIME', '2026-08-17', NULL, '{"schedule":"daily","activationMode":"RUNTIME"}'::jsonb),
    ('usgs-earthquakes', 'USGS Earthquakes', 'macro', 'https://earthquake.usgs.gov/fdsnws/event/1/query', 'API', 'usgs-earthquakes-v1', 360, TRUE, 'IMPORT_ONLY', '2026-08-17', NULL, '{"schedule":"daily","activationMode":"IMPORT_ONLY"}'::jsonb)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    market = EXCLUDED.market,
    source_url = EXCLUDED.source_url,
    collection_mode = EXCLUDED.collection_mode,
    methodology_version = EXCLUDED.methodology_version,
    freshness_sla_minutes = EXCLUDED.freshness_sla_minutes,
    enabled = EXCLUDED.enabled,
    activation_mode = EXCLUDED.activation_mode,
    verified_at = EXCLUDED.verified_at,
    disabled_reason = EXCLUDED.disabled_reason,
    metadata_json = EXCLUDED.metadata_json,
    updated_at = NOW();

CREATE INDEX IF NOT EXISTS idx_data_sources_activation
    ON data_sources(activation_mode, enabled, code);
