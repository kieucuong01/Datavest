import importlib.util
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest


@pytest.mark.parametrize('public', [True, False])
def test_previous_report_is_completed_same_asset_kind_locale_and_strictly_earlier(public, monkeypatch):
    from app.services.smart_insights import public_reports, shared_reports
    module = public_reports if public else shared_reports
    table = 'public_research_reports' if public else 'shared_watchlist_research_reports'
    period = 'effective_date' if public else 'period_key'
    connection = sqlite3.connect(':memory:')
    connection.row_factory = sqlite3.Row
    connection.execute(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY, asset_key TEXT, report_kind TEXT, locale TEXT, {period} TEXT, status TEXT, payload_json TEXT, generated_at TEXT)')
    for asset, kind, locale, day, status in [
        ('crypto:BTC/USDT', 'deep', 'vi-VN', '2026-09-21', 'complete'),
        ('crypto:BTC/USDT', 'deep', 'vi-VN', '2026-09-28', 'complete'),
        ('crypto:BTC/USDT', 'deep', 'vi-VN', '2026-10-01', 'failed'),
        ('crypto:BTC/USDT', 'deep', 'en-US', '2026-10-02', 'complete'),
        ('crypto:BTC/USDT', 'quick', 'vi-VN', '2026-10-03', 'complete'),
        ('crypto:SOL/USDT', 'deep', 'vi-VN', '2026-10-04', 'complete'),
        ('crypto:BTC/USDT', 'deep', 'vi-VN', '2026-10-05', 'complete'),
        ('crypto:BTC/USDT', 'deep', 'vi-VN', '2026-10-12', 'complete'),
    ]:
        connection.execute(f'INSERT INTO {table} (asset_key, report_kind, locale, {period}, status) VALUES (?,?,?,?,?)', (asset, kind, locale, day, status))
    @contextmanager
    def db():
        yield connection
    monkeypatch.setattr(module, 'get_db_connection', db)
    repo = module.PublicResearchReportsRepository() if public else module.SharedResearchReportsRepository()
    row = repo.previous_completed(asset_key='crypto:BTC/USDT', report_kind='deep', locale='vi-VN', before_date='2026-10-05')
    assert row[period] == '2026-09-28'
    assert repo.previous_completed(asset_key='crypto:BTC/USDT', report_kind='deep', locale='vi-VN', before_date='2026-09-21') is None


def test_portfolio_brief_is_rendered_in_the_same_native_decision_call(monkeypatch):
    schema_path = Path(__file__).resolve().parents[2] / 'third_party/tradingagents/tradingagents/agents/schemas.py'
    spec = importlib.util.spec_from_file_location('decision_brief_schemas', schema_path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    decision = module.PortfolioDecision(rating='Hold', executive_summary='Wait for disclosure.', investment_thesis='Limited evidence.',
                                       supporting_evidence=['Revenue grew, FY2025, source: filing'],
                                       counter_evidence=['Cash flow lagged earnings.'], key_risks=['Valuation risk.'],
                                       invalidation_conditions=['Reassess if quarterly revenue falls.'], next_watch=['Next filing.'])
    rendered = module.render_pm_decision(decision)
    assert '### Supporting Evidence\n- Revenue grew, FY2025, source: filing' in rendered
    assert '### Invalidation Conditions\n- Reassess if quarterly revenue falls.' in rendered
    legacy = module.PortfolioDecision(rating='Hold', executive_summary='Wait.', investment_thesis='No verified data.')
    assert 'Invalidation Conditions' not in module.render_pm_decision(legacy)


def test_previous_and_dated_reads_recheck_current_watchlist_membership():
    from datetime import date
    from app.services.smart_insights.shared_research_access import SharedResearchAccessService
    class Repository:
        calls = []
        def previous_completed(self, **kwargs):
            self.calls.append(kwargs)
            return {'asset_key': 'vnstock:FPT', 'period_key': '2026-09-28', 'report_kind': 'deep',
                    'locale': 'vi-VN', 'status': 'complete', 'payload': {'body': 'same asset prior report', 'userId': 9}}
        def current(self, **kwargs):
            self.calls.append(kwargs)
            return {'asset_key': 'vnstock:FPT', 'period_key': kwargs['period_key'], 'report_kind': 'deep',
                    'status': 'complete', 'payload': {'body': 'date-pinned report'}}
    watching = {7}
    repository = Repository()
    service = SharedResearchAccessService(watchlist_loader=lambda user: [{'market': 'VNStock', 'symbol': 'FPT'}] if user in watching else [],
                                          shared_repository=repository)
    previous = service.previous_report(user_id=7, asset_key='vnstock:FPT', before_date=date(2026, 10, 5))
    assert previous['effectiveDate'] == '2026-09-28' and 'userId' not in previous
    assert service.report_for_date(user_id=7, asset_key='vnstock:FPT', effective_date=date(2026, 9, 28))['body'] == 'date-pinned report'
    count = len(repository.calls)
    watching.clear()
    for user in (7, 8):
        with pytest.raises(ValueError, match='shared_report_not_found'):
            service.previous_report(user_id=user, asset_key='vnstock:FPT', before_date=date(2026, 10, 5))
        with pytest.raises(ValueError, match='shared_report_not_found'):
            service.report_for_date(user_id=user, asset_key='vnstock:FPT', effective_date=date(2026, 9, 28))
    assert len(repository.calls) == count


def test_guest_previous_route_keeps_fixed_public_scope(monkeypatch):
    from flask import Flask
    from app.routes import smart_insights as routes
    calls = []
    monkeypatch.setattr(routes.PublicResearchReportsService, '__init__', lambda self: setattr(self, 'repository', type('Repository', (), {
        'previous_completed': lambda self, **kwargs: calls.append(kwargs) or None
    })()))
    app = Flask(__name__)
    app.register_blueprint(routes.smart_insights_blp, url_prefix='/api/smart-insights')
    client = app.test_client()
    assert client.get('/api/smart-insights/public/reports/vnstock:FPT/deep/previous?date=2026-10-05').status_code == 404
    assert not calls
    assert client.get('/api/smart-insights/public/reports/crypto:BTC%2FUSDT/deep/previous').status_code == 400
    result = client.get('/api/smart-insights/public/reports/crypto:BTC%2FUSDT/deep/previous?date=2026-10-05')
    assert result.status_code == 200 and result.get_json()['data'] is None
    assert calls == [{'asset_key': 'crypto:BTC/USDT', 'report_kind': 'deep', 'locale': 'vi-VN', 'before_date': '2026-10-05'}]
    assert client.get('/api/smart-insights/research/reports/vnstock:FPT/deep/previous?date=2026-10-05').status_code == 401


@pytest.mark.parametrize('summary', [False, True])
def test_shared_pdf_renders_the_requested_period_not_newest(summary, monkeypatch):
    from inspect import unwrap
    from datetime import date
    from flask import Flask, g
    from app.routes import smart_insights as routes
    calls, rendered = [], []
    class Service:
        def resolve_asset(self, user, key):
            assert user == 7 and key == 'vnstock:FPT'
            return 'watchlist_shared', {'market': 'VNStock', 'symbol': 'FPT'}
        def report_for_date(self, **kwargs):
            calls.append(kwargs)
            return {'effectiveDate': '2026-09-28', 'body': 'displayed prior period'}
        def state(self, **kwargs):
            raise AssertionError('Must not substitute latest period')
    monkeypatch.setattr(routes, '_shared_research', Service)
    builder = 'build_trading_agents_summary_pdf' if summary else 'build_trading_agents_report_pdf'
    monkeypatch.setattr(routes, builder, lambda **kwargs: rendered.append(kwargs) or b'%PDF-1.4 fixture')
    app = Flask(__name__)
    view = routes.shared_deep_summary_pdf if summary else routes.shared_deep_report_pdf
    with app.test_request_context('/?date=2026-09-28'):
        g.user_id = 7
        response = unwrap(view)('vnstock:FPT')
    assert response.status_code == 200
    assert calls == [{'user_id': 7, 'asset_key': 'vnstock:FPT', 'effective_date': date(2026, 9, 28)}]
    assert rendered[0]['content'] == 'displayed prior period'
    assert rendered[0]['analysis_date'] == '2026-09-28'
