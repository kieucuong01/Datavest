from datetime import datetime, timezone
from tests.test_smart_insights_crypto_pulse import _observation

NOW = datetime(2026, 10, 5, 1, tzinfo=timezone.utc)


def whale_rows(day, exchange_day=None):
    return [_observation('bitinfocharts-top-addresses', 'crypto.large_address.balance_change_btc', '1250', symbol='BTC', effective_at=f'{day}T00:00:00Z'),
            _observation('coinmetrics-community', 'crypto.onchain.exchange_netflow_native', '-800', symbol='BTC', effective_at=f'{exchange_day or day}T00:00:00Z')]


def test_mismatched_or_expired_whale_evidence_never_becomes_mixed_or_directional():
    from app.services.smart_insights.crypto_pulse import build_crypto_market_pulse
    for rows in (whale_rows('2026-08-24', '2026-10-04'), whale_rows('2026-08-24')):
        flow = build_crypto_market_pulse(rows, mode='live', now=NOW)['tabs']['flows']['whaleFlows']
        assert flow['status'] == 'PARTIAL'
        assert flow['insight']['tone'] == 'INSUFFICIENT'
        assert flow['quality']['comparisonReady'] is False


def test_aligned_current_whale_evidence_retains_heuristic():
    from app.services.smart_insights.crypto_pulse import build_crypto_market_pulse
    flow = build_crypto_market_pulse(whale_rows('2026-10-04'), mode='live', now=NOW)['tabs']['flows']['whaleFlows']
    assert flow['insight']['tone'] == 'ACCUMULATION'
    assert flow['quality']['comparisonReady'] is True


def test_same_timestamp_with_different_flow_windows_is_not_comparable():
    from app.services.smart_insights.crypto_pulse import build_crypto_market_pulse
    rows = whale_rows('2026-10-04')
    rows[1]['value']['dimensions']['interval'] = '1h'
    flow = build_crypto_market_pulse(rows, mode='live', now=NOW)['tabs']['flows']['whaleFlows']
    assert flow['quality']['comparisonReady'] is False
    assert flow['insight']['tone'] == 'INSUFFICIENT'


def test_refetching_an_old_value_does_not_make_widget_fresh():
    from app.services.smart_insights.crypto_pulse import build_crypto_market_pulse
    row = _observation('alternative-fng', 'crypto.fear_greed.index', '66')
    row['observedAt'] = NOW.isoformat()
    fear = build_crypto_market_pulse([row], mode='live', now=NOW)['tabs']['overview']['fearGreed']
    assert fear['freshness'] == 'STALE'
    assert fear['latest']['value'] == 66  # retain historical evidence


def test_weekly_and_business_daily_cadences_do_not_use_one_daily_cutoff():
    from app.services.smart_insights.crypto_pulse import build_crypto_market_pulse
    rows = [_observation('coinshares-weekly', 'crypto.coinshares.net_flow_usd', '1', effective_at='2026-09-29T00:00:00Z'),
            _observation('farside-btc-etf', 'crypto.etf.net_flow_usd', '2', symbol='BTC', dimensions={'fund':'TOTAL'}, effective_at='2026-10-02T00:00:00Z')]
    overview = build_crypto_market_pulse(rows, mode='live', now=NOW)['tabs']['overview']
    assert overview['fundFlows']['freshness'] == 'FRESH'
    assert overview['etfFlows']['freshness'] == 'FRESH'


def test_default_refresh_uses_only_enabled_core_sources_and_preserves_explicit_override(monkeypatch):
    from app.tasks import smart_insights as tasks
    from app.services.smart_insights import repository
    class Repo:
        def list_enabled_source_codes(self):
            return ('datavest-market-bars', 'coinmetrics-community', 'fred', 'coinglass-margin-borrow', 'bybit-derivatives')
        def create_refresh_request(self, **kwargs):
            self.sources = kwargs['source_codes']
            return 'test'
    repo = Repo()
    monkeypatch.setattr(repository, 'SmartInsightsRepository', lambda: repo)
    monkeypatch.setattr(tasks.run_smart_insights_refresh, 'delay', lambda _: None)
    monkeypatch.setenv('SMART_INSIGHTS_AUTO_REFRESH', 'true')
    monkeypatch.delenv('SMART_INSIGHTS_AUTO_REFRESH_SOURCE_CODES', raising=False)
    tasks.enqueue_smart_insights_refresh.run()
    assert set(repo.sources) == {'datavest-market-bars', 'coinmetrics-community', 'bybit-derivatives'}
    monkeypatch.setenv('SMART_INSIGHTS_AUTO_REFRESH_SOURCE_CODES', 'fred')
    tasks.enqueue_smart_insights_refresh.run()
    assert repo.sources == ('fred',)
