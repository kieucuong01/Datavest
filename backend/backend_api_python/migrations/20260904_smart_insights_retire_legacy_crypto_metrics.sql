-- Retire crypto metrics removed from the product surface.
-- Keep historical observations for auditability, but prevent future refreshes
-- from selecting the legacy source and make the state explicit in Data Health.

UPDATE data_sources
SET enabled = FALSE,
    activation_mode = 'DISABLED',
    disabled_reason = 'retired from Smart Insights product scope',
    metadata_json = COALESCE(metadata_json, '{}'::jsonb)
        || '{"activationMode":"DISABLED","retiredMetrics":["crypto.cycle.cbbi.*","crypto.onchain.rhodl_ratio"]}'::jsonb,
    updated_at = NOW()
WHERE code = 'cbbi-public';
