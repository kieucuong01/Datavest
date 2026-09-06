from __future__ import annotations

import pytest

from tradingagents.graph.trading_graph import TradingAgentsGraph, _coerce_timeout


@pytest.mark.unit
def test_llm_timeout_is_positive_and_forwarded_to_provider_clients():
    graph = TradingAgentsGraph.__new__(TradingAgentsGraph)
    graph.config = {"llm_timeout": "120"}

    assert _coerce_timeout("120") == 120
    assert TradingAgentsGraph._get_provider_kwargs(graph)["timeout"] == 120


@pytest.mark.unit
def test_llm_timeout_rejects_non_positive_values():
    with pytest.raises(ValueError, match="llm_timeout must be > 0"):
        _coerce_timeout(0)
