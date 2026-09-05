# DataVest TradingAgents service

This is the private runtime boundary for the unmodified vendored TradingAgents
source. It is not a public API and must only be reachable from the DataVest
backend network.

The service validates its container environment before any later task imports
`TradingAgentsGraph`. It never logs provider credentials or the internal
callback secret.
