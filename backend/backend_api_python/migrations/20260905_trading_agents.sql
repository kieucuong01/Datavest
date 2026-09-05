-- Durable, tenant-owned metadata for the private TradingAgents service.
-- The native graph state, reports and memory stay inside its scoped volume;
-- DataVest stores only immutable request metadata and redacted event/artifact
-- references so the UI can safely stream and retrieve research results.

CREATE TABLE IF NOT EXISTS trading_agents_runs (
    run_id VARCHAR(128) PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES qd_users(id) ON DELETE CASCADE,
    status VARCHAR(24) NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    request_json JSONB NOT NULL,
    config_json JSONB NOT NULL,
    config_checksum VARCHAR(64) NOT NULL,
    source_pin VARCHAR(160) NOT NULL,
    failure_code VARCHAR(80),
    failure_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_trading_agents_runs_user_created
    ON trading_agents_runs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trading_agents_runs_user_status
    ON trading_agents_runs(user_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS trading_agents_events (
    id BIGSERIAL PRIMARY KEY,
    run_id VARCHAR(128) NOT NULL REFERENCES trading_agents_runs(run_id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES qd_users(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL CHECK (sequence > 0),
    event_type VARCHAR(80) NOT NULL,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, sequence)
);

CREATE INDEX IF NOT EXISTS idx_trading_agents_events_owner_cursor
    ON trading_agents_events(user_id, run_id, sequence);

CREATE TABLE IF NOT EXISTS trading_agents_artifacts (
    id BIGSERIAL PRIMARY KEY,
    run_id VARCHAR(128) NOT NULL REFERENCES trading_agents_runs(run_id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES qd_users(id) ON DELETE CASCADE,
    artifact_name VARCHAR(160) NOT NULL,
    content_type VARCHAR(120) NOT NULL DEFAULT 'text/markdown',
    storage_path TEXT NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    byte_size BIGINT NOT NULL CHECK (byte_size >= 0),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, artifact_name)
);

CREATE INDEX IF NOT EXISTS idx_trading_agents_artifacts_owner
    ON trading_agents_artifacts(user_id, run_id, artifact_name);
CREATE INDEX IF NOT EXISTS idx_trading_agents_artifacts_checksum
    ON trading_agents_artifacts(run_id, sha256);

CREATE TABLE IF NOT EXISTS trading_agents_proposals (
    id BIGSERIAL PRIMARY KEY,
    run_id VARCHAR(128) NOT NULL UNIQUE REFERENCES trading_agents_runs(run_id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES qd_users(id) ON DELETE CASCADE,
    native_decision VARCHAR(80),
    native_rating VARCHAR(80),
    proposal_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    report_sha256 VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trading_agents_proposals_owner
    ON trading_agents_proposals(user_id, created_at DESC);

-- Runs may transition status, but their request/config/source provenance is
-- deliberately append-only. A new configuration always produces a new run.
CREATE OR REPLACE FUNCTION trading_agents_runs_immutable_fields()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.request_json IS DISTINCT FROM OLD.request_json
       OR NEW.config_json IS DISTINCT FROM OLD.config_json
       OR NEW.config_checksum IS DISTINCT FROM OLD.config_checksum
       OR NEW.source_pin IS DISTINCT FROM OLD.source_pin
       OR NEW.user_id IS DISTINCT FROM OLD.user_id THEN
        RAISE EXCEPTION 'TradingAgents run request/config/source provenance is immutable';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trading_agents_runs_immutable_fields ON trading_agents_runs;
CREATE TRIGGER trading_agents_runs_immutable_fields
BEFORE UPDATE ON trading_agents_runs
FOR EACH ROW EXECUTE FUNCTION trading_agents_runs_immutable_fields();
