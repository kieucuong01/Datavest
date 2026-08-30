"""Ported golden contracts for the DataVest OpenBB-Deribit adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest


NOW = datetime(2026, 8, 19, 9, 30, tzinfo=timezone.utc)


class FakeOpenBBDeribitClient:
    def collect_daily(self, *, as_of: datetime) -> dict[str, object]:
        assert as_of == NOW
        return {
            "observed_at": "2026-08-19T09:30:00+00:00",
            "futures_curve": {
                "BTC": [
                    {"expiration": "2026-08-19", "price": "115000"},
                    {"expiration": "2026-08-29", "price": "115500"},
                    {"expiration": "2026-12-26", "price": "120000"},
                ],
                "ETH": [
                    {"expiration": "2026-08-19", "price": "4300"},
                    {"expiration": "2026-08-29", "price": "4330"},
                    {"expiration": "2026-12-26", "price": "4550"},
                ],
            },
            "futures_historical": {
                "BTC": [
                    {
                        "date": "2026-08-18T00:00:00+00:00",
                        "close": "114800",
                        "volume_notional": "250000000",
                    }
                ],
                "ETH": [
                    {
                        "date": "2026-08-18T00:00:00+00:00",
                        "close": "4280",
                        "volume_notional": "120000000",
                    }
                ],
            },
            "options_chains": {
                "BTC": [
                    {"option_type": "call", "open_interest": "1000"},
                    {"option_type": "put", "open_interest": "800"},
                ],
                "ETH": [
                    {"option_type": "call", "open_interest": "700"},
                    {"option_type": "put", "open_interest": "900"},
                ],
            },
        }


def test_openbb_deribit_port_preserves_daily_metric_golden_values():
    from app.services.smart_insights.openbb_deribit import OpenBBDeribitCollector

    rows = OpenBBDeribitCollector(client=FakeOpenBBDeribitClient()).collect(NOW)

    assert len(rows) == 14
    assert {row.source_code for row in rows} == {"openbb-deribit"}
    assert {row.data_class.value for row in rows} == {"LIVE"}
    assert {row.symbol for row in rows} == {"BTC", "ETH"}
    assert {row.effective_at for row in rows} == {
        datetime(2026, 8, 18, tzinfo=timezone.utc)
    }
    assert {row.value["metric"] for row in rows} == {
        "crypto.derivatives.futures.near_term_annualized_basis",
        "crypto.derivatives.futures.far_term_annualized_basis",
        "crypto.derivatives.futures.perpetual_close_usd",
        "crypto.derivatives.futures.perpetual_volume_notional_usd",
        "crypto.derivatives.options.call_open_interest",
        "crypto.derivatives.options.put_open_interest",
        "crypto.derivatives.options.put_call_open_interest_ratio",
    }
    btc_near = next(
        row
        for row in rows
        if row.symbol == "BTC"
        and row.value["metric"] == "crypto.derivatives.futures.near_term_annualized_basis"
    )
    assert Decimal(str(btc_near.value["value"])).quantize(
        Decimal("0.000000000001")
    ) == Decimal("0.158695652174")
    btc_ratio = next(
        row
        for row in rows
        if row.symbol == "BTC"
        and row.value["metric"] == "crypto.derivatives.options.put_call_open_interest_ratio"
    )
    assert Decimal(str(btc_ratio.value["value"])) == Decimal("0.8")


def test_openbb_deribit_rejects_one_sided_option_coverage():
    from app.services.smart_insights.openbb_deribit import (
        OpenBBDeribitCollector,
        OpenBBDeribitUnavailable,
    )

    class OneSidedOptions(FakeOpenBBDeribitClient):
        def collect_daily(self, *, as_of: datetime) -> dict[str, object]:
            payload = super().collect_daily(as_of=as_of)
            payload["options_chains"] = {
                "BTC": [{"option_type": "call", "open_interest": "1000"}],
                "ETH": [{"option_type": "call", "open_interest": "700"}],
            }
            return payload

    with pytest.raises(OpenBBDeribitUnavailable, match="OPTIONS_COVERAGE_INCOMPLETE"):
        OpenBBDeribitCollector(client=OneSidedOptions()).collect(NOW)


def test_openbb_deribit_is_registered_but_needs_isolated_runtime():
    from app.services.smart_insights.collectors import default_collector_registry
    from app.services.smart_insights.sources import source_for_code

    source = source_for_code("openbb-deribit")
    assert source.enabled_by_default is True
    assert source.methodology_version == "openbb-deribit-v1"
    assert "openbb-deribit" in default_collector_registry()


def test_openbb_subprocess_failure_does_not_expose_stderr(tmp_path):
    import subprocess

    from app.services.smart_insights.openbb_deribit import (
        OpenBBDeribitSubprocessClient,
        OpenBBDeribitUnavailable,
    )

    executable = tmp_path / "python.exe"
    executable.touch()

    def runner(*_args, **_kwargs):
        return subprocess.CompletedProcess([], 1, stdout="", stderr="provider-secret")

    client = OpenBBDeribitSubprocessClient(
        python_executable=str(executable), runner=runner
    )
    with pytest.raises(OpenBBDeribitUnavailable) as error:
        client.collect_daily(as_of=NOW)
    assert str(error.value) == "OPENBB_DERIBIT_UNAVAILABLE"
    assert "provider-secret" not in str(error.value)
