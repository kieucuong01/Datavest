CREATE TABLE IF NOT EXISTS qd_portfolio_nav_snapshots (
 book_id VARCHAR(36) NOT NULL REFERENCES qd_portfolio_books(id), day VARCHAR(10) NOT NULL,
 revision INTEGER NOT NULL, snapshot_json TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL,
 PRIMARY KEY(book_id,day,revision)
);
CREATE TABLE IF NOT EXISTS qd_portfolio_nav_jobs (
 book_id VARCHAR(36) PRIMARY KEY REFERENCES qd_portfolio_books(id),
 lease_token VARCHAR(36), lease_until TIMESTAMPTZ, next_due TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS qd_portfolio_nav_evidence (
 book_id VARCHAR(36) NOT NULL REFERENCES qd_portfolio_books(id), day VARCHAR(10) NOT NULL,
 revision INTEGER NOT NULL, checksum VARCHAR(64) NOT NULL, snapshot_json TEXT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL, PRIMARY KEY(book_id,day,revision,checksum)
);
CREATE TABLE IF NOT EXISTS qd_portfolio_nav_retries (
 book_id VARCHAR(36) NOT NULL REFERENCES qd_portfolio_books(id), day VARCHAR(10) NOT NULL,
 revision INTEGER NOT NULL, next_due TIMESTAMPTZ NOT NULL,
 PRIMARY KEY(book_id,day,revision)
);
