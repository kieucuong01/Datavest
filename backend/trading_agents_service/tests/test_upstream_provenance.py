from __future__ import annotations

from pathlib import Path


UPSTREAM_COMMIT = "9dee508c44662702281a8dbaad1f7b42179b5ba7"
REQUIRED_FILES = (
    "LICENSE",
    "pyproject.toml",
    "cli/main.py",
    "tradingagents/graph/trading_graph.py",
    "tradingagents/graph/setup.py",
    "tradingagents/agents/analysts/fundamentals_analyst.py",
    "tradingagents/agents/analysts/market_analyst.py",
    "tradingagents/agents/analysts/news_analyst.py",
    "tradingagents/agents/analysts/sentiment_analyst.py",
    "tradingagents/agents/researchers/bull_researcher.py",
    "tradingagents/agents/researchers/bear_researcher.py",
    "tradingagents/agents/trader/trader.py",
    "tradingagents/agents/managers/portfolio_manager.py",
    "tradingagents/agents/risk_mgmt/aggressive_debator.py",
    "tradingagents/agents/risk_mgmt/conservative_debator.py",
    "tradingagents/agents/risk_mgmt/neutral_debator.py",
    "tradingagents/graph/checkpointer.py",
    "tradingagents/agents/utils/memory.py",
)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_vendored_tradingagents_is_complete_and_pinned() -> None:
    upstream_root = _repository_root() / "backend" / "third_party" / "tradingagents"
    provenance = upstream_root / "UPSTREAM.md"

    assert upstream_root.is_dir(), "TradingAgents must be vendored as a complete source tree"
    assert provenance.is_file(), "Vendored TradingAgents must declare its source pin"
    assert f"Commit: `{UPSTREAM_COMMIT}`" in provenance.read_text(encoding="utf-8")

    missing = [relative_path for relative_path in REQUIRED_FILES if not (upstream_root / relative_path).is_file()]
    assert not missing, f"Vendored TradingAgents source is incomplete: {missing}"
