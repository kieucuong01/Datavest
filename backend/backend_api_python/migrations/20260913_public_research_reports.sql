CREATE TABLE IF NOT EXISTS public_research_reports (
    id BIGSERIAL PRIMARY KEY,
    asset_key VARCHAR(120) NOT NULL,
    report_kind VARCHAR(16) NOT NULL CHECK (report_kind IN ('quick', 'deep')),
    locale VARCHAR(16) NOT NULL DEFAULT 'vi-VN',
    effective_date DATE NOT NULL,
    status VARCHAR(16) NOT NULL CHECK (status IN ('pending', 'complete', 'failed')),
    payload_json JSONB,
    failure_code VARCHAR(80),
    source_run_id VARCHAR(128),
    generated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (asset_key, report_kind, locale, effective_date)
);

CREATE INDEX IF NOT EXISTS idx_public_research_reports_latest
    ON public_research_reports (asset_key, report_kind, locale, effective_date DESC);
