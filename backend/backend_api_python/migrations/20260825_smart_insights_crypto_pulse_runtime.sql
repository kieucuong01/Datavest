-- Runtime activation for the public-source collectors that now execute in
-- QuantDinger's Smart Insights worker.  Safe to re-run; no historical data is
-- generated or modified by this manifest.

UPDATE data_sources
SET activation_mode = 'RUNTIME',
    enabled = TRUE,
    disabled_reason = NULL,
    metadata_json = COALESCE(metadata_json, '{}'::jsonb) || '{"activationMode":"RUNTIME"}'::jsonb,
    updated_at = NOW()
WHERE code IN (
    'alternative-fng',
    'blockchaincenter-altcoin-season',
    'farside-btc-etf',
    'farside-eth-etf',
    'farside-sol-etf',
    'mempool-space'
);
