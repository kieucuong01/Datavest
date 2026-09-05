# TradingAgents upstream provenance

- Source: https://github.com/TauricResearch/TradingAgents
- Commit: `9dee508c44662702281a8dbaad1f7b42179b5ba7`
- Upstream package version: `0.4.0`
- Import method: `git subtree --squash`
- License: Apache-2.0; the complete upstream license is retained as `LICENSE`.

This directory is a full vendored copy of TradingAgents. Do not edit upstream
agent, graph, prompt, dataflow, CLI, test, or package files here. DataVest
integration code belongs in `backend/trading_agents_service/` so that source
pins, license obligations and future upstream updates remain auditable.

To upgrade, import a reviewed upstream commit with `git subtree pull`, update
this file, run the complete upstream test suite, and record the upgrade in the
DataVest release manifest.
