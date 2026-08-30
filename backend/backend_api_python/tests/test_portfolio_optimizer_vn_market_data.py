"""KBS public daily market-data contracts for VN optimizer inputs."""

from __future__ import annotations

from datetime import datetime, timezone
import json

import pytest

from app.services.smart_insights.transport import HttpResponse


class FakeTransport:
    def __init__(self, payload, *, status=200, response_url=None, error=None):
        self.payload = payload
        self.status = status
        self.response_url = response_url
        self.error = error
        self.requests = []

    def fetch(self, url, *, timeout_seconds, max_bytes, headers=None):
        self.requests.append({"url": url, "timeout_seconds": timeout_seconds, "max_bytes": max_bytes, "headers": headers})
        if self.error is not None:
            raise self.error
        return HttpResponse(self.status, self.response_url or url, json.dumps(self.payload).encode("utf-8"))


def gateway_for(payload, **transport_options):
    from app.services.portfolio_optimizer.quantdinger_gateway import QuantDingerOptimizerGateway

    transport = FakeTransport(payload, **transport_options)
    return QuantDingerOptimizerGateway(vn_transport=transport), transport


def test_vn_equity_daily_contract_uses_fixed_kbs_url_and_vnd_prices():
    from app.services.portfolio_optimizer.market_data import Instrument

    gateway, transport = gateway_for({"data_day": [
        {"t": "2025-01-03 07:00", "o": 101000, "h": 103000, "l": 100500, "c": 102500, "v": 1200},
        {"t": "2025-01-02 07:00", "o": 100000, "h": 102000, "l": 99500, "c": 101250, "v": 1000},
        {"t": "2025-01-01 07:00", "o": 98000, "h": 100000, "l": 97500, "c": 99000, "v": 900},
    ]})
    series = gateway.fetch_daily(
        Instrument(market="VNStock", symbol="FPT", currency="VND"),
        start_date="2025-01-02", end_date="2025-01-03",
    )

    assert transport.requests == [{
        "url": "https://kbbuddywts.kbsec.com.vn/iis-server/investment/stocks/FPT/data_day?sdate=02-01-2025&edate=03-01-2025",
        "timeout_seconds": 20,
        "max_bytes": 5_000_000,
        "headers": {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; DataVest-MarketData/1.0)",
        },
    }]
    assert series.timestamps == (
        int(datetime(2025, 1, 2, 0, tzinfo=timezone.utc).timestamp()),
        int(datetime(2025, 1, 3, 0, tzinfo=timezone.utc).timestamp()),
    )
    assert series.closes == (101250.0, 102500.0)
    assert series.currency == "VND"
    assert series.provider == "kbs-public"
    assert series.fallback_chain == ("kbs-public",)
    assert series.coverage == 1.0
    assert len(series.checksum) == 64
    assert series.data_class == "LIVE"
    assert series.price_unit == "VND"
    assert series.mark_to_market_supported is True


def test_vn_index_daily_contract_uses_index_path_and_disables_mark_to_market():
    from app.services.portfolio_optimizer.market_data import Instrument

    gateway, transport = gateway_for({"data_day": [
        {"t": "2025-01-02 07:00", "o": 1260, "h": 1265, "l": 1258, "c": 1263.5, "v": 500000}
    ]})
    series = gateway.fetch_daily(
        Instrument(market="VNStock", symbol="VNINDEX", currency="VND"),
        start_date="2025-01-02", end_date="2025-01-02",
    )

    assert "/investment/index/VNINDEX/data_day?" in transport.requests[0]["url"]
    assert series.closes == (1263.5,)
    assert series.provider == "kbs-public"
    assert series.fallback_chain == ("kbs-public",)
    assert series.price_unit == "INDEX_POINTS"
    assert series.mark_to_market_supported is False


@pytest.mark.parametrize(("instrument", "start_date", "end_date", "payload", "error"), [
    ({"symbol": "FPT.HM", "currency": "VND"}, "2025-01-02", "2025-01-03", {}, "invalid_symbol"),
    ({"symbol": "FPT", "currency": "USD"}, "2025-01-02", "2025-01-03", {}, "invalid_currency"),
    ({"symbol": "FPT", "currency": "VND"}, "2025-01-03", "2025-01-02", {}, "invalid_date_range"),
    ({"symbol": "FPT", "currency": "VND"}, "2025-01-02", "2025-01-03", {"data_day": []}, "no_bars"),
    ({"symbol": "FPT", "currency": "VND"}, "2025-01-02", "2025-01-03", {"wrong": []}, "invalid_schema"),
    ({"symbol": "FPT", "currency": "VND"}, "2025-01-02", "2025-01-03", {"data_day": [{"t": "2025-01-02 07:00", "o": 100, "h": 102, "l": 99, "c": 101}]}, "invalid_schema"),
    ({"symbol": "FPT", "currency": "VND"}, "2025-01-02", "2025-01-03", {"data_day": [{"t": "2025-01-02 07:00", "o": 100, "h": 102, "l": 99, "c": -1, "v": 5}]}, "invalid_schema"),
])
def test_vn_daily_fails_closed_for_invalid_inputs_or_bars(instrument, start_date, end_date, payload, error):
    from app.services.portfolio_optimizer.market_data import Instrument

    gateway, _ = gateway_for(payload)
    with pytest.raises(ValueError, match=f"vn_market_data_unavailable: {error}"):
        gateway.fetch_daily(Instrument(market="VNStock", **instrument), start_date=start_date, end_date=end_date)


@pytest.mark.parametrize(("options", "error"), [
    ({"error": RuntimeError("upstream detail")}, "provider_request_failed"),
    ({"status": 503}, "provider_request_failed"),
    ({"response_url": "https://example.com/redirected"}, "provider_request_failed"),
])
def test_vn_daily_sanitizes_transport_status_and_redirect_failures(options, error):
    from app.services.portfolio_optimizer.market_data import Instrument

    gateway, _ = gateway_for({"data_day": []}, **options)
    with pytest.raises(ValueError, match=f"vn_market_data_unavailable: {error}"):
        gateway.fetch_daily(
            Instrument(market="VNStock", symbol="FPT", currency="VND"),
            start_date="2025-01-02", end_date="2025-01-03",
        )


def test_vn_daily_rejects_duplicate_local_trading_day():
    from app.services.portfolio_optimizer.market_data import Instrument

    gateway, _ = gateway_for({"data_day": [
        {"t": "2025-01-02 07:00", "o": 100, "h": 102, "l": 99, "c": 101, "v": 5},
        {"t": "2025-01-02 14:00", "o": 101, "h": 103, "l": 100, "c": 102, "v": 7},
    ]})
    with pytest.raises(ValueError, match="vn_market_data_unavailable: invalid_schema"):
        gateway.fetch_daily(
            Instrument(market="VNStock", symbol="FPT", currency="VND"),
            start_date="2025-01-02", end_date="2025-01-02",
        )


def test_vn_daily_does_not_import_vnstock_or_vnai(monkeypatch):
    import builtins
    from app.services.portfolio_optimizer.market_data import Instrument

    gateway, _ = gateway_for({"data_day": [
        {"t": "2025-01-02 07:00", "o": 100, "h": 102, "l": 99, "c": 101, "v": 5}
    ]})
    imported = []
    original_import = builtins.__import__

    def observe(name, *args, **kwargs):
        if name == "vnai" or name.startswith("vnstock"):
            imported.append(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", observe)
    series = gateway.fetch_daily(
        Instrument(market="VNStock", symbol="FPT", currency="VND"),
        start_date="2025-01-02", end_date="2025-01-02",
    )
    assert series.provider == "kbs-public"
    assert imported == []
