-- One-time/import lineage for accounts copied from the legacy DataVest app.
-- Raw records are retained because the QuantDinger schema has no equivalent
-- for several legacy read models (performance, briefings and research runs).
-- No authentication secret is stored here.

CREATE TABLE IF NOT EXISTS qd_production_account_imports (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES qd_users(id) ON DELETE CASCADE,
    source_user_id VARCHAR(128) NOT NULL,
    data_type VARCHAR(64) NOT NULL,
    source_record_id VARCHAR(255) NOT NULL,
    payload JSONB NOT NULL,
    source_updated_at TIMESTAMPTZ,
    payload_checksum CHAR(64) NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, data_type, source_record_id)
);

CREATE INDEX IF NOT EXISTS idx_qd_production_imports_user_type
    ON qd_production_account_imports(user_id, data_type, imported_at DESC);

CREATE INDEX IF NOT EXISTS idx_qd_production_imports_checksum
    ON qd_production_account_imports(user_id, payload_checksum);
