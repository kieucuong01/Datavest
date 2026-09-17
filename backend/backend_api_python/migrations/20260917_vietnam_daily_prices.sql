CREATE TABLE IF NOT EXISTS qd_vietnam_daily_prices (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    trading_time TIMESTAMPTZ NOT NULL,
    raw_open DOUBLE PRECISION NOT NULL,
    raw_high DOUBLE PRECISION NOT NULL,
    raw_low DOUBLE PRECISION NOT NULL,
    raw_close DOUBLE PRECISION NOT NULL,
    adjusted_open DOUBLE PRECISION,
    adjusted_high DOUBLE PRECISION,
    adjusted_low DOUBLE PRECISION,
    adjusted_close DOUBLE PRECISION,
    adjustment_factor DOUBLE PRECISION,
    volume DOUBLE PRECISION NOT NULL DEFAULT 0,
    price_mode VARCHAR(20) NOT NULL,
    source VARCHAR(50) NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    quality_flags JSONB NOT NULL DEFAULT '{}'::jsonb,
    checksum VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(symbol, trading_time, price_mode, source)
);

CREATE INDEX IF NOT EXISTS idx_qd_vietnam_daily_prices_lookup
    ON qd_vietnam_daily_prices(symbol, price_mode, trading_time DESC);
