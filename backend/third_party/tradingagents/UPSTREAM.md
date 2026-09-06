# TradingAgents upstream provenance

- Source: https://github.com/TauricResearch/TradingAgents
- Commit: `9dee508c44662702281a8dbaad1f7b42179b5ba7`
- Upstream package version: `0.4.0`
- Import method: `git subtree --squash`
- License: Apache-2.0; the complete upstream license is retained as `LICENSE`.

This directory is a full vendored copy of TradingAgents. DataVest integration
code belongs in `backend/trading_agents_service/`. The source pin identifies the
upstream base, not a claim that the working tree is byte-for-byte unmodified.
Keep narrowly scoped runtime patches documented below; do not replace upstream
analysts, prompts, debate rounds, tools, or graph nodes with reduced variants.

## DataVest modification notice — 2026-09-06

- `agents/analysts/sentiment_analyst.py`, `agents/utils/progress.py`: expose
  source/model substeps, bound each public-source wait (45 seconds by default),
  cap outstanding source threads and preserve the run context in those threads.
  Unavailable sources remain explicitly unavailable in the upstream prompt.
- `default_config.py`, `graph/trading_graph.py`, `llm_clients/bedrock_client.py`:
  forward an operator-configured per-request model timeout (180 seconds default).
- `agents/utils/structured.py`: do not repeat a timed-out model request using
  the free-text fallback; other upstream fallback behavior remains intact.
- `dataflows/config.py`: isolate hosted run language/provider/cache configuration
  using context-local state while retaining the CLI's default configuration API.
- Tests accompanying these fixes are included. The Apache-2.0 license and
  upstream copyright notices are retained.

To upgrade, import a reviewed upstream commit with `git subtree pull`, update
this file, run the complete upstream test suite, and record the upgrade in the
DataVest release manifest.
