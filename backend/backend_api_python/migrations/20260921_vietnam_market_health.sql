CREATE TABLE IF NOT EXISTS qd_vietnam_market_health (
    id BIGSERIAL PRIMARY KEY,
    trigger_type VARCHAR(40) NOT NULL,
    status VARCHAR(24) NOT NULL,
    coverage DOUBLE PRECISION NOT NULL DEFAULT 0,
    result JSONB NOT NULL DEFAULT '{}'::jsonb,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_qd_vietnam_market_health_checked
    ON qd_vietnam_market_health(checked_at DESC);
