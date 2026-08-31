-- Public crypto-derivatives source activation. Safe to re-run.
INSERT INTO data_sources
    (code, name, market, source_url, collection_mode, methodology_version,
     freshness_sla_minutes, enabled, activation_mode, verified_at,
     disabled_reason, metadata_json)
VALUES
    ('bybit-derivatives', 'Bybit V5 Derivatives Market Data', 'crypto', 'https://api.bybit.com/', 'API', 'bybit-derivatives-v1', 2880, TRUE, 'RUNTIME', NULL, NULL, '{"schedule":"daily","venue":"bybit","historyPolicy":"provider-returned"}'::jsonb),
    ('binance-usdm-derivatives', 'Binance USD-M Futures Market Data', 'crypto', 'https://fapi.binance.com/', 'API', 'binance-usdm-derivatives-v1', 2880, TRUE, 'RUNTIME', NULL, NULL, '{"schedule":"daily","venue":"binance-usdm","historyPolicy":"metric-windowed"}'::jsonb),
    ('deribit-public-derivatives', 'Deribit Public Derivatives Market Data', 'crypto', 'https://www.deribit.com/api/v2/', 'API', 'deribit-public-derivatives-v1', 2880, TRUE, 'RUNTIME', NULL, NULL, '{"schedule":"daily","venue":"deribit","historyPolicy":"provider-returned"}'::jsonb)
ON CONFLICT (code) DO UPDATE
SET name = EXCLUDED.name, source_url = EXCLUDED.source_url, collection_mode = EXCLUDED.collection_mode,
    methodology_version = EXCLUDED.methodology_version, freshness_sla_minutes = EXCLUDED.freshness_sla_minutes,
    enabled = EXCLUDED.enabled, activation_mode = EXCLUDED.activation_mode, disabled_reason = EXCLUDED.disabled_reason,
    metadata_json = EXCLUDED.metadata_json, updated_at = NOW();
