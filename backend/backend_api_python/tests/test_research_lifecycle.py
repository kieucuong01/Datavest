from datetime import date, datetime, timedelta, timezone
import pytest


def test_weekly_validity_uses_period_not_late_generation_time():
    from app.services.smart_insights.report_lifecycle import report_validity
    fresh = report_validity('2026-09-30', today=date(2026, 10, 4))
    assert fresh['validUntil'] == '2026-10-05T00:00:00+07:00'
    assert fresh['isExpired'] is False
    assert report_validity('2026-09-30', today=date(2026, 10, 5))['isExpired'] is True


def test_retry_policy_is_bounded_and_never_steals_active_runs():
    from app.services.smart_insights.report_lifecycle import can_retry
    now = datetime(2026, 10, 5, tzinfo=timezone.utc)
    row = dict(status='failed', attempt_count=1, failure_code='dispatch_failed', updated_at=now-timedelta(hours=4))
    assert can_retry(row, now=now)
    assert not can_retry({**row, 'attempt_count': 3}, now=now)
    assert not can_retry({**row, 'updated_at': now}, now=now)
    assert not can_retry({**row, 'failure_code': 'sync_failed', 'source_run_id': 'active'}, now=now)
    assert can_retry({**row, 'status': 'pending', 'source_run_id': None}, now=now)
    assert not can_retry({**row, 'status': 'pending', 'source_run_id': 'active'}, now=now)


def test_dispatch_failure_marks_claim_failed_and_keeps_authorization():
    from app.services.smart_insights.shared_research_access import SharedResearchAccessService
    from tests.test_shared_research_reports import FakePublicRepository, FakeRepository
    class Reports(FakePublicRepository):
        def mark_failed(self, **kwargs):
            self.failure = kwargs
    reports = Reports()
    def fail(*args):
        raise RuntimeError('broker unavailable')
    service = SharedResearchAccessService(public_repository=reports, shared_repository=FakeRepository(), watchlist_loader=lambda _: [], dispatch=fail)
    result = service.request(user_id=7, asset_key='crypto:BTC/USDT', report_kind='deep', today=date(2026, 10, 5))
    assert result['claimed'] is True
    assert reports.failure['failure_code'] == 'dispatch_failed'


def test_runtime_refresh_materializes_evidence_without_opinions(monkeypatch):
    from app.services.smart_insights import collectors
    from app.services.smart_insights.snapshot_pipeline import SnapshotMaterializer
    class Coordinator:
        def __init__(self, **kwargs):
            self.publisher = kwargs['snapshot_publisher']
        def execute(self, run_id):
            assert isinstance(self.publisher.__self__, SnapshotMaterializer)
            assert self.publisher.__self__.include_opinions is False
            return {'status': 'SUCCEEDED'}
    monkeypatch.setattr(collectors, 'SmartInsightsRepository', lambda: object())
    monkeypatch.setattr(collectors, 'default_collector_registry', lambda **_: {})
    monkeypatch.setattr(collectors, 'RefreshCoordinator', Coordinator)
    assert collectors.execute_refresh('fake')['status'] == 'SUCCEEDED'


def test_public_weekly_schedule_and_worker_redelivery_do_not_duplicate_ai_runs():
    from app.services.smart_insights.public_research_publisher import PublicResearchPublisher
    from tests.test_public_research_publisher import _Reports
    class Trading:
        calls = []
        def create_run(self, **kwargs):
            self.calls.append(kwargs)
    reports, trading = _Reports(), Trading()
    publisher = PublicResearchPublisher(reports=reports, trading_repository=trading,
        enqueue_trading_run=lambda _: None, system_user_id=lambda: 42)
    first = publisher.enqueue_weekly_deep_reports(effective_date=date(2026, 10, 7))
    second = publisher.enqueue_weekly_deep_reports(effective_date=date(2026, 10, 8))
    assert first == {'queued': 4, 'failed': 0}
    assert second == {'queued': 0, 'failed': 0}
    assert {call['request']['analysis_date'] for call in trading.calls} == {'2026-10-05'}
    result = publisher.enqueue_claimed_deep_report(asset_key='crypto:BTC/USDT', effective_date=date(2026, 10, 5))
    assert result['queued'] is False
    assert len(trading.calls) == 4


def test_artifact_outage_keeps_same_run_pending_instead_of_generating_again():
    from app.services.smart_insights.public_research_publisher import PublicResearchPublisher
    class Reports:
        def list_pending_deep(self, **kwargs):
            return [dict(asset_key='crypto:BTC/USDT', effective_date='2026-10-05', source_run_id='existing')]
        def mark_failed(self, **kwargs):
            raise AssertionError('a transport outage must not fail the generation')
    class Trading:
        def get_run_for_worker(self, **kwargs):
            return {'status': 'succeeded', 'user_id': 42}
    def unavailable(**kwargs):
        raise RuntimeError('temporary artifact outage')
    publisher = PublicResearchPublisher(reports=Reports(), trading_repository=Trading(),
        fetch_artifact=unavailable, system_user_id=lambda: 42)
    assert publisher.sync_pending_deep_reports() == {'published': 0, 'failed': 0, 'pending': 1}


def test_evidence_only_snapshot_contains_no_synthetic_confidence():
    from app.services.smart_insights.snapshot_pipeline import build_snapshot_draft
    from tests.test_smart_insights_snapshot_pipeline import _evidence, AS_OF
    draft = build_snapshot_draft([_evidence('obs-a', metric='price'), _evidence('obs-b', metric='volume')],
        market='crypto', mode='live', as_of=AS_OF, include_opinions=False)
    assert draft.status == 'COMPLETE'
    assert draft.opinions == ()
    assert draft.methodology_version == 'datavest-evidence-snapshot-v2'


@pytest.mark.parametrize('public', [True, False])
def test_repository_claim_cooldown_limit_and_active_run_guard(public, monkeypatch):
    """Execute real claim predicates in SQLite with PostgreSQL cast/time adapters.

    This verifies state transitions, bindings and deduplication, not PostgreSQL
    concurrency; that remains a release-time check against the migrated DB.
    """
    import re
    import sqlite3
    from contextlib import contextmanager
    from app.services.smart_insights import public_reports, shared_reports
    module = public_reports if public else shared_reports
    table = 'public_research_reports' if public else 'shared_watchlist_research_reports'
    period_column = 'effective_date' if public else 'period_key'
    connection = sqlite3.connect(':memory:')
    connection.row_factory = sqlite3.Row
    connection.execute(f'''CREATE TABLE {table} (id INTEGER PRIMARY KEY,
        asset_key TEXT, report_kind TEXT, locale TEXT, {period_column} TEXT,
        status TEXT, payload_json TEXT, failure_code TEXT, source_run_id TEXT,
        generated_at TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        attempt_count INTEGER DEFAULT 1, UNIQUE(asset_key, report_kind, locale, {period_column}))''')
    class Cursor:
        def __init__(self):
            self.cursor = connection.cursor()
        def execute(self, sql, params):
            sql = re.sub(r"NOW\(\) - INTERVAL '([^']+)'", r"datetime('now', '-\1')", sql)
            self.cursor.execute(sql.replace('::jsonb', '').replace('NOW()', 'CURRENT_TIMESTAMP'), params)
        def fetchone(self):
            return self.cursor.fetchone()
        def close(self):
            self.cursor.close()
    class DB:
        def cursor(self):
            return Cursor()
        def commit(self):
            connection.commit()
    @contextmanager
    def db():
        yield DB()
    monkeypatch.setattr(module, 'get_db_connection', db)
    repo = module.PublicResearchReportsRepository() if public else module.SharedResearchReportsRepository()
    args = dict(asset_key='crypto:BTC/USDT', report_kind='deep', locale='vi-VN', **{period_column: '2026-10-05'})
    assert repo.claim_pending(**args)
    assert not repo.claim_pending(**args)
    assert repo.set_source_run(**args, source_run_id='original')
    assert not repo.set_source_run(**args, source_run_id='duplicate')
    connection.execute(f"UPDATE {table} SET updated_at=datetime('now','-4 hours')")
    assert not repo.claim_pending(**args)  # never reclaim an active run
    repo.mark_failed(**args, failure_code='trading_agents_failed', source_run_id='original')
    assert not repo.claim_pending(**args)  # cooldown
    for attempt in (2, 3):
        connection.execute(f"UPDATE {table} SET updated_at=datetime('now','-4 hours')")
        assert repo.claim_pending(**args)
        assert connection.execute(f'SELECT attempt_count FROM {table}').fetchone()[0] == attempt
        repo.set_source_run(**args, source_run_id=f'run-{attempt}')
        # A delayed response from the original worker must not overwrite it.
        repo.mark_failed(**args, failure_code='trading_agents_failed', source_run_id='original')
        assert connection.execute(f'SELECT status FROM {table}').fetchone()[0] == 'pending'
        repo.mark_failed(**args, failure_code='trading_agents_failed', source_run_id=f'run-{attempt}')
    connection.execute(f"UPDATE {table} SET updated_at=datetime('now','-4 hours')")
    assert not repo.claim_pending(**args)
    other = {**args, 'asset_key': 'crypto:ETH/USDT'}
    assert repo.claim_pending(**other)
    connection.execute(f"UPDATE {table} SET updated_at=datetime('now','-4 hours') WHERE source_run_id IS NULL")
    assert repo.claim_pending(**other)  # abandoned pre-generation dispatch
    connection.close()
