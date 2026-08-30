# Agent Gateway quickstart

## 1. Issue a token

Sign in with a human account and issue an Agent Token from `/api/agent/v1/me/tokens` or the admin token page. Select only the scopes needed:

- `R` for market data and research reads;
- `W` for Strategy source, Indicator, watchlist, or alert workspace changes;
- `B` for backtests;
- `N` for notifications.

Copy the token once and store it in a secret manager. Never place it in source control or logs.

## 2. Call the gateway

Send the token as a bearer credential:

```bash
curl -H "Authorization: Bearer $QUANTDINGER_AGENT_TOKEN" \
  "$QUANTDINGER_BASE_URL/api/agent/v1/whoami"
```

Use market and instrument allowlists to constrain reads. Public price, OHLCV, symbol-search, and catalog endpoints use uncredentialed market-data providers.

## 3. Author and test research code

Fetch the Strategy API V2 authoring contract before writing source. Compile or validate the source, save it in the source workspace, then submit a backtest. Poll `/jobs/{job_id}` or use the bounded progress stream until the job reaches a terminal state.

Indicators are chart-only. Fetch the Indicator authoring contract, validate code, and save the Indicator workspace; do not send Indicator code directly to the backtest endpoint.

## 4. Paper and research tools

Agents may read manual portfolio positions and paper-order history, manage universes and watchlists, inspect factors, and configure signal alerts. Destructive workspace changes and notification delivery require explicit confirmation and an idempotency key.

## 5. Safety

- Agent capabilities stop at research, backtest, Indicator, alert, watchlist, and paper-portfolio boundaries.
- Reuse the same idempotency key when retrying one logical write.
- Respect `429` responses and `Retry-After`.
- Review generated research before using it for a decision.
- Revoke tokens immediately if they may have leaked.
