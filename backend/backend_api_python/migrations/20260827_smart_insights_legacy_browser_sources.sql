-- Enable the browser-backed legacy Smart Insights sources for scheduled runs.
-- The refresh coordinator still fails closed when an upstream page is blocked or
-- changes shape; enabling a source never creates substitute observations.

UPDATE data_sources
SET activation_mode = 'RUNTIME',
    enabled = TRUE,
    disabled_reason = NULL,
    metadata_json = COALESCE(metadata_json, '{}'::jsonb) ||
        '{"activationMode":"RUNTIME","acquisition":"bounded-browser"}'::jsonb,
    updated_at = NOW()
WHERE code IN (
    'bitinfocharts-top-addresses',
    'coinglass-liquidation-maxpain',
    'coinglass-margin-borrow',
    'coinshares-weekly'
);
