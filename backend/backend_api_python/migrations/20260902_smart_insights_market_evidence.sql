-- Watchlist-derived market bars are LIVE evidence, never an AI prediction.
-- Additive and safe to re-run on local and production PostgreSQL.

INSERT INTO data_sources
    (code, name, market, source_url, collection_mode, methodology_version,
     freshness_sla_minutes, enabled, activation_mode, verified_at,
     disabled_reason, metadata_json)
VALUES
    ('datavest-market-bars', 'DataVest Market Data Gateway', 'all',
     'https://github.com/kieucuong01/Datavest', 'INTERNAL_ADAPTER',
     'datavest-market-bars-v1', 720, TRUE, 'RUNTIME', NULL, NULL,
     '{"schedule":"every-6-hours","scope":"distinct-supported-watchlist-pairs","output":"evidence-only"}'::jsonb)
ON CONFLICT (code) DO UPDATE
SET name = EXCLUDED.name,
    market = EXCLUDED.market,
    source_url = EXCLUDED.source_url,
    collection_mode = EXCLUDED.collection_mode,
    methodology_version = EXCLUDED.methodology_version,
    freshness_sla_minutes = EXCLUDED.freshness_sla_minutes,
    enabled = EXCLUDED.enabled,
    activation_mode = EXCLUDED.activation_mode,
    disabled_reason = EXCLUDED.disabled_reason,
    metadata_json = EXCLUDED.metadata_json,
    updated_at = NOW();
