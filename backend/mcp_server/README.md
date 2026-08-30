# QuantDinger MCP Server

`quantdinger-mcp` is a thin MCP adapter over the QuantDinger Agent Gateway. It provides tenant-scoped public market data, research, Strategy and Indicator authoring, backtests, watchlists, alerts, jobs, and paper-portfolio reads.

## Configuration

Set:

- `QUANTDINGER_BASE_URL` to the backend URL;
- `QUANTDINGER_AGENT_TOKEN` to a least-privilege token using only `R/W/B/N` scopes;
- `QUANTDINGER_MCP_TRANSPORT` to `stdio`, `streamable-http`, or `sse` as appropriate.

For network transports, use TLS and configure the documented MCP auth settings. Never log or paste the Agent Token.

## Tool boundary

The registered tool surface includes:

- identity and health;
- market catalog, symbol search, price snapshots, and OHLCV;
- Strategy API V2 source contracts, templates, validation, versions, and backtests;
- Indicator contracts, validation, saved workspaces, and config linking;
- universes, factors, watchlists, jobs, and bounded job progress;
- manual portfolio positions, paper orders, and signal alerts.

The package does not load user exchange credentials or expose external-order controls. Its declared tool-name tuple is tested against the functions decorated with `@mcp.tool()` so dormant functions cannot masquerade as supported tools.

## Safety

Mutating tools use caller-generated idempotency keys. Reuse one key for retries of the same logical request. Source-version restore, job cancellation, watchlist removal, and notification delivery require explicit confirmation.

Responses are tenant-scoped and may contain redacted placeholders. Do not attempt to recover redacted values.

## Development

Install the package in an isolated environment and run its tests from `mcp_server`:

```bash
python -m pytest tests -q
```
