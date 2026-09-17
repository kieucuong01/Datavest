"""Agents on the schema-only structured-output path must not invite tool calls (#1130).

`with_structured_output` binds exactly one tool (the schema). A prompt that
primes tool use makes models emit an unknown `web_search` call, which discards
the structured attempt and forces a free-text retry — an extra LLM round trip
and the loss of typed output.

These assert the constraint reaches the *rendered* prompt each agent actually
sends, not merely that the constant is referenced in the module.
"""
from __future__ import annotations

import inspect
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

import tradingagents.agents.analysts.sentiment_analyst as sentiment
from tradingagents.agents.managers.portfolio_manager import create_portfolio_manager
from tradingagents.agents.managers.research_manager import create_research_manager
from tradingagents.agents.trader.trader import create_trader
from tradingagents.agents.utils.structured import NO_EXTERNAL_TOOLS


def _capturing_llm(captured: dict, result):
    """LLM whose structured binding records the prompt it was handed."""
    structured = MagicMock()
    structured.invoke.side_effect = lambda prompt: (
        captured.__setitem__("prompt", prompt) or result
    )
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    return llm


def _prompt_text(prompt) -> str:
    """Flatten a captured prompt (str, message list, or objects) to text."""
    if isinstance(prompt, str):
        return prompt
    parts = []
    messages = prompt.to_messages() if hasattr(prompt, "to_messages") else prompt
    for m in messages:
        parts.append(m.get("content", "") if isinstance(m, dict) else getattr(m, "content", ""))
    return "\n".join(str(p) for p in parts)


def _tool_capturing_llm(captured: dict):
    class ToolLLM:
        def bind_tools(self, _tools):
            return RunnableLambda(
                lambda prompt: captured.__setitem__("prompt", prompt)
                or AIMessage(content="report", tool_calls=[])
            )

    return ToolLLM()


@pytest.mark.unit
def test_trader_prompt_states_constraint():
    from tradingagents.agents.schemas import TraderAction, TraderProposal

    captured = {}
    llm = _capturing_llm(captured, TraderProposal(action=TraderAction.BUY, reasoning="x"))
    create_trader(llm)({
        "company_of_interest": "NVDA",
        "investment_plan": "**Recommendation**: Buy",
        "market_report": "Current price $189.5; ATR 4.2.",
    })
    assert NO_EXTERNAL_TOOLS in _prompt_text(captured["prompt"])


@pytest.mark.unit
def test_research_manager_prompt_states_constraint():
    from tradingagents.agents.schemas import PortfolioRating, ResearchPlan

    captured = {}
    llm = _capturing_llm(
        captured,
        ResearchPlan(
            recommendation=PortfolioRating.BUY, rationale="x", strategic_actions="y"
        ),
    )
    create_research_manager(llm)({
        "company_of_interest": "NVDA",
        "investment_debate_state": {
            "history": "h", "bull_history": "b", "bear_history": "r",
            "current_response": "", "judge_decision": "", "count": 1,
        },
    })
    assert NO_EXTERNAL_TOOLS in _prompt_text(captured["prompt"])


@pytest.mark.unit
def test_portfolio_manager_prompt_states_constraint():
    from tradingagents.agents.schemas import PortfolioDecision, PortfolioRating

    captured = {}
    llm = _capturing_llm(
        captured,
        PortfolioDecision(
            rating=PortfolioRating.HOLD,
            executive_summary="x",
            investment_thesis="y",
        ),
    )
    risk = {
        "history": "h", "aggressive_history": "a", "conservative_history": "c",
        "neutral_history": "n", "current_aggressive_response": "",
        "current_conservative_response": "", "current_neutral_response": "",
        "latest_speaker": "Neutral", "count": 1,
    }
    create_portfolio_manager(llm)({
        "company_of_interest": "NVDA",
        "risk_debate_state": risk,
        "investment_plan": "plan",
        "trader_investment_plan": "trader plan",
    })
    assert NO_EXTERNAL_TOOLS in _prompt_text(captured["prompt"])


@pytest.mark.unit
def test_sentiment_prompt_states_constraint(monkeypatch):
    from tradingagents.agents.schemas import SentimentBand, SentimentReport

    # Pre-fetched sources are stubbed so the prompt builds without network I/O.
    monkeypatch.setattr(sentiment, "fetch_stocktwits_messages", lambda *a, **k: "st")
    monkeypatch.setattr(sentiment, "fetch_reddit_posts", lambda *a, **k: "rd")
    monkeypatch.setattr(sentiment.get_news, "func", lambda *a, **k: "news", raising=False)

    captured = {}
    llm = _capturing_llm(captured, SentimentReport(
        overall_band=SentimentBand.BULLISH, overall_score=7.5,
        confidence="high", narrative="n",
    ))
    sentiment.create_sentiment_analyst(llm)({
        "company_of_interest": "NVDA", "trade_date": "2026-01-15",
        "asset_type": "stock", "messages": [],
    })
    text = _prompt_text(captured["prompt"])
    assert NO_EXTERNAL_TOOLS in text
    # This agent binds no tools, so tool-range wording must not reappear.
    assert "tool-call date ranges" not in text


@pytest.mark.unit
def test_tool_using_analysts_keep_their_date_guidance():
    # The analysts that really do call tools keep the wording that anchors their
    # tool date ranges (#836) — this fix is scoped to no-tool agents.
    import tradingagents.agents.analysts.market_analyst as market
    import tradingagents.agents.analysts.news_analyst as news
    for module in (market, news):
        assert "tool-call date ranges" in inspect.getsource(module)


@pytest.mark.unit
def test_constraint_text_is_unambiguous():
    assert "do not call external tools" in NO_EXTERNAL_TOOLS.lower()
    # No template braces: it is embedded in ChatPromptTemplate strings, where
    # braces would be parsed as input variables.
    assert "{" not in NO_EXTERNAL_TOOLS and "}" not in NO_EXTERNAL_TOOLS


@pytest.mark.unit
def test_hose_market_and_fundamental_prompts_do_not_override_datavest_evidence():
    from tradingagents.agents.analysts.market_analyst import create_market_analyst
    from tradingagents.agents.analysts.fundamentals_analyst import create_fundamentals_analyst

    context = (
        "The instrument is `FPT.VN`. DATAVEST_VIETNAM_EVIDENCE: authoritative point-in-time "
        '{"price":{"price":123.0},"fundamentals":{"derivedMetrics":{"pe_ratio":20.5}}}'
    )
    state = {
        "company_of_interest": "FPT.VN",
        "trade_date": "2026-09-16",
        "asset_type": "stock",
        "instrument_context": context,
        "messages": [HumanMessage(content="FPT.VN")],
    }

    market_capture = {}
    fundamental_capture = {}
    create_market_analyst(_tool_capturing_llm(market_capture))(state)
    create_fundamentals_analyst(_tool_capturing_llm(fundamental_capture))(state)

    market_prompt = _prompt_text(market_capture["prompt"])
    fundamental_prompt = _prompt_text(fundamental_capture["prompt"])
    assert "Do not let get_verified_market_snapshot override it" in market_prompt
    assert "Do not let generic fundamental tools override it" in fundamental_prompt
    assert '"price":123.0' in market_prompt
    assert '"pe_ratio":20.5' in fundamental_prompt
