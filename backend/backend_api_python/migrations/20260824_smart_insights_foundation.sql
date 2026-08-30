-- DataVest Smart Insights foundation.
-- Additive from the pinned QuantDinger baseline; safe to re-run.

CREATE TABLE IF NOT EXISTS data_sources (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(120) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    market VARCHAR(40) NOT NULL,
    source_url TEXT NOT NULL,
    collection_mode VARCHAR(32) NOT NULL DEFAULT 'API',
    methodology_version VARCHAR(120) NOT NULL,
    freshness_sla_minutes INTEGER NOT NULL CHECK (freshness_sla_minutes > 0),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO data_sources
    (code, name, market, source_url, collection_mode, methodology_version,
     freshness_sla_minutes, enabled, metadata_json)
VALUES
    ('openbb-deribit', 'OpenBB Deribit', 'crypto',
     'https://docs.openbb.co/odp/python/extensions/providers', 'API',
     'openbb-deribit-v1', 1440, FALSE,
     '{"schedule":"daily","termsUrl":"https://docs.openbb.co/odp/python/faqs/license","optionalRuntime":true}'::jsonb),
    ('fred', 'Federal Reserve Economic Data', 'macro',
     'https://fred.stlouisfed.org/graph/fredgraph.csv', 'API',
     'fred-v1', 4320, FALSE,
     '{"schedule":"daily","termsUrl":"https://fred.stlouisfed.org/legal/"}'::jsonb),
    ('eia-energy', 'U.S. EIA Energy', 'macro',
     'https://api.eia.gov/v2/', 'API', 'eia-energy-v1', 11520, FALSE,
     '{"schedule":"daily","termsUrl":"https://www.eia.gov/about/copyrights_reuse.php","requiresApiKey":true}'::jsonb),
    ('cftc-disaggregated', 'CFTC Disaggregated Commitments of Traders', 'macro',
     'https://publicreporting.cftc.gov/resource/72hh-3qpy.json', 'API',
     'cftc-disaggregated-v1', 14400, FALSE,
     '{"schedule":"weekly","termsUrl":"https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm"}'::jsonb),
    ('bis-statistics', 'BIS Statistics', 'macro',
     'https://stats.bis.org/api/v1/data', 'API', 'bis-statistics-v1', 20160, FALSE,
     '{"schedule":"weekly","termsUrl":"https://www.bis.org/terms_conditions.htm"}'::jsonb),
    ('farside-btc-etf', 'Farside Bitcoin ETF Flows', 'crypto',
     'https://farside.co.uk/btc/', 'SCRAPING', 'farside-btc-v1', 2880, FALSE,
     '{"schedule":"daily","termsUrl":"https://farside.co.uk/btc/"}'::jsonb),
    ('defillama-stablecoins', 'DefiLlama Stablecoins', 'crypto',
     'https://stablecoins.llama.fi/stablecoincharts/all', 'API',
     'defillama-stablecoins-v1', 2880, FALSE,
     '{"schedule":"daily","termsUrl":"https://defillama.com/about"}'::jsonb),
    ('mempool-space', 'mempool.space', 'crypto',
     'https://mempool.space/api/mempool', 'API', 'mempool-v1', 1440, FALSE,
     '{"schedule":"daily","termsUrl":"https://mempool.space/about"}'::jsonb),
    ('cryptocraft', 'CryptoCraft Economic Calendar', 'macro',
     'https://www.cryptocraft.com/calendar?week=this', 'SCRAPING',
     'cryptocraft-v1', 120, FALSE,
     '{"schedule":"calendar","termsUrl":"https://www.cryptocraft.com/legal.php"}'::jsonb),
    ('gdelt-events', 'GDELT Events', 'macro',
     'https://api.gdeltproject.org/api/v2/doc/doc', 'API', 'gdelt-events-v1', 360, FALSE,
     '{"schedule":"hourly","termsUrl":"https://www.gdeltproject.org/about.html"}'::jsonb)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    market = EXCLUDED.market,
    source_url = EXCLUDED.source_url,
    collection_mode = EXCLUDED.collection_mode,
    methodology_version = EXCLUDED.methodology_version,
    freshness_sla_minutes = EXCLUDED.freshness_sla_minutes,
    metadata_json = EXCLUDED.metadata_json,
    updated_at = NOW();

CREATE TABLE IF NOT EXISTS collector_runs (
    id UUID PRIMARY KEY,
    data_source_id BIGINT REFERENCES data_sources(id) ON DELETE RESTRICT,
    requested_by_user_id BIGINT REFERENCES qd_users(id) ON DELETE SET NULL,
    market VARCHAR(40),
    status VARCHAR(24) NOT NULL,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    records_fetched INTEGER NOT NULL DEFAULT 0 CHECK (records_fetched >= 0),
    records_persisted INTEGER NOT NULL DEFAULT 0 CHECK (records_persisted >= 0),
    error_code VARCHAR(120),
    warnings_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    request_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'QUARANTINED'))
);

CREATE TABLE IF NOT EXISTS observations (
    id UUID PRIMARY KEY,
    data_source_id BIGINT NOT NULL REFERENCES data_sources(id) ON DELETE RESTRICT,
    collector_run_id UUID REFERENCES collector_runs(id) ON DELETE SET NULL,
    market VARCHAR(40) NOT NULL,
    symbol VARCHAR(80),
    effective_at TIMESTAMPTZ NOT NULL,
    published_at TIMESTAMPTZ,
    observed_at TIMESTAMPTZ NOT NULL,
    source_url TEXT NOT NULL,
    methodology_version VARCHAR(120) NOT NULL,
    value_json JSONB NOT NULL,
    warnings_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    checksum CHAR(64) NOT NULL,
    data_class VARCHAR(8) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (data_class IN ('LIVE', 'DEMO')),
    UNIQUE (data_source_id, checksum)
);

CREATE TABLE IF NOT EXISTS insight_snapshots (
    id UUID PRIMARY KEY,
    as_of TIMESTAMPTZ NOT NULL,
    market VARCHAR(40) NOT NULL,
    status VARCHAR(24) NOT NULL,
    methodology_version VARCHAR(120) NOT NULL,
    summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence_checksum CHAR(64) NOT NULL,
    data_class VARCHAR(8) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('COMPLETE', 'PARTIAL', 'UNAVAILABLE')),
    CHECK (data_class IN ('LIVE', 'DEMO')),
    UNIQUE (market, as_of, methodology_version, data_class, evidence_checksum)
);

CREATE TABLE IF NOT EXISTS asset_opinions (
    id UUID PRIMARY KEY,
    insight_snapshot_id UUID NOT NULL REFERENCES insight_snapshots(id) ON DELETE CASCADE,
    market VARCHAR(40) NOT NULL,
    symbol VARCHAR(80) NOT NULL,
    stance VARCHAR(24) NOT NULL,
    score NUMERIC(10, 4),
    confidence NUMERIC(5, 2) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
    rationale_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    explanation TEXT,
    explanation_model VARCHAR(120),
    evidence_validated BOOLEAN NOT NULL DEFAULT FALSE,
    data_class VARCHAR(8) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (data_class IN ('LIVE', 'DEMO')),
    UNIQUE (insight_snapshot_id, symbol)
);

CREATE TABLE IF NOT EXISTS insight_evidence_links (
    id BIGSERIAL PRIMARY KEY,
    insight_snapshot_id UUID NOT NULL REFERENCES insight_snapshots(id) ON DELETE CASCADE,
    asset_opinion_id UUID REFERENCES asset_opinions(id) ON DELETE CASCADE,
    observation_id UUID NOT NULL REFERENCES observations(id) ON DELETE RESTRICT,
    evidence_role VARCHAR(24) NOT NULL DEFAULT 'SUPPORTING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (evidence_role IN ('SUPPORTING', 'CONTRADICTING', 'CONTEXT')),
    UNIQUE (insight_snapshot_id, asset_opinion_id, observation_id, evidence_role)
);

CREATE TABLE IF NOT EXISTS user_insight_preferences (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES qd_users(id) ON DELETE CASCADE,
    markets_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    symbols_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    locale VARCHAR(8) NOT NULL DEFAULT 'vi',
    base_currency VARCHAR(8) NOT NULL DEFAULT 'USD',
    investment_horizon VARCHAR(40) NOT NULL DEFAULT 'medium',
    risk_tolerance VARCHAR(40) NOT NULL DEFAULT 'balanced',
    alert_preferences_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (locale IN ('vi', 'en')),
    UNIQUE (user_id)
);

CREATE INDEX IF NOT EXISTS idx_data_sources_market_enabled
    ON data_sources(market, enabled);
CREATE INDEX IF NOT EXISTS idx_collector_runs_source_created
    ON collector_runs(data_source_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_collector_runs_status_created
    ON collector_runs(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_observations_market_effective
    ON observations(market, effective_at DESC);
CREATE INDEX IF NOT EXISTS idx_observations_symbol_effective
    ON observations(symbol, effective_at DESC) WHERE symbol IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_observations_class_observed
    ON observations(data_class, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_insight_snapshots_lookup
    ON insight_snapshots(market, data_class, as_of DESC);
CREATE INDEX IF NOT EXISTS idx_asset_opinions_symbol_created
    ON asset_opinions(symbol, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_evidence_links_observation
    ON insight_evidence_links(observation_id);
