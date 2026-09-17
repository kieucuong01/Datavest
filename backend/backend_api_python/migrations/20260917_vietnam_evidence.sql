CREATE TABLE IF NOT EXISTS qd_vietnam_financial_observations (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(16) NOT NULL,
    metric VARCHAR(80) NOT NULL,
    item_code VARCHAR(80) NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    numeric_value DOUBLE PRECISION NOT NULL,
    unit VARCHAR(24) NOT NULL DEFAULT 'VND',
    period_end DATE NOT NULL,
    available_at TIMESTAMPTZ NOT NULL,
    revision_at TIMESTAMPTZ,
    frequency VARCHAR(24) NOT NULL,
    report_scope VARCHAR(24) NOT NULL,
    model_type VARCHAR(80) NOT NULL DEFAULT '',
    source VARCHAR(80) NOT NULL,
    source_url TEXT NOT NULL DEFAULT '',
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, item_code, period_end, available_at, report_scope, source)
);

CREATE INDEX IF NOT EXISTS idx_qd_vietnam_financial_pit
    ON qd_vietnam_financial_observations (symbol, available_at, period_end);

CREATE TABLE IF NOT EXISTS qd_vietnam_events (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(80) NOT NULL,
    event_id VARCHAR(160) NOT NULL,
    symbol VARCHAR(16) NOT NULL,
    category VARCHAR(40) NOT NULL,
    event_type VARCHAR(100) NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    available_at TIMESTAMPTZ NOT NULL,
    effective_date DATE,
    actual_date DATE,
    source_url TEXT NOT NULL DEFAULT '',
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source, event_id)
);

CREATE INDEX IF NOT EXISTS idx_qd_vietnam_events_pit
    ON qd_vietnam_events (symbol, available_at, category);
