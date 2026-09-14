-- Reusable, authenticated-only reports for assets outside the fixed public scope.
-- Visibility is enforced from the caller's current qd_watchlist membership, not
-- from a durable recipient list, so removing an asset revokes access immediately.
CREATE TABLE IF NOT EXISTS shared_watchlist_research_reports (
    id BIGSERIAL PRIMARY KEY,
    asset_key VARCHAR(120) NOT NULL,
    report_kind VARCHAR(16) NOT NULL CHECK (report_kind IN ('quick', 'deep')),
    locale VARCHAR(16) NOT NULL DEFAULT 'vi-VN',
    period_key DATE NOT NULL,
    status VARCHAR(16) NOT NULL CHECK (status IN ('pending', 'complete', 'failed')),
    payload_json JSONB,
    failure_code VARCHAR(80),
    source_run_id VARCHAR(128),
    generated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (asset_key, report_kind, locale, period_key)
);

CREATE INDEX IF NOT EXISTS idx_shared_watchlist_research_reports_latest
    ON shared_watchlist_research_reports (asset_key, report_kind, locale, period_key DESC);

CREATE INDEX IF NOT EXISTS idx_shared_watchlist_research_reports_pending_deep
    ON shared_watchlist_research_reports (locale, period_key, id)
    WHERE report_kind = 'deep' AND status = 'pending' AND source_run_id IS NOT NULL;
