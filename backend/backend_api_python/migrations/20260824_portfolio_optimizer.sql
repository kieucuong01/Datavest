-- DataVest portfolio optimizer: immutable inputs and paper-only rebalance audit.

CREATE TABLE IF NOT EXISTS optimizer_runs (
    id VARCHAR(36) PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES qd_users(id) ON DELETE CASCADE,
    status VARCHAR(24) NOT NULL DEFAULT 'SUCCEEDED',
    method VARCHAR(40) NOT NULL,
    base_currency VARCHAR(8) NOT NULL,
    request_json JSONB NOT NULL,
    input_snapshot_json JSONB NOT NULL,
    input_checksum VARCHAR(64) NOT NULL,
    result_json JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_optimizer_runs_user_created
    ON optimizer_runs(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS optimizer_input_series (
    id BIGSERIAL PRIMARY KEY,
    optimizer_run_id VARCHAR(36) NOT NULL REFERENCES optimizer_runs(id) ON DELETE CASCADE,
    market VARCHAR(32) NOT NULL,
    symbol VARCHAR(80) NOT NULL,
    currency VARCHAR(8) NOT NULL,
    provider VARCHAR(120) NOT NULL,
    fallback_chain_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    coverage DECIMAL(10,6) NOT NULL,
    checksum VARCHAR(64) NOT NULL,
    data_class VARCHAR(8) NOT NULL CHECK (data_class = 'LIVE'),
    timestamps_json JSONB NOT NULL,
    closes_json JSONB NOT NULL,
    UNIQUE(optimizer_run_id, market, symbol, currency, checksum)
);

CREATE TABLE IF NOT EXISTS optimizer_allocations (
    optimizer_run_id VARCHAR(36) NOT NULL REFERENCES optimizer_runs(id) ON DELETE CASCADE,
    symbol VARCHAR(80) NOT NULL,
    target_weight_bps INTEGER NOT NULL CHECK (target_weight_bps BETWEEN 0 AND 10000),
    PRIMARY KEY(optimizer_run_id, symbol)
);

CREATE TABLE IF NOT EXISTS paper_rebalance_plans (
    id VARCHAR(36) PRIMARY KEY,
    optimizer_run_id VARCHAR(36) NOT NULL REFERENCES optimizer_runs(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES qd_users(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'PREVIEW' CHECK (status IN ('PREVIEW', 'APPLIED')),
    portfolio_value DECIMAL(24,8) NOT NULL CHECK (portfolio_value > 0),
    input_checksum VARCHAR(64) NOT NULL,
    proposal_json JSONB NOT NULL,
    apply_idempotency_key VARCHAR(128),
    applied_result_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    applied_at TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_rebalance_apply_idempotency
    ON paper_rebalance_plans(user_id, apply_idempotency_key)
    WHERE apply_idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_rebalance_plans_run
    ON paper_rebalance_plans(optimizer_run_id, created_at DESC);

CREATE TABLE IF NOT EXISTS paper_portfolio_transactions (
    id VARCHAR(36) PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES qd_users(id) ON DELETE CASCADE,
    paper_rebalance_plan_id VARCHAR(36) NOT NULL REFERENCES paper_rebalance_plans(id) ON DELETE RESTRICT,
    market VARCHAR(32) NOT NULL,
    symbol VARCHAR(80) NOT NULL,
    side VARCHAR(8) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity DECIMAL(24,8) NOT NULL CHECK (quantity > 0),
    price DECIMAL(24,8) NOT NULL CHECK (price > 0),
    notional DECIMAL(24,8) NOT NULL CHECK (notional >= 0),
    currency VARCHAR(8) NOT NULL,
    execution_mode VARCHAR(16) NOT NULL DEFAULT 'SIMULATED' CHECK (execution_mode = 'SIMULATED'),
    idempotency_key VARCHAR(128) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(paper_rebalance_plan_id, market, symbol, side)
);
