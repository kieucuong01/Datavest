-- Public BTC API. Keep an operator's disabled flag on subsequent migrations.
INSERT INTO data_sources
    (code, name, market, source_url, collection_mode, methodology_version,
     freshness_sla_minutes, enabled, activation_mode, metadata_json)
VALUES ('bitview-onchain', 'Bitview / Bitcoin Research Kit', 'crypto',
        'https://bitview.space/api/series', 'API', 'bitview-daily-v1', 2880, TRUE, 'RUNTIME',
        '{"schedule":"daily 10:00 Asia/Ho_Chi_Minh","holderThresholdDays":150,"asset":"BTC","free":true}'::jsonb)
ON CONFLICT (code) DO NOTHING;
