"""Application contracts for immutable optimizer runs and paper rebalances."""

from __future__ import annotations

from dataclasses import replace

import pytest


class FakeGateway:
    def __init__(self, series, fx=None):
        self.series = series
        self.fx = fx or {}

    def fetch_daily(self, instrument, *, start_date, end_date):
        del start_date, end_date
        return self.series[instrument.symbol]

    def fetch_fx(self, source_currency, target_currency, *, start_date, end_date):
        del start_date, end_date
        return self.fx.get((source_currency, target_currency))


class FakeRepository:
    def __init__(self):
        self.runs = {}
        self.plans = {}
        self.applies = {}

    def create_run(self, **payload):
        run_id = "run-1"
        self.runs[run_id] = {"id": run_id, **payload}
        return run_id

    def get_run(self, *, run_id, user_id):
        run = self.runs.get(run_id)
        return run if run and run["user_id"] == user_id else None

    def create_plan(self, **payload):
        plan_id = "plan-1"
        self.plans[plan_id] = {"id": plan_id, "status": "PREVIEW", **payload}
        return self.plans[plan_id]

    def list_managed_positions(self, *, user_id):
        del user_id
        return []

    def apply_plan(self, *, plan_id, run_id, user_id, idempotency_key):
        key = (user_id, idempotency_key)
        if key in self.applies:
            return self.applies[key]
        plan = self.plans.get(plan_id)
        if not plan or plan["run_id"] != run_id or plan["user_id"] != user_id:
            return None
        result = {"planId": plan_id, "status": "APPLIED", "executionMode": "SIMULATED"}
        self.applies[key] = result
        return result


def live_series(symbol, *, currency="USD", data_class="LIVE", provider="fixture"):
    from app.services.portfolio_optimizer.market_data import PriceSeries

    return PriceSeries(
        market="USStock",
        symbol=symbol,
        currency=currency,
        timestamps=tuple(range(1, 42)),
        closes=tuple(100 + index * (1 + len(symbol) / 10) for index in range(41)),
        provider=provider,
        fallback_chain=(provider,),
        coverage=1.0,
        checksum=f"checksum-{symbol}-{currency}",
        data_class=data_class,
    )


def request_payload():
    return {
        "method": "minimum_variance",
        "baseCurrency": "USD",
        "startDate": "2025-01-01",
        "endDate": "2025-12-31",
        "maxWeight": 0.8,
        "instruments": [
            {"market": "USStock", "symbol": "AAPL", "currency": "USD"},
            {"market": "USStock", "symbol": "MSFT", "currency": "USD"},
        ],
    }


def test_create_run_pins_live_provenance_and_immutable_result():
    from app.services.portfolio_optimizer.service import PortfolioOptimizerService

    repository = FakeRepository()
    service = PortfolioOptimizerService(
        repository=repository,
        gateway=FakeGateway({"AAPL": live_series("AAPL"), "MSFT": live_series("MSFT")}),
    )

    result = service.create_run(user_id=7, payload=request_payload())

    assert result["id"] == "run-1"
    stored = repository.runs["run-1"]
    assert stored["user_id"] == 7
    assert stored["input_checksum"]
    assert len(stored["series"]) == 2
    assert {item.provider for item in stored["series"]} == {"fixture"}
    assert sum(item["weightBps"] for item in stored["result"]["allocations"]) == 10_000


@pytest.mark.parametrize(
    "series,error",
    [
        (replace(live_series("AAPL"), data_class="DEMO"), "live_market_data_required"),
        (replace(live_series("AAPL"), provider=""), "provider_provenance_required"),
        (replace(live_series("AAPL"), checksum=""), "market_data_checksum_required"),
        (replace(live_series("AAPL"), coverage=0.0), "market_data_coverage_required"),
    ],
)
def test_create_run_rejects_nonproduction_or_unproven_series(series, error):
    from app.services.portfolio_optimizer.service import PortfolioOptimizerService

    service = PortfolioOptimizerService(
        repository=FakeRepository(),
        gateway=FakeGateway({"AAPL": series, "MSFT": live_series("MSFT")}),
    )
    with pytest.raises(ValueError, match=error):
        service.create_run(user_id=7, payload=request_payload())


def test_create_run_fails_closed_when_production_fx_is_missing():
    from app.services.portfolio_optimizer.service import PortfolioOptimizerService

    payload = request_payload()
    payload["instruments"][0]["currency"] = "VND"
    service = PortfolioOptimizerService(
        repository=FakeRepository(),
        gateway=FakeGateway(
            {"AAPL": live_series("AAPL", currency="VND"), "MSFT": live_series("MSFT")}
        ),
    )
    with pytest.raises(ValueError, match="production_fx_unavailable"):
        service.create_run(user_id=7, payload=payload)


def test_preview_uses_pinned_base_currency_prices_after_fx_conversion():
    from app.services.portfolio_optimizer.service import PortfolioOptimizerService

    payload = request_payload()
    payload["instruments"][0]["currency"] = "VND"
    local = live_series("AAPL", currency="VND")
    fx = replace(
        live_series("VNDUSD", currency="USD"),
        market="Forex",
        closes=tuple(0.00004 for _ in range(41)),
        checksum="checksum-vndusd",
    )
    repository = FakeRepository()
    service = PortfolioOptimizerService(
        repository=repository,
        gateway=FakeGateway({"AAPL": local, "MSFT": live_series("MSFT")}, fx={("VND", "USD"): fx}),
    )
    service.create_run(user_id=7, payload=payload)
    preview = service.preview(user_id=7, run_id="run-1", portfolio_value=10_000)

    aapl = next(item for item in preview["orders"] if item["symbol"] == "AAPL")
    assert aapl["markPrice"] == pytest.approx(local.closes[-1] * 0.00004)


def test_create_run_persists_returns_only_index_price_metadata():
    from app.services.portfolio_optimizer.service import PortfolioOptimizerService

    payload = request_payload()
    payload["baseCurrency"] = "VND"
    payload["instruments"] = [
        {"market": "VNStock", "symbol": "VNINDEX", "currency": "VND"},
        {"market": "VNStock", "symbol": "FPT", "currency": "VND"},
    ]
    index = replace(
        live_series("VNINDEX", currency="VND"),
        market="VNStock",
        price_unit="INDEX_POINTS",
        mark_to_market_supported=False,
    )
    equity = replace(
        live_series("FPT", currency="VND"),
        market="VNStock",
        price_unit="VND",
    )
    repository = FakeRepository()
    service = PortfolioOptimizerService(
        repository=repository,
        gateway=FakeGateway({"VNINDEX": index, "FPT": equity}),
    )

    service.create_run(user_id=7, payload=payload)

    stored_index = repository.runs["run-1"]["input_snapshot"]["series"][0]
    assert stored_index["priceUnit"] == "INDEX_POINTS"
    assert stored_index["markToMarketSupported"] is False


def test_preview_rejects_returns_only_index_mark_to_market():
    from app.services.portfolio_optimizer.service import PortfolioOptimizerService

    payload = request_payload()
    payload["baseCurrency"] = "VND"
    payload["instruments"] = [
        {"market": "VNStock", "symbol": "VNINDEX", "currency": "VND"},
        {"market": "VNStock", "symbol": "FPT", "currency": "VND"},
    ]
    index = replace(
        live_series("VNINDEX", currency="VND"),
        market="VNStock",
        price_unit="INDEX_POINTS",
        mark_to_market_supported=False,
    )
    equity = replace(
        live_series("FPT", currency="VND"),
        market="VNStock",
        price_unit="VND",
    )
    repository = FakeRepository()
    service = PortfolioOptimizerService(
        repository=repository,
        gateway=FakeGateway({"VNINDEX": index, "FPT": equity}),
    )
    service.create_run(user_id=7, payload=payload)

    with pytest.raises(
        ValueError, match="optimizer_mark_to_market_unavailable: VNINDEX"
    ):
        service.preview(user_id=7, run_id="run-1", portfolio_value=10_000)


def test_run_ownership_preview_and_apply_are_paper_only_and_idempotent():
    from app.services.portfolio_optimizer.service import PortfolioOptimizerService

    repository = FakeRepository()
    service = PortfolioOptimizerService(
        repository=repository,
        gateway=FakeGateway({"AAPL": live_series("AAPL"), "MSFT": live_series("MSFT")}),
    )
    service.create_run(user_id=7, payload=request_payload())

    assert service.get_run(user_id=8, run_id="run-1") is None
    preview = service.preview(user_id=7, run_id="run-1", portfolio_value=10_000)
    assert preview["status"] == "PREVIEW"
    assert preview["executionMode"] == "SIMULATED"
    assert all(item["markPrice"] > 0 for item in preview["orders"])

    first = service.apply(
        user_id=7, run_id="run-1", plan_id="plan-1", idempotency_key="idem-key-1"
    )
    second = service.apply(
        user_id=7, run_id="run-1", plan_id="plan-1", idempotency_key="idem-key-1"
    )
    assert first == second
    assert first["executionMode"] == "SIMULATED"


def test_request_rejects_unsupported_universe_and_excessive_window():
    from app.services.portfolio_optimizer.service import PortfolioOptimizerService

    service = PortfolioOptimizerService(repository=FakeRepository(), gateway=FakeGateway({}))
    payload = request_payload()
    payload["instruments"][0]["market"] = "CNStock"
    with pytest.raises(ValueError, match="unsupported_optimizer_market"):
        service.create_run(user_id=7, payload=payload)

    payload = request_payload()
    payload["startDate"] = "2010-01-01"
    payload["endDate"] = "2025-12-31"
    with pytest.raises(ValueError, match="optimizer_window_too_large"):
        service.create_run(user_id=7, payload=payload)
