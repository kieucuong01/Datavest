from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4
import json
from .ledger import timestamp, fingerprint
from .ledger_repository import LedgerRepository, BookConflict
from .nav import build_nav_snapshot, performance_points, VN
from app.services.portfolio_optimizer.market_data import Instrument

class PortfolioHistoryService:
    def __init__(self, repository=None, gateway=None, clock=None):
        self.repo = repository or LedgerRepository()
        if gateway is None:
            from app.services.portfolio_optimizer.quantdinger_gateway import QuantDingerOptimizerGateway
            gateway = QuantDingerOptimizerGateway()
        self.gateway = gateway; self.clock = clock or (lambda: datetime.now(timezone.utc))
    def bounds(self, start_date=None, end_date=None):
        yesterday = self.clock().astimezone(VN).date() - timedelta(days=1)
        end = date.fromisoformat(end_date) if end_date else yesterday
        start = date.fromisoformat(start_date) if start_date else end - timedelta(days=89)
        if end > yesterday or start > end or (end-start).days >= 366: raise ValueError('Choose up to 366 completed calendar days')
        return start, end
    def history(self, user_id, book_id, start_date=None, end_date=None, revision=None):
        start, end = self.bounds(start_date, end_date)
        with self.repo.connection() as db:
            cur = db.cursor(); book = self.repo._owned(cur, user_id, book_id)
            selected_revision = book['revision'] if revision is None else int(revision)
            if not 0 <= selected_revision <= book['revision']: raise ValueError('Invalid history revision')
            cur.execute('SELECT snapshot_json FROM qd_portfolio_nav_snapshots WHERE book_id=? AND revision=? AND day>=? AND day<=? ORDER BY day', (book_id,selected_revision,start.isoformat(),end.isoformat()))
            points = [json.loads(row['snapshot_json']) for row in cur.fetchall()]; cur.close()
        if points:
            by_day = {point['day']:point for point in points}
            first,last = date.fromisoformat(points[0]['day']),date.fromisoformat(points[-1]['day'])
            points = [by_day.get((first+timedelta(days=n)).isoformat()) or {'day':(first+timedelta(days=n)).isoformat(),'cutoff':datetime.combine(first+timedelta(days=n),time.max,tzinfo=VN).isoformat(),'nav':None,'status':'UNAVAILABLE','externalFlows':[]} for n in range((last-first).days+1)]
        return {'revision': selected_revision, 'superseded':selected_revision != book['revision'], 'currency': book['currency'], 'points': performance_points(points), 'method': 'Modified Dietz estimate', 'dirtyFrom': book.get('dirty_from'), 'benchmarkKey': book.get('benchmark_key')}
    def refresh(self, user_id, book_id, start_date, end_date):
        start, end = self.bounds(start_date,end_date)
        book = self.repo.load_owned(user_id,book_id)
        if not book['events']: return {'points':[], 'revision':book['revision']}
        first = min(timestamp(row['effectiveAt']).astimezone(VN).date() for row in book['events'])
        start = max(start, first)
        if start > end: return {'points':[], 'revision':book['revision']}
        series = {}
        identities = {(r['market'],r['symbol']) for r in book['events'] if r.get('market') and not r.get('cancelled')}
        for market, symbol in identities:
            try:
                series[(market,symbol)] = self.gateway.fetch_daily(Instrument(market,symbol,book['currency'],market_type='spot' if market=='Crypto' else ''),start_date=(start-timedelta(days=10)).isoformat(),end_date=end.isoformat(),price_mode='raw')
            except Exception: series[(market,symbol)] = None
        points = []
        for offset in range((end-start).days+1):
            day = start + timedelta(days=offset)
            cutoff = datetime.combine(day,time.max,tzinfo=VN).astimezone(timezone.utc)
            quotes = {identity:self.quote(value,identity[0],day,cutoff) for identity,value in series.items()}
            points.append(build_nav_snapshot(book['events'],quotes,cutoff=cutoff,ledger_revision=book['revision']))
        with self.repo.connection() as db:
            cur = db.cursor(); current = self.repo._owned(cur,user_id,book_id,lock=True)
            if current['revision'] != book['revision']: raise BookConflict('Ledger revision changed during price fetch; retry')
            for point in points:
                args = (book_id,point['day'],book['revision'],json.dumps(point),self.clock().isoformat())
                cur.execute('INSERT INTO qd_portfolio_nav_evidence(book_id,day,revision,checksum,snapshot_json,created_at) VALUES(?,?,?,?,?,?) ON CONFLICT(book_id,day,revision,checksum) DO NOTHING', (book_id,point['day'],book['revision'],point['checksum'],json.dumps(point),self.clock().isoformat()))
                cur.execute('SELECT snapshot_json FROM qd_portfolio_nav_snapshots WHERE book_id=? AND day=? AND revision=?',(book_id,point['day'],book['revision']))
                prior = cur.fetchone()
                if prior and json.loads(prior['snapshot_json']).get('nav') is not None:
                    cur.execute('DELETE FROM qd_portfolio_nav_retries WHERE book_id=? AND day=? AND revision=?',(book_id,point['day'],book['revision']))
                    continue
                cur.execute('INSERT INTO qd_portfolio_nav_snapshots(book_id,day,revision,snapshot_json,created_at) VALUES(?,?,?,?,?) ON CONFLICT(book_id,day,revision) DO UPDATE SET snapshot_json=excluded.snapshot_json,created_at=excluded.created_at', args)
                if point['nav'] is None:
                    cur.execute('INSERT INTO qd_portfolio_nav_retries(book_id,day,revision,next_due) VALUES(?,?,?,?) ON CONFLICT(book_id,day,revision) DO UPDATE SET next_due=excluded.next_due', (book_id,point['day'],book['revision'],(self.clock()+timedelta(minutes=5)).isoformat()))
                else:
                    cur.execute('DELETE FROM qd_portfolio_nav_retries WHERE book_id=? AND day=? AND revision=?',(book_id,point['day'],book['revision']))
            if current.get('dirty_from') and start.isoformat() <= current['dirty_from'] <= end.isoformat():
                dirty = (end+timedelta(days=1)).isoformat()
                cur.execute('UPDATE qd_portfolio_books SET dirty_from=? WHERE id=? AND user_id=?', (dirty,book_id,user_id))
            db.commit(); cur.close()
        return self.history(user_id,book_id,start.isoformat(),end.isoformat())
    @staticmethod
    def quote(series, market, day, cutoff, allow_index=False):
        if series is None: return {'status':'UNAVAILABLE','reason':'provider_unavailable'}
        if series.price_mode != 'raw' or not series.mark_to_market_supported and not allow_index: return {'status':'UNAVAILABLE','reason':'raw_holding_prices_required'}
        # VN bars are session opens and complete by this local cutoff. UTC daily
        # crypto/gold bars must finish for 24h before they can contribute a close.
        rows = [(datetime.fromtimestamp(ts,timezone.utc),price) for ts,price in zip(series.timestamps,series.closes) if (ts <= cutoff.timestamp() if market=='VNStock' else ts+86400 <= cutoff.timestamp())]
        if not rows: return {'status':'UNAVAILABLE','reason':'no_completed_bar'}
        observed, price = max(rows,key=lambda row:row[0])
        trade_day = observed.astimezone(VN).date() if market=='VNStock' else observed.date()
        expected = day if market=='VNStock' else cutoff.date()-timedelta(days=1)
        if market != 'Crypto':
            while expected.weekday() >= 5: expected -= timedelta(days=1)
        valid = trade_day == expected
        return {'price':str(price),'priceMode':'raw','tradeDate':trade_day.isoformat(),'source':series.provider,'checksum':fingerprint({'series':series.checksum,'time':observed.isoformat(),'price':str(price)}),'seriesChecksum':series.checksum,'retrievedAt':datetime.now(timezone.utc).isoformat(),'status':('AVAILABLE' if trade_day==day else 'PREVIOUS_CLOSE') if valid else 'STALE','qualityFlags':list(series.quality_flags)}

def refresh_due_books(*, service=None, limit=20):
    svc = service or PortfolioHistoryService(); now = svc.clock(); count = 0
    with svc.repo.connection() as db:
        cur = db.cursor(); cur.execute('SELECT b.id,b.user_id FROM qd_portfolio_books b LEFT JOIN qd_portfolio_nav_jobs j ON j.book_id=b.id WHERE b.revision>0 AND (j.next_due IS NULL OR j.next_due<=?) AND (j.lease_until IS NULL OR j.lease_until<=?) ORDER BY b.dirty_from,b.id LIMIT ?', (now.isoformat(),now.isoformat(),min(20,max(1,limit)))); books = cur.fetchall(); cur.close()
    for row in books:
        token = str(uuid4())
        with svc.repo.connection() as db:
            cur = db.cursor(); book = svc.repo._owned(cur,row['user_id'],row['id'],lock=True)
            cur.execute('INSERT INTO qd_portfolio_nav_jobs(book_id) VALUES(?) ON CONFLICT(book_id) DO NOTHING',(row['id'],))
            cur.execute('SELECT * FROM qd_portfolio_nav_jobs WHERE book_id=? FOR UPDATE',(row['id'],)); job = cur.fetchone()
            if (job['lease_until'] and timestamp(job['lease_until']) > now) or (job['next_due'] and timestamp(job['next_due']) > now): db.commit(); continue
            events = svc.repo._events(cur,row['id'],book['revision'])
            first = min(timestamp(e['effectiveAt']).astimezone(VN).date() for e in events)
            day = date.fromisoformat(book['dirty_from']) if book.get('dirty_from') else first
            cur.execute('SELECT day,next_due FROM qd_portfolio_nav_retries WHERE book_id=? AND revision=? AND day<? ORDER BY next_due,day LIMIT 1',(row['id'],book['revision'],now.astimezone(VN).date().isoformat()))
            retry = cur.fetchone()
            days = [day] if day < now.astimezone(VN).date() else []
            if retry and timestamp(retry['next_due']) <= now and date.fromisoformat(retry['day']) not in days: days.append(date.fromisoformat(retry['day']))
            if not days:
                next_day = datetime.combine(now.astimezone(VN).date()+timedelta(days=1),time.min,tzinfo=VN).astimezone(timezone.utc)
                next_due = min(next_day,timestamp(retry['next_due'])) if retry else next_day
                cur.execute('UPDATE qd_portfolio_nav_jobs SET next_due=? WHERE book_id=?',(next_due.isoformat(),row['id']))
                db.commit(); continue
            cur.execute('UPDATE qd_portfolio_nav_jobs SET lease_token=?,lease_until=? WHERE book_id=?',(token,(now+timedelta(minutes=10)).isoformat(),row['id'])); db.commit()
        try:
            successful = False
            for selected_day in days:
                try:
                    svc.refresh(row['user_id'],row['id'],selected_day.isoformat(),selected_day.isoformat()); successful = True
                except Exception:
                    from app.utils.logger import get_logger
                    get_logger(__name__).warning('Portfolio NAV refresh deferred for book %s',row['id'])
            count += int(successful)
        finally:
            with svc.repo.connection() as db:
                cur = db.cursor(); cur.execute('UPDATE qd_portfolio_nav_jobs SET lease_token=NULL,lease_until=NULL,next_due=? WHERE book_id=? AND lease_token=?',((now+timedelta(minutes=1)).isoformat(),row['id'],token)); db.commit(); cur.close()
    return count
