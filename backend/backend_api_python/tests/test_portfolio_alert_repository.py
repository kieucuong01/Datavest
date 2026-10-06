from datetime import datetime, timedelta, timezone
from tests.test_portfolio_ledger_repository import repository
from tests.test_portfolio_selective_alerts import snapshot
from app.services.portfolio.alert_repository import AlertRepository
from app.services.portfolio.books import BooksService
import pytest
NOW=datetime(2026,10,6,tzinfo=timezone.utc)

def setup(repo):
    with repo.connection() as db:
        db.conn.executescript('CREATE TABLE qd_strategy_notifications(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,strategy_id INTEGER,symbol TEXT,signal_type TEXT,channels TEXT,title TEXT,message TEXT,payload_json TEXT,is_read INTEGER DEFAULT 0,created_at TEXT); CREATE TABLE qd_strategies_trading(id INTEGER,user_id INTEGER);')
    book=BooksService(repo).create(1,{'name':'A','currency':'VND'})
    alerts=AlertRepository(repo)
    alerts.save_preferences(1,book['id'],{'enabled':True},NOW)
    return book,alerts

def test_baseline_restart_dedupe_recovery_new_episode_and_digest(repository):
    book,repo=setup(repository)
    assert repo.evaluate(1,book['id'],{'asOf':NOW.isoformat(),'snapshot':snapshot('40')},NOW)==0
    assert repo.evaluate(1,book['id'],{'asOf':NOW.isoformat(),'snapshot':snapshot('60')},NOW+timedelta(hours=1))==1
    restarted=AlertRepository(repository)
    assert restarted.evaluate(1,book['id'],{'asOf':NOW.isoformat(),'snapshot':snapshot('60')},NOW+timedelta(hours=2))==0
    assert restarted.emit_due_digest(1,NOW+timedelta(hours=2))==0
    assert restarted.emit_due_digest(1,NOW+timedelta(hours=25))==1
    assert restarted.emit_due_digest(1,NOW+timedelta(hours=25))==0
    assert restarted.evaluate(1,book['id'],{'asOf':NOW.isoformat(),'snapshot':snapshot('40')},NOW+timedelta(hours=26))==1
    assert restarted.evaluate(1,book['id'],{'asOf':NOW.isoformat(),'snapshot':snapshot('60')},NOW+timedelta(hours=27))==1
    assert restarted.emit_due_digest(1,NOW+timedelta(hours=50))==1
    with repository.connection() as db:
        cur=db.cursor();cur.execute('SELECT * FROM qd_strategy_notifications')
        rows=cur.fetchall();assert len(rows)==2 and all(row['channels']=='in_app' and row['strategy_id'] is None and row['user_id']==1 for row in rows)

def test_disable_cancels_pending_owner_cannot_override(repository):
    book,repo=setup(repository)
    repo.evaluate(1,book['id'],{'snapshot':snapshot('40')},NOW)
    repo.evaluate(1,book['id'],{'snapshot':snapshot('60')},NOW+timedelta(hours=1))
    with pytest.raises(LookupError): repo.preferences(2,book['id'])
    with pytest.raises(LookupError): repo.save_preferences(2,book['id'],{'enabled':True},NOW)
    repo.save_preferences(1,book['id'],{'enabled':False},NOW+timedelta(hours=2))
    assert repo.emit_due_digest(1,NOW+timedelta(hours=30))==0
    assert repo.preferences(1,book['id'])['enabled'] is False

def test_notification_read_and_mark_read_are_owner_scoped(repository,monkeypatch):
    from flask import Flask
    import app.utils.auth as auth
    import app.routes.strategy_notifications as routes
    book,alerts=setup(repository)
    alerts.evaluate(1,book['id'],{'snapshot':snapshot('40')},NOW)
    alerts.evaluate(1,book['id'],{'snapshot':snapshot('60')},NOW+timedelta(hours=1))
    alerts.emit_due_digest(1,NOW+timedelta(hours=25))
    monkeypatch.setattr(routes,'get_db_connection',repository.connection)
    monkeypatch.setattr(auth,'verify_token',lambda token:{'user_id':int(token),'_verified_user_role':'user','_verified_username':'test'})
    app=Flask(__name__);app.register_blueprint(routes.strategy_blp,url_prefix='/api');client=app.test_client()
    headers={'Authorization':'Bearer 2'}
    assert client.get('/api/strategies/notifications',headers=headers).json['data']['items']==[]
    assert client.post('/api/strategies/notifications/read',headers=headers,json={'id':1}).status_code==200
    rows=client.get('/api/strategies/notifications',headers={'Authorization':'Bearer 1'}).json['data']['items']
    assert len(rows)==1 and rows[0]['is_read']==0
    client.post('/api/strategies/notifications/read',headers={'Authorization':'Bearer 1'},json={'id':1})
    with repository.connection() as db:
        cur=db.cursor();cur.execute('SELECT is_read FROM qd_strategy_notifications WHERE id=1');assert cur.fetchone()['is_read']==1

def test_two_workers_emit_one_digest(repository,tmp_path):
    import sqlite3
    from contextlib import contextmanager
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from tests.test_portfolio_ledger_repository import DB
    from app.services.portfolio.ledger_repository import LedgerRepository
    book,alerts=setup(repository)
    alerts.evaluate(1,book['id'],{'snapshot':snapshot('40')},NOW)
    alerts.evaluate(1,book['id'],{'snapshot':snapshot('60')},NOW+timedelta(hours=1))
    path=str(tmp_path/'concurrent.db')
    with repository.connection() as db:
        target=sqlite3.connect(path);db.conn.backup(target);target.close()
    @contextmanager
    def connection():
        conn=sqlite3.connect(path,timeout=10);conn.row_factory=sqlite3.Row
        conn.execute('BEGIN IMMEDIATE')
        try: yield DB(conn)
        except Exception: conn.rollback();raise
        finally: conn.close()
    repo=AlertRepository(LedgerRepository(connection));barrier=Barrier(2)
    def emit(): barrier.wait();return repo.emit_due_digest(1,NOW+timedelta(hours=25))
    with ThreadPoolExecutor(2) as pool:
        a,b=pool.submit(emit),pool.submit(emit);assert sorted([a.result(),b.result()])==[0,1]

def test_existing_monitor_hook_and_worker_restart(repository,monkeypatch):
    from app.services.portfolio.alert_sources import evaluate_due_alerts
    book,_=setup(repository)
    assert evaluate_due_alerts(repository=repository,source_reader=lambda *args:{'snapshot':snapshot('40')},clock=lambda:NOW)==1
    assert evaluate_due_alerts(repository=repository,source_reader=lambda *args:{'snapshot':snapshot('60')},clock=lambda:NOW+timedelta(hours=1))==1
    assert evaluate_due_alerts(repository=repository,source_reader=lambda *args:{'snapshot':snapshot('60')},clock=lambda:NOW+timedelta(hours=25))==1
    assert evaluate_due_alerts(repository=repository,source_reader=lambda *args:{'snapshot':snapshot('60')},clock=lambda:NOW+timedelta(hours=25))==0
    with repository.connection() as db:
        cur=db.cursor();cur.execute('SELECT id FROM qd_strategy_notifications');assert len(cur.fetchall())==1
    import app.services.portfolio_monitor as monitor
    import app.services.portfolio.history as history
    import app.services.portfolio.alert_sources as sources
    calls=[]
    monkeypatch.setattr(history,'refresh_due_books',lambda **kw:calls.append('nav'))
    monkeypatch.setattr(sources,'evaluate_due_alerts',lambda **kw:calls.append('alerts'))
    class ImmediateThread:
        def __init__(self,target,**kwargs): self.target=target
        def start(self): self.target()
    monkeypatch.setattr(monitor.threading,'Thread',ImmediateThread)
    monitor._tick_portfolio_books()
    assert calls==['nav','alerts']

def test_settings_change_keeps_other_pending_and_old_allocation_survives_data_gap(repository):
    book,alerts=setup(repository)
    alerts.evaluate(1,book['id'],{'snapshot':snapshot('40')},NOW)
    alerts.evaluate(1,book['id'],{'snapshot':snapshot('60')},NOW+timedelta(hours=1))
    alerts.evaluate(1,book['id'],{'snapshot':snapshot(nav=None,status='UNAVAILABLE')},NOW+timedelta(hours=2))
    assert alerts.evaluate(1,book['id'],{'snapshot':snapshot('40')},NOW+timedelta(hours=3))==2
    alerts.save_preferences(1,book['id'],{'digestHours':6},NOW+timedelta(hours=4))
    assert alerts.emit_due_digest(1,NOW+timedelta(hours=12))==1

def test_source_reader_uses_stored_owned_scope_and_preserves_future_cursor(repository):
    import json
    from app.services.portfolio.alert_sources import read_alert_sources
    book,alerts=setup(repository)
    alerts.save_preferences(1,book['id'],{'reports':False,'events':True},NOW-timedelta(days=2))
    with repository.connection() as db:
        db.conn.executescript('CREATE TABLE qd_watchlist(user_id INTEGER,market TEXT,symbol TEXT); CREATE TABLE qd_vietnam_events(id INTEGER,event_id TEXT,symbol TEXT,source TEXT,source_url TEXT,available_at TEXT,title TEXT);')
        cur=db.cursor()
        cur.execute('INSERT INTO qd_watchlist VALUES(1,?,?)',('VNStock','FPT'))
        cur.execute('INSERT INTO qd_watchlist VALUES(2,?,?)',('VNStock','VCB'))
        for n,symbol,at in [(1,'FPT',NOW-timedelta(days=1)),(2,'FPT',NOW+timedelta(days=1)),(3,'FPT',NOW),(4,'VCB',NOW)]:
            cur.execute('INSERT INTO qd_vietnam_events VALUES(?,?,?,?,?,?,?)',(n,str(n),symbol,'fixture','https://example.com/'+str(n),at.isoformat(),'Dividend'))
        cur.execute('SELECT * FROM qd_portfolio_alert_preferences WHERE book_id=?',(book['id'],));prefs=cur.fetchone()
        db.commit()
    current=read_alert_sources(repository,repository.load_owned(1,book['id']),prefs,NOW)
    assert {row['assetKey'] for row in current['events']}=={'vnstock:FPT'}
    assert current['eventCursor']==1
    assert len(current['events'])==2
