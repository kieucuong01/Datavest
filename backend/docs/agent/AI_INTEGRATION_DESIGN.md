# QuantDinger Agent integration design

## Purpose

The Agent Gateway exposes tenant-scoped research workflows to external AI and MCP clients. The REST API remains the source of truth; MCP is a curated adapter over that API.

The gateway is deliberately separate from human JWT authentication. Agent tokens are hashed at rest, bound to one user, rate-limited, auditable, and restricted by market and instrument allowlists.

## Capability classes

Agent scopes are exactly:

- `R`: read public market data, research artifacts, job state, paper portfolio state, and saved workspaces.
- `W`: write strategy-source and Indicator drafts, watchlists, and other non-executing workspace state.
- `B`: submit backtests and simulations.
- `N`: configure or deliver notifications with explicit confirmation where required.

Unknown scope letters are rejected during issuance. Existing stored tokens containing unsupported letters are rejected by authentication. Agent tokens never load user exchange credentials or place external orders.

## Preserved API surface

The supported `/api/agent/v1` surface includes:

- identity, health, market catalog, symbol search, OHLCV, and public price snapshots;
- Strategy API V2 source contracts, templates, validation, versioning, and backtests;
- Indicator authoring, validation, saved Indicator workspaces, and signal alerts;
- universes, factors, watchlists, asynchronous jobs, and bounded job progress;
- manual positions and paper-portfolio order history.

Strategy-source writes create research artifacts only. They do not create or control an execution deployment.

## Token policy

Token issuance accepts a name, any subset of `R/W/B/N`, optional market and instrument allowlists, expiry, and rate limit. Portfolio behavior is paper-only. Notional fields retained in the token record are compatibility metadata for simulations and do not authorize external execution.

Self-service and admin issuance use the same capability set. Admin endpoints may list, revoke, and audit tenant tokens but cannot mint additional capability classes.

## MCP boundary

The MCP package declares exactly the functions decorated as tools. Retained tools cover public market data, Strategy and Indicator authoring, backtests, research, watchlists, paper portfolio reads, jobs, and signal alerts.

Mutating calls use caller-generated idempotency keys. Source-version restore, watchlist removal, job cancellation, and notification delivery require explicit human confirmation.

## Operational safety

- Never log or return raw Agent Tokens, provider keys, or secrets.
- Provider keys are server-side data-provider configuration and are not user broker credentials.
- Use public, uncredentialed clients for market data.
- Keep retries bounded and reuse the same idempotency key.
- Treat research and backtest output as decision support requiring human review.
- Audit records are append-only and tenant-scoped.

## Deployment

The same gateway can run self-hosted or hosted. Hosted mode adds outer rate limits and tenant isolation requirements but does not change the scope model. Use TLS for network transports and configure the MCP server with a least-privilege Agent Token.
