import sqlite3
from contextlib import contextmanager
from pathlib import Path
import pytest
from app.services.portfolio.ledger_repository import LedgerRepository, BookConflict, BookNotFound
from app.services.portfolio.books import BooksService
from datetime import datetime, timezone
NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)

class Cursor:
    def __init__(self, conn): self.c = conn.cursor()
    def execute(self, sql, args=()):
        self.c.execute(sql.replace(' FOR UPDATE', ''), args)
        return self
    def fetchone(self):
        row = self.c.fetchone()
        return dict(row) if row else None
    def fetchall(self): return [dict(row) for row in self.c.fetchall()]
    def close(self): self.c.close()
class DB:
    def __init__(self, conn): self.conn = conn
    def cursor(self): return Cursor(self.conn)
    def commit(self): self.conn.commit()
    def rollback(self): self.conn.rollback()

@pytest.fixture
def repository():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    sql = (Path(__file__).parents[1] / 'migrations/20261005_portfolio_ledger.sql').read_text()
    sql = sql.replace('TIMESTAMPTZ', 'TEXT').replace('BIGSERIAL PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT').replace('REFERENCES qd_users(id)', '')
    conn.executescript(sql)
    for name in ('20261005_portfolio_nav.sql', '20261005_portfolio_selective_alerts.sql'):
        path = Path(__file__).parents[1] / 'migrations' / name
        if path.exists(): conn.executescript(path.read_text().replace('TIMESTAMPTZ','TEXT').replace('BIGSERIAL PRIMARY KEY','INTEGER PRIMARY KEY AUTOINCREMENT').replace('REFERENCES qd_users(id)',''))
    @contextmanager
    def connection():
        try: yield DB(conn)
        except Exception:
            conn.rollback()
            raise
    repo = LedgerRepository(connection)
    yield repo
    conn.close()

def test_owner_idempotency_revision_replay(repository):
    svc = BooksService(repository, clock=lambda: NOW)
    book = svc.create(1, {'name': 'HOSE', 'currency': 'VND'})
    payload = {'expectedRevision': 0, 'requestKey': 'deposit-1', 'events': [{'type': 'deposit', 'amount': '100', 'effectiveAt': '2026-10-01T00:00:00Z'}]}
    assert svc.append(1, book['id'], payload)['revision'] == 1
    assert svc.append(1, book['id'], payload)['revision'] == 1
    with pytest.raises(BookConflict): svc.append(1, book['id'], {**payload, 'events': [{**payload['events'][0], 'amount': '200'}]})
    with pytest.raises(BookNotFound): svc.state(2, book['id'])
    with pytest.raises(BookNotFound): svc.append(2, book['id'], payload)
    assert repository.list_owned(2) == []
    trade = {'type': 'buy', 'market': 'VNStock', 'symbol': 'FPT', 'quantity': '1', 'unitPrice': '90', 'effectiveAt': '2026-10-02T00:00:00Z'}
    svc.append(1, book['id'], {'expectedRevision': 1, 'requestKey': 'buy', 'events': [trade]})
    event_id = svc.state(1, book['id'])['events'][0]['eventId']
    with pytest.raises(ValueError): svc.revise(1, book['id'], event_id, {'expectedRevision': 2, 'requestKey': 'cancel', 'cancelled': True})
    assert svc.state(1, book['id'])['revision'] == 2
    assert repository.revisions(1, book['id'], event_id)[0]['revision'] == 1

def test_csv_preview_atomic_and_repeated_ids(repository):
    svc = BooksService(repository, clock=lambda: NOW)
    book = svc.create(1, {'name': 'Test', 'currency': 'VND'})
    csv = 'eventId,type,effectiveAt,amount\n11111111-1111-4111-8111-111111111111,deposit,2026-10-01T00:00:00Z,100\n'
    assert svc.csv_preview(1, book['id'], {'csv': csv})['valid']
    svc.csv_commit(1, book['id'], {'csv': csv, 'expectedRevision': 0, 'requestKey': 'csv'})
    assert svc.csv_commit(1, book['id'], {'csv': csv, 'expectedRevision': 0, 'requestKey': 'csv'})['replayedRequest']
    with pytest.raises(ValueError): svc.csv_commit(1, book['id'], {'csv': csv, 'expectedRevision': 1, 'requestKey': 'csv2'})
    invalid = csv + ',withdraw,2026-10-02T00:00:00Z,1000\n'
    assert not svc.csv_preview(1, book['id'], {'csv': invalid})['valid']
    assert svc.state(1, book['id'])['state']['cash'] == '100'

def test_edit_old_buy_cannot_oversell_later(repository):
    svc = BooksService(repository, clock=lambda: NOW)
    book = svc.create(1, {'name':'Test', 'currency':'VND'})
    rows = [{'type':'deposit', 'amount':'1000', 'effectiveAt':'2026-10-01T00:00:00Z'}, {'type':'buy', 'market':'VNStock', 'symbol':'FPT', 'quantity':'10', 'unitPrice':'10', 'effectiveAt':'2026-10-02T00:00:00Z'}, {'type':'sell', 'market':'VNStock', 'symbol':'FPT', 'quantity':'5', 'unitPrice':'12', 'effectiveAt':'2026-10-03T00:00:00Z'}]
    svc.append(1, book['id'], {'events':rows, 'requestKey':'batch', 'expectedRevision':0})
    event_id = svc.state(1, book['id'])['events'][1]['eventId']
    with pytest.raises(ValueError, match='Sale exceeds'):
        svc.revise(1, book['id'], event_id, {'event':{**rows[1], 'quantity':'1'}, 'expectedRevision':1, 'requestKey':'edit'})
    assert svc.state(1, book['id'])['state']['positions'][0]['quantity'] == '5'

def test_opening_preview_source_changed_conflict(repository, monkeypatch):
    svc = BooksService(repository, clock=lambda: NOW)
    book = svc.create(1, {'name':'Test', 'currency':'VND'})
    rows = [{'id':4, 'market':'VNStock', 'symbol':'FPT', 'side':'long', 'quantity':'10', 'entry_price':'12'}]
    monkeypatch.setattr(repository, 'opening_positions', lambda uid, ids: rows)
    payload = {'positionIds':[4], 'cash':'100', 'effectiveAt':'2026-10-01T00:00:00Z', 'expectedRevision':0, 'requestKey':'opening'}
    preview = svc.opening_preview(1, book['id'], payload)
    rows[0]['quantity'] = '11'
    with pytest.raises(BookConflict): svc.opening_commit(1, book['id'], {**payload, 'fingerprint':preview['fingerprint']})
    assert svc.state(1, book['id'])['revision'] == 0

def test_opening_retry_replays_before_mutable_source_validation(repository, monkeypatch):
    svc = BooksService(repository, clock=lambda: NOW)
    book = svc.create(1, {'name':'Test', 'currency':'VND'})
    rows = [{'id':4, 'market':'VNStock', 'symbol':'FPT', 'side':'long', 'quantity':'10', 'entry_price':'12'}]
    monkeypatch.setattr(repository, 'opening_positions', lambda uid, ids: rows)
    payload = {'positionIds':[4], 'cash':'100', 'effectiveAt':'2026-10-01T00:00:00Z', 'expectedRevision':0, 'requestKey':'opening'}
    payload['fingerprint'] = svc.opening_preview(1, book['id'], payload)['fingerprint']
    assert svc.opening_commit(1, book['id'], payload)['revision'] == 1
    rows.clear()
    assert svc.opening_commit(1, book['id'], payload)['replayedRequest']
    with pytest.raises(BookConflict): svc.opening_commit(1, book['id'], {**payload,'cash':'200'})
    with pytest.raises(BookNotFound): svc.opening_commit(2, book['id'], payload)
    assert svc.state(1, book['id'])['revision'] == 1

def test_cancel_retry_after_restoring_event_replays_original_command(repository):
    svc = BooksService(repository, clock=lambda: NOW)
    book = svc.create(1, {'name':'Test','currency':'VND'})
    event = {'type':'deposit','amount':'100','effectiveAt':'2026-10-01T00:00:00Z'}
    svc.append(1, book['id'], {'events':[event],'expectedRevision':0,'requestKey':'fund'})
    event_id = svc.state(1,book['id'])['events'][0]['eventId']
    payload = {'cancelled':True,'expectedRevision':1,'requestKey':'cancel'}
    svc.revise(1,book['id'],event_id,payload)
    svc.revise(1,book['id'],event_id,{'event':{**event,'amount':'200'},'expectedRevision':2,'requestKey':'restore'})
    assert svc.revise(1,book['id'],event_id,payload)['revision'] == 2
    assert svc.state(1,book['id'])['state']['cash'] == '200'
