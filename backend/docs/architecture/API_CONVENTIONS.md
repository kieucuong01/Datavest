# API conventions

Human APIs live under `/api`; Agent APIs live under `/api/agent/v1`. Routes validate input, enforce tenant ownership, call services, and map results to the standard envelope.

High-risk human mutations include authentication, password changes, publication, and destructive workspace changes. They require typed request schemas and explicit authorization.

Agent mutations require the relevant R/W/B/N scope. Retryable writes use an `Idempotency-Key`; destructive workspace changes and notification delivery require explicit confirmation.

Market-data endpoints are read-only and use public provider clients. Strategy-source, Indicator, universe, factor, watchlist, backtest, and paper-portfolio contracts must not import external-order or user-account modules.
