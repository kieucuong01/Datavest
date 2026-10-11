from datetime import datetime, timezone
from types import SimpleNamespace
import pytest
from tests.test_portfolio_ledger_repository import repository
from app.services.portfolio.books import BooksService
from app.services.portfolio.history import PortfolioHistoryService, refresh_due_books

def setup_book(repo):
    svc = BooksService(repo, clock=lambda: datetime(2026,10,6,tzinfo=timezone.utc))
    book = svc.create(1, {'name':'Test','currency':'VND'})
    svc.append(1,book['id'],{'events':[{'type':'deposit','amount':'100','effectiveAt':'2026-10-01T00:00:00Z'}], 'expectedRevision':0,'requestKey':'fund'})
    return svc, book

def test_cash_history_revision_and_current_day_bounds(repository):
    svc, book = setup_book(repository)
    history = PortfolioHistoryService(repository, clock=lambda:datetime(2026,10,6,tzinfo=timezone.utc))
    assert len(history.refresh(1,book['id'],'2026-10-01','2026-10-03')['points']) == 3
    assert history.history(1,book['id'],'2026-10-01','2026-10-03')['points'][-1]['nav'] == '100'
    svc.append(1,book['id'],{'events':[{'type':'deposit','amount':'10','effectiveAt':'2026-10-02T00:00:00Z'}], 'expectedRevision':1,'requestKey':'fund2'})
    carried = history.history(1,book['id'],'2026-10-01','2026-10-03')['points']
    assert len(carried) == 1 and carried[0]['ledgerRevision'] == 2 and carried[0]['derivedFromRevision'] == 1
    old = history.history(1,book['id'],'2026-10-01','2026-10-03',revision=1)
    assert old['superseded'] and len(old['points']) == 3
    with pytest.raises(ValueError): history.refresh(1,book['id'],'2026-10-01','2026-10-06')
    with pytest.raises(ValueError): history.refresh(1,book['id'],'2020-01-01','2026-10-05')
    with pytest.raises(LookupError): history.history(2,book['id'],'2026-10-01','2026-10-03')

def test_revision_changed_during_fetch_is_not_saved(repository):
    svc, book = setup_book(repository)
    svc.append(1,book['id'],{'events':[{'type':'buy','market':'VNStock','symbol':'FPT','quantity':'1','unitPrice':'10','effectiveAt':'2026-10-01T01:00:00Z'}], 'expectedRevision':1,'requestKey':'buy'})
    class Gateway:
        def fetch_daily(self, *args, **kwargs):
            svc.append(1,book['id'],{'events':[{'type':'deposit','amount':'10','effectiveAt':'2026-10-02T00:00:00Z'}], 'expectedRevision':2,'requestKey':'changed'})
            return SimpleNamespace(timestamps=(1790899200,),closes=(10,),provider='fixture',checksum='hash',price_mode='raw',mark_to_market_supported=True,quality_flags=())
    history = PortfolioHistoryService(repository, gateway=Gateway(), clock=lambda:datetime(2026,10,6,tzinfo=timezone.utc))
    with pytest.raises(ValueError, match='revision'): history.refresh(1,book['id'],'2026-10-01','2026-10-02')

def test_monitor_tick_claims_one_day_per_book(repository):
    _, book = setup_book(repository)
    svc = PortfolioHistoryService(repository, clock=lambda:datetime(2026,10,6,tzinfo=timezone.utc))
    assert refresh_due_books(service=svc,limit=20) == 1
    assert len(svc.history(1,book['id'],'2026-10-01','2026-10-05')['points']) == 1

def test_missing_provider_can_recover_without_erasing_evidence(repository):
    svc, book = setup_book(repository)
    svc.append(1,book['id'],{'events':[{'type':'buy','market':'VNStock','symbol':'FPT','quantity':'1','unitPrice':'10','effectiveAt':'2026-10-01T01:00:00Z'}], 'expectedRevision':1,'requestKey':'buy'})
    class Gateway:
        working = False
        def fetch_daily(self,*args,**kwargs):
            if not self.working: raise ValueError('offline')
            return SimpleNamespace(timestamps=(int(datetime(2026,10,1,tzinfo=timezone.utc).timestamp()),),closes=(11,),provider='fixture',checksum='hash',price_mode='raw',mark_to_market_supported=True,quality_flags=())
    gateway = Gateway()
    history = PortfolioHistoryService(repository,gateway=gateway,clock=lambda:datetime(2026,10,6,tzinfo=timezone.utc))
    assert history.refresh(1,book['id'],'2026-10-01','2026-10-01')['points'][0]['nav'] is None
    gateway.working = True
    assert history.refresh(1,book['id'],'2026-10-01','2026-10-01')['points'][0]['nav'] == '101'
    with repository.connection() as db:
        cur = db.cursor(); cur.execute('SELECT snapshot_json FROM qd_portfolio_nav_evidence WHERE book_id=?',(book['id'],))
        assert len(cur.fetchall()) == 2

def test_closed_weekend_quote_is_valid_but_missing_weekday_is_stale():
    series = SimpleNamespace(timestamps=(int(datetime(2026,10,2,tzinfo=timezone.utc).timestamp()),),closes=(11,),provider='fixture',checksum='hash',price_mode='raw',mark_to_market_supported=True,quality_flags=())
    quote = PortfolioHistoryService.quote(series,'VNStock',datetime(2026,10,4).date(),datetime(2026,10,4,16,59,tzinfo=timezone.utc))
    assert quote['status'] == 'PREVIOUS_CLOSE' and quote['tradeDate'] == '2026-10-02'
    quote = PortfolioHistoryService.quote(series,'VNStock',datetime(2026,10,5).date(),datetime(2026,10,5,16,59,tzinfo=timezone.utc))
    assert quote['status'] == 'STALE'

def test_worker_retries_missing_dates_without_blocking_newer_days(repository):
    svc, book = setup_book(repository)
    svc.append(1,book['id'],{'events':[{'type':'buy','market':'VNStock','symbol':'FPT','quantity':'1','unitPrice':'10','effectiveAt':'2026-10-01T01:00:00Z'}], 'expectedRevision':1,'requestKey':'buy'})
    class Gateway:
        working = False
        def fetch_daily(self,*args,**kwargs):
            if not self.working: raise ValueError('offline')
            return SimpleNamespace(timestamps=tuple(int(datetime(2026,10,d,tzinfo=timezone.utc).timestamp()) for d in (1,2,5)),closes=(11,12,13),provider='fixture',checksum='hash',price_mode='raw',mark_to_market_supported=True,quality_flags=())
    gateway = Gateway(); now = datetime(2026,10,6,tzinfo=timezone.utc)
    history = PortfolioHistoryService(repository,gateway=gateway,clock=lambda:now)
    for tick in range(5):
        now = datetime(2026,10,6,0,tick,tzinfo=timezone.utc)
        refresh_due_books(service=history)
    assert len(history.history(1,book['id'],'2026-10-01','2026-10-05')['points']) == 5
    gateway.working = True
    for tick in range(5,25):
        now = datetime(2026,10,6,0,tick,tzinfo=timezone.utc)
        refresh_due_books(service=history)
    points = history.history(1,book['id'],'2026-10-01','2026-10-05')['points']
    assert points[0]['nav'] == '101' and points[-1]['nav'] == '103'
    with repository.connection() as db:
        cur = db.cursor(); cur.execute('SELECT COUNT(*) AS n FROM qd_portfolio_nav_evidence WHERE book_id=? AND day=?',(book['id'],'2026-10-01'))
        assert cur.fetchone()['n'] == 2

def test_carried_incomplete_date_keeps_retry_in_new_revision(repository):
    svc, book = setup_book(repository)
    svc.append(1,book['id'],{'events':[{'type':'buy','market':'VNStock','symbol':'FPT','quantity':'1','unitPrice':'10','effectiveAt':'2026-10-01T01:00:00Z'}], 'expectedRevision':1,'requestKey':'buy'})
    class Gateway:
        working = False
        def fetch_daily(self,*args,**kwargs):
            if not self.working: raise ValueError('offline')
            return SimpleNamespace(timestamps=(int(datetime(2026,10,1,tzinfo=timezone.utc).timestamp()),),closes=(11,),provider='fixture',checksum='hash',price_mode='raw',mark_to_market_supported=True,quality_flags=())
    gateway = Gateway(); history = PortfolioHistoryService(repository,gateway=gateway,clock=lambda:datetime(2026,10,6,tzinfo=timezone.utc))
    history.refresh(1,book['id'],'2026-10-01','2026-10-01')
    svc.append(1,book['id'],{'events':[{'type':'deposit','amount':'10','effectiveAt':'2026-10-03T00:00:00Z'}], 'expectedRevision':2,'requestKey':'later'})
    gateway.working = True
    refresh_due_books(service=history)
    assert history.history(1,book['id'],'2026-10-01','2026-10-01')['points'][0]['nav'] == '101'

def test_worker_defers_idle_book_so_retry_books_are_not_starved(repository):
    _, book = setup_book(repository)
    now = datetime(2026,10,6,tzinfo=timezone.utc)
    history = PortfolioHistoryService(repository,clock=lambda:now)
    history.refresh(1,book['id'],'2026-10-01','2026-10-05')
    assert refresh_due_books(service=history) == 0
    with repository.connection() as db:
        cur = db.cursor(); cur.execute('SELECT next_due FROM qd_portfolio_nav_jobs WHERE book_id=?',(book['id'],))
        assert cur.fetchone()['next_due'] > now.isoformat()
