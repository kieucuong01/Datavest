"""Bounded HOSE research consumes the frozen, dated run evidence."""
from datetime import datetime, timezone
import pytest


def test_pilot_registry_excludes_benchmarks_and_is_small():
    from app.services.hose_research import HOSE_RESEARCH_PILOT
    assert [item['symbol'] for item in HOSE_RESEARCH_PILOT] == ['FPT', 'HPG', 'VCB']
    assert all(item['market'] == 'VNStock' and item['selectionReason'] for item in HOSE_RESEARCH_PILOT)


def test_projection_preserves_dates_zero_and_missing_metrics_without_private_metadata():
    from app.services.hose_research import project_hose_research
    evidence = {
        'asOf': '2026-10-02T16:59:59+00:00', 'checksum': 'frozen-checksum',
        'instrument': {'market': 'VNStock', 'symbol': 'FPT', 'name': 'FPT', 'sector': 'Technology'},
        'price': {'price': 100000, 'volume': 1000, 'time': 1790906400, 'timeframe': '1D', 'source': 'vndirect'},
        'provenance': {'price': {'fetchedAt': '2026-10-03T01:00:00Z'}},
        'fundamentals': {'observations': [
            {'metric': 'net_income', 'value': 0, 'unit': 'VND', 'periodEnd': '2025-12-31',
             'availableAt': '2026-03-01T00:00:00Z', 'source': 'vndirect', 'sourceUrl': 'https://example.com/filing',
             'reportScope': 'UNKNOWN', 'privateNote': 'secret'},
            {'metric': 'revenue', 'value': 1e12, 'periodEnd': '2026-12-31', 'availableAt': '2027-01-01', 'source': 'vndirect'},
        ]}, 'userId': 7, 'prompt': 'private',
    }
    report = project_hose_research(evidence)
    assert report['checksum'] == 'frozen-checksum'
    assert report['price']['value'] == 100000
    assert report['price']['status'] == 'DAILY'
    assert report['price']['retrievedAt'] == '2026-10-03T01:00:00+00:00'
    facts = {row['metric']: row for row in report['metrics']}
    assert facts['net_income']['value'] == 0
    assert facts['net_income']['status'] == 'PARTIAL'
    assert facts['revenue']['value'] is None
    assert facts['pe_ratio']['value'] is None
    assert 'secret' not in str(report) and 'private' not in str(report)


def test_benchmark_builder_filters_future_bars_and_marks_missing_benchmark(monkeypatch):
    from app.services import trading_agents_vietnam as module
    cutoff = datetime(2026, 10, 2, 16, 59, tzinfo=timezone.utc)
    def bars(**kwargs):
        if kwargs['symbol'] == 'VN30':
            return []
        return [
            {'time': int(datetime(2026, 10, 1, 8, tzinfo=timezone.utc).timestamp()), 'close': 100, 'source': 'vndirect'},
            {'time': int(datetime(2026, 10, 2, 8, tzinfo=timezone.utc).timestamp()), 'close': 102, 'source': 'vndirect'},
            {'time': int(datetime(2026, 10, 5, 8, tzinfo=timezone.utc).timestamp()), 'close': 999, 'source': 'vndirect'},
        ]
    monkeypatch.setattr(module.DataSourceFactory, 'get_kline', bars)
    context, gaps = module.build_hose_benchmark_context(cutoff)
    assert context['VNINDEX']['price'] == 102
    assert context['VNINDEX']['changePct'] == pytest.approx(2)
    assert context['VNINDEX']['tradeDate'] == '2026-10-02'
    assert context['VNINDEX']['investable'] is False
    assert 'VN30' not in context
    assert {'field': 'benchmark:VN30', 'reason': 'NO_POINT_IN_TIME_PRICE'} in gaps


def test_old_price_is_stale_at_the_report_cutoff():
    from app.services.hose_research import project_hose_research
    report = project_hose_research({'instrument': {'market': 'VNStock', 'symbol': 'FPT'},
                                   'asOf': '2026-10-02T16:59:59Z',
                                   'price': {'price': 100, 'time': '2026-09-01T08:00:00Z', 'timeframe': '1D'}})
    assert report['price']['status'] == 'STALE'


def test_growth_only_compares_same_fiscal_period_frequency_and_verified_scope():
    from app.services.hose_research import project_hose_research
    base = {'metric': 'revenue', 'unit': 'VND', 'frequency': 'ANNUAL', 'source': 'vndirect', 'reportScope': 'CONSOLIDATED'}
    evidence = {'instrument': {'market': 'VNStock', 'symbol': 'FPT'}, 'asOf': '2026-10-02',
                'fundamentals': {'observations': [
                    {**base, 'value': 120, 'periodEnd': '2025-12-31', 'availableAt': '2026-03-01'},
                    {**base, 'value': 100, 'periodEnd': '2024-12-31', 'availableAt': '2025-03-01'},
                    {**base, 'value': 10, 'periodEnd': '2025-09-30', 'availableAt': '2025-11-01', 'frequency': 'QUARTERLY'},
                ]}}
    metric = next(row for row in project_hose_research(evidence)['metrics'] if row['metric'] == 'revenue')
    assert metric['growthPct'] == pytest.approx(20)
    evidence['fundamentals']['observations'][1]['reportScope'] = 'SEPARATE'
    metric = next(row for row in project_hose_research(evidence)['metrics'] if row['metric'] == 'revenue')
    assert metric['growthPct'] is None


def test_shared_worker_publishes_the_same_frozen_evidence_without_refetching():
    from app.services.smart_insights.shared_research_publisher import SharedResearchPublisher
    from app.services.smart_insights.shared_reports import SharedResearchReportsService
    class Reports:
        completed = []
        def list_pending_deep(self, **kwargs):
            return [{'asset_key': 'vnstock:FPT', 'period_key': '2026-09-28', 'source_run_id': 'system-run'}]
        def mark_complete(self, **kwargs):
            self.completed.append(kwargs)
    class Trading:
        def get_run_for_worker(self, **kwargs):
            return {'user_id': 42, 'status': 'succeeded', 'evidence_json': {
                'instrument': {'market': 'VNStock', 'symbol': 'FPT'}, 'asOf': '2026-09-28', 'checksum': 'same-frozen',
                'notes': 'private', 'userId': 99}}
    reports = Reports()
    result = SharedResearchPublisher(reports=reports, trading_repository=Trading(), system_user_id=lambda: 42,
                                     fetch_artifact=lambda **kwargs: (b'# FPT report', 'text/markdown')).sync_pending_deep_reports()
    assert result == {'published': 1, 'failed': 0, 'pending': 0}
    payload = reports.completed[0]['payload']
    assert payload['researchEvidence']['checksum'] == 'same-frozen'
    projected = SharedResearchReportsService.project({'asset_key': 'vnstock:FPT', 'report_kind': 'deep',
                                                      'period_key': '2026-09-28', 'payload': payload})
    assert projected['researchEvidence']['symbol'] == 'FPT'
    assert 'private' not in str(projected)
