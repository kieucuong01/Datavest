# Module boundaries

| Boundary | Primary modules |
| --- | --- |
| Authentication and security | `app/routes/auth.py`, `app/utils/auth.py`, `app/services/security_service.py` |
| Human research APIs | `app/routes/backtest_center.py`, `script_source_routes.py`, `indicator.py`, `factors.py`, `universe.py` |
| Agent research APIs | `app/routes/agent_v1` |
| Public market data | `app/data_sources`, `app/data_providers`, `app/services/market` |
| Strategy source and backtest | `app/services/script_source.py`, `app/services/strategy_v2` |
| Indicator IDE and alerts | `app/services/indicator_workspace.py`, `indicator_signal_alerts.py` |
| Manual and paper portfolio | `app/services/portfolio`, `app/routes/portfolio.py` |
| MCP | `mcp_server/src/quantdinger_mcp` |

Routes own HTTP concerns. Services own domain behavior. Data sources expose read-only market behavior. Agent and MCP modules use only R/W/B/N capabilities.
