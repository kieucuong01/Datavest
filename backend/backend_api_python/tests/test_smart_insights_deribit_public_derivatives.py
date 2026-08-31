from datetime import datetime, timezone


class FakeDeribitClient:
    def __init__(self, futures, options): self.futures, self.options = futures, options
    def get(self, method, params): return self.futures if params["kind"] == "future" else self.options


def test_deribit_collector_emits_options_and_two_futures_basis_points():
    from app.services.smart_insights.deribit_public_derivatives import DeribitPublicDerivativesCollector
    from app.services.smart_insights.derivatives import CALL_OI, FAR_BASIS, NEAR_BASIS, PUT_CALL_OI_RATIO, PUT_OI

    collector = DeribitPublicDerivativesCollector(client=FakeDeribitClient(
        [{"instrument_name": "BTC-PERPETUAL", "estimated_delivery_price": "100"}, {"instrument_name": "BTC-30AUG26", "mark_price": "101", "expiration_timestamp": "1788076800000"}, {"instrument_name": "BTC-27SEP26", "mark_price": "102", "expiration_timestamp": "1790553600000"}],
        [{"instrument_name": "BTC-30AUG26-100-C", "open_interest": "4"}, {"instrument_name": "BTC-30AUG26-100-P", "open_interest": "2"}],
    ))
    rows = collector.collect(datetime(2026, 8, 1, tzinfo=timezone.utc))

    assert {row.value["metric"] for row in rows} == {NEAR_BASIS, FAR_BASIS, CALL_OI, PUT_OI, PUT_CALL_OI_RATIO}
    assert next(row for row in rows if row.value["metric"] == PUT_CALL_OI_RATIO).value["value"] == "0.5"
