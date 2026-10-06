CREATE TABLE IF NOT EXISTS qd_portfolio_alert_preferences (
 book_id VARCHAR(36) PRIMARY KEY REFERENCES qd_portfolio_books(id), user_id INTEGER NOT NULL REFERENCES qd_users(id),
 settings_json TEXT NOT NULL, baseline_json TEXT, baseline_at TIMESTAMPTZ NOT NULL,
 next_digest_at TIMESTAMPTZ NOT NULL, next_check_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS qd_portfolio_alert_state (
 book_id VARCHAR(36) NOT NULL REFERENCES qd_portfolio_books(id), rule VARCHAR(30) NOT NULL,
 asset_key VARCHAR(120) NOT NULL, episode INTEGER NOT NULL DEFAULT 0,
 active INTEGER NOT NULL DEFAULT 0, fingerprint VARCHAR(64), PRIMARY KEY(book_id,rule,asset_key)
);
CREATE TABLE IF NOT EXISTS qd_portfolio_alert_pending (
 id BIGSERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES qd_users(id), book_id VARCHAR(36) NOT NULL REFERENCES qd_portfolio_books(id),
 rule VARCHAR(30) NOT NULL, asset_key VARCHAR(120) NOT NULL, episode INTEGER NOT NULL,
 fingerprint VARCHAR(64) NOT NULL, payload_json TEXT NOT NULL, observed_at TIMESTAMPTZ NOT NULL,
 sent_at TIMESTAMPTZ, cancelled INTEGER NOT NULL DEFAULT 0,
 UNIQUE(book_id,rule,asset_key,episode,fingerprint)
);
CREATE INDEX IF NOT EXISTS ix_portfolio_alert_pending_user ON qd_portfolio_alert_pending(user_id,sent_at,cancelled);
CREATE TABLE IF NOT EXISTS qd_portfolio_alert_delivery (
 user_id INTEGER PRIMARY KEY REFERENCES qd_users(id), last_sent_at TIMESTAMPTZ
);
