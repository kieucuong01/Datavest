CREATE TABLE IF NOT EXISTS qd_portfolio_books (
 id VARCHAR(36) PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES qd_users(id),
 name VARCHAR(100) NOT NULL, currency VARCHAR(4) NOT NULL CHECK(currency IN ('VND','USD','USDT')),
 revision INTEGER NOT NULL DEFAULT 0, dirty_from VARCHAR(10), benchmark_key VARCHAR(30),
 created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_portfolio_books_owner ON qd_portfolio_books(user_id);
CREATE TABLE IF NOT EXISTS qd_portfolio_ledger_revisions (
 book_id VARCHAR(36) NOT NULL REFERENCES qd_portfolio_books(id), revision INTEGER NOT NULL,
 request_key VARCHAR(100) NOT NULL, request_hash VARCHAR(64) NOT NULL, events_json TEXT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL, PRIMARY KEY(book_id,revision), UNIQUE(book_id,request_key)
);
CREATE TABLE IF NOT EXISTS qd_portfolio_ledger_entries (
 book_id VARCHAR(36) NOT NULL REFERENCES qd_portfolio_books(id), revision INTEGER NOT NULL,
 event_id VARCHAR(36) NOT NULL, effective_at TIMESTAMPTZ NOT NULL,
 quantity NUMERIC(38,12) NOT NULL, unit_price NUMERIC(38,12) NOT NULL,
 amount NUMERIC(38,12) NOT NULL, fee NUMERIC(38,12) NOT NULL, tax NUMERIC(38,12) NOT NULL,
 event_json TEXT NOT NULL, PRIMARY KEY(book_id,revision,event_id)
);
