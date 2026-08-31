-- Public ETF-flow API sources. Safe to re-run and does not create observations.
INSERT INTO data_sources
    (code, name, market, source_url, collection_mode, methodology_version,
     freshness_sla_minutes, enabled, activation_mode, verified_at,
     disabled_reason, metadata_json)
VALUES
    ('cryptoetf-btc-etf', 'CryptoETF Bitcoin ETF Flows', 'crypto', 'https://api.cryptoetf.today/api/v1/flows/btc', 'API', 'cryptoetf-v1', 2880, TRUE, 'RUNTIME', NULL, NULL, '{"schedule":"daily","activationMode":"RUNTIME","requiresApiKey":true}'::jsonb),
    ('cryptoetf-eth-etf', 'CryptoETF Ethereum ETF Flows', 'crypto', 'https://api.cryptoetf.today/api/v1/flows/eth', 'API', 'cryptoetf-v1', 2880, TRUE, 'RUNTIME', NULL, NULL, '{"schedule":"daily","activationMode":"RUNTIME","requiresApiKey":true}'::jsonb),
    ('cryptoetf-sol-etf', 'CryptoETF Solana ETF Flows', 'crypto', 'https://api.cryptoetf.today/api/v1/flows/sol', 'API', 'cryptoetf-v1', 2880, TRUE, 'RUNTIME', NULL, NULL, '{"schedule":"daily","activationMode":"RUNTIME","requiresApiKey":true}'::jsonb),
    ('cryptoetf-xrp-etf', 'CryptoETF XRP ETF Flows', 'crypto', 'https://api.cryptoetf.today/api/v1/flows/xrp', 'API', 'cryptoetf-v1', 2880, TRUE, 'RUNTIME', NULL, NULL, '{"schedule":"daily","activationMode":"RUNTIME","requiresApiKey":true}'::jsonb),
    ('cryptoetf-hyp-etf', 'CryptoETF Hyperliquid ETF Flows', 'crypto', 'https://api.cryptoetf.today/api/v1/flows/hyp', 'API', 'cryptoetf-v1', 2880, TRUE, 'RUNTIME', NULL, NULL, '{"schedule":"daily","activationMode":"RUNTIME","requiresApiKey":true}'::jsonb),
    ('cryptoetf-doge-etf', 'CryptoETF Dogecoin ETF Flows', 'crypto', 'https://api.cryptoetf.today/api/v1/flows/doge', 'API', 'cryptoetf-v1', 2880, TRUE, 'RUNTIME', NULL, NULL, '{"schedule":"daily","activationMode":"RUNTIME","requiresApiKey":true}'::jsonb),
    ('cryptoetf-link-etf', 'CryptoETF Chainlink ETF Flows', 'crypto', 'https://api.cryptoetf.today/api/v1/flows/link', 'API', 'cryptoetf-v1', 2880, TRUE, 'RUNTIME', NULL, NULL, '{"schedule":"daily","activationMode":"RUNTIME","requiresApiKey":true}'::jsonb),
    ('cryptoetf-avax-etf', 'CryptoETF Avalanche ETF Flows', 'crypto', 'https://api.cryptoetf.today/api/v1/flows/avax', 'API', 'cryptoetf-v1', 2880, TRUE, 'RUNTIME', NULL, NULL, '{"schedule":"daily","activationMode":"RUNTIME","requiresApiKey":true}'::jsonb),
    ('cryptoetf-hbar-etf', 'CryptoETF Hedera ETF Flows', 'crypto', 'https://api.cryptoetf.today/api/v1/flows/hbar', 'API', 'cryptoetf-v1', 2880, TRUE, 'RUNTIME', NULL, NULL, '{"schedule":"daily","activationMode":"RUNTIME","requiresApiKey":true}'::jsonb),
    ('cryptoetf-ltc-etf', 'CryptoETF Litecoin ETF Flows', 'crypto', 'https://api.cryptoetf.today/api/v1/flows/ltc', 'API', 'cryptoetf-v1', 2880, TRUE, 'RUNTIME', NULL, NULL, '{"schedule":"daily","activationMode":"RUNTIME","requiresApiKey":true}'::jsonb),
    ('cryptoetf-bnb-etf', 'CryptoETF BNB ETF Flows', 'crypto', 'https://api.cryptoetf.today/api/v1/flows/bnb', 'API', 'cryptoetf-v1', 2880, TRUE, 'RUNTIME', NULL, NULL, '{"schedule":"daily","activationMode":"RUNTIME","requiresApiKey":true}'::jsonb),
    ('cryptoetf-dot-etf', 'CryptoETF Polkadot ETF Flows', 'crypto', 'https://api.cryptoetf.today/api/v1/flows/dot', 'API', 'cryptoetf-v1', 2880, TRUE, 'RUNTIME', NULL, NULL, '{"schedule":"daily","activationMode":"RUNTIME","requiresApiKey":true}'::jsonb),
    ('cryptoetf-sui-etf', 'CryptoETF Sui ETF Flows', 'crypto', 'https://api.cryptoetf.today/api/v1/flows/sui', 'API', 'cryptoetf-v1', 2880, TRUE, 'RUNTIME', NULL, NULL, '{"schedule":"daily","activationMode":"RUNTIME","requiresApiKey":true}'::jsonb),
    ('xoomar-btc-etf', 'Xoomar Bitcoin ETF Flow Estimate', 'crypto', 'https://xoomar.com/api/markets/etf-flows?asset=btc&days=90', 'API', 'xoomar-etf-v1', 2880, TRUE, 'RUNTIME', NULL, NULL, '{"schedule":"daily","activationMode":"RUNTIME","flowMethod":"holdings-delta-estimate"}'::jsonb),
    ('xoomar-eth-etf', 'Xoomar Ethereum ETF Flow Estimate', 'crypto', 'https://xoomar.com/api/markets/etf-flows?asset=eth&days=90', 'API', 'xoomar-etf-v1', 2880, TRUE, 'RUNTIME', NULL, NULL, '{"schedule":"daily","activationMode":"RUNTIME","flowMethod":"holdings-delta-estimate"}'::jsonb)
ON CONFLICT (code) DO UPDATE
SET name = EXCLUDED.name,
    source_url = EXCLUDED.source_url,
    collection_mode = EXCLUDED.collection_mode,
    methodology_version = EXCLUDED.methodology_version,
    freshness_sla_minutes = EXCLUDED.freshness_sla_minutes,
    enabled = EXCLUDED.enabled,
    activation_mode = EXCLUDED.activation_mode,
    disabled_reason = EXCLUDED.disabled_reason,
    metadata_json = EXCLUDED.metadata_json,
    updated_at = NOW();
