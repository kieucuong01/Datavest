"""Read stored evidence only, preserving existing shared-report authorization."""
from datetime import timedelta
import json
from .ledger import replay_ledger, timestamp
from .nav import VN
from .report_changes import report_fields
from .selective_alerts import safe_url

def read_alert_sources(repository,book,preferences,now):
    previous = json.loads(preferences['baseline_json']) if preferences.get('baseline_json') else {}
    settings = json.loads(preferences['settings_json'])
    holdings = replay_ledger(book['events'])['positions']
    with repository.connection() as db:
        cur = db.cursor()
        cur.execute('SELECT market,symbol FROM qd_watchlist WHERE user_id=?',(book['user_id'],)); watchlist=[dict(row) for row in cur.fetchall()]
        cur.execute('SELECT snapshot_json FROM qd_portfolio_nav_snapshots WHERE book_id=? AND revision=? ORDER BY day DESC LIMIT 1',(book['id'],book['revision'])); row=cur.fetchone()
        snapshot=json.loads(row['snapshot_json']) if row else None
        if snapshot: snapshot['fresh'] = snapshot['day']==(now.astimezone(VN).date()-timedelta(days=1)).isoformat()
        cursor = int(previous.get('eventCursor',0)); events=[]; next_cursor=cursor
        symbols = sorted({row['symbol'] for row in [*holdings,*watchlist] if row['market']=='VNStock'})
        if settings['events'] and symbols:
            cur.execute('SELECT id,event_id,symbol,source,source_url,available_at,title FROM qd_vietnam_events WHERE id>? AND symbol IN ('+','.join('?' for _ in symbols)+') ORDER BY id LIMIT 1000',(cursor,*symbols))
            rows=cur.fetchall(); blocked=False
            for event in rows:
                if timestamp(event['available_at'])>now: blocked=True;continue
                if not blocked: next_cursor=event['id']
                if timestamp(event['available_at'])<=timestamp(preferences['baseline_at']): continue
                link=safe_url(event['source_url'])
                if event['event_id'] and event['source'] and link: events.append({'eventId':event['event_id'],'assetKey':'vnstock:'+event['symbol'],'source':event['source'],'sourceUrl':link,'availableAt':str(event['available_at']),'title':str(event['title'])[:300]})
        cur.close()
    reports=[]
    if settings['reports']:
        from app.services.smart_insights.shared_research_access import SharedResearchAccessService
        from app.services.smart_insights.public_reports import public_asset_key
        access=SharedResearchAccessService(watchlist_loader=lambda user_id:watchlist)
        relevant={public_asset_key(row) for row in [*holdings,*watchlist]}
        # assets_for_user includes the common public assets; only held/watched
        # assets may contribute alerts, and shared assets still need a watchlist.
        for asset in access.assets_for_user(book['user_id']):
            key=public_asset_key(asset)
            if key not in relevant: continue
            report=access.state(user_id=book['user_id'],asset_key=key,report_kind='deep',today=now.astimezone(VN).date()).get('report')
            if not report: continue
            try:
                if timestamp(report['generatedAt'])>now: continue
            except (ValueError,KeyError): continue
            reports.append({k:report[k] for k in ('assetKey','reportKind','locale','effectiveDate','generatedAt')} | {'status':'complete','fields':report_fields(report)})
    return {'asOf':now.isoformat(),'baselineAt':str(preferences['baseline_at']),'snapshot':snapshot,'reports':reports,'events':events,'eventCursor':next_cursor}

def evaluate_due_alerts(*,repository=None,source_reader=None,clock=None,limit=20):
    from datetime import datetime,timezone
    from .alert_repository import AlertRepository
    from .ledger_repository import LedgerRepository
    repo=repository or LedgerRepository(); alerts=AlertRepository(repo); now=(clock or (lambda:datetime.now(timezone.utc)))()
    reader=source_reader or read_alert_sources
    with repo.connection() as db:
        cur=db.cursor();cur.execute('SELECT b.id,b.user_id,p.settings_json,p.baseline_json,p.baseline_at,p.next_digest_at FROM qd_portfolio_books b JOIN qd_portfolio_alert_preferences p ON p.book_id=b.id WHERE p.next_check_at IS NULL OR p.next_check_at<=? ORDER BY p.next_check_at,p.next_digest_at,b.id',(now.isoformat(),)); rows=cur.fetchall();cur.close()
    users=set(); processed=0
    # Disabled books do not consume the bounded batch. next_digest_at rotates
    # delivered users; baseline cursor keeps report/events stable after restart.
    for row in rows:
        if not json.loads(row['settings_json'])['enabled']: continue
        if processed>=min(20,max(1,limit)): break
        try:
            book=repo.load_owned(row['user_id'],row['id'])
            current=reader(repo,book,row,now)
            alerts.evaluate(row['user_id'],row['id'],current,now)
            users.add(row['user_id']);processed+=1
        except Exception:
            from app.utils.logger import get_logger
            get_logger(__name__).warning('Portfolio alert evaluation deferred for book %s',row['id'],exc_info=True)
        finally:
            with repo.connection() as db:
                cur=db.cursor();cur.execute('UPDATE qd_portfolio_alert_preferences SET next_check_at=? WHERE book_id=? AND user_id=?',((now+timedelta(minutes=1)).isoformat(),row['id'],row['user_id']));db.commit();cur.close()
    for user in users: alerts.emit_due_digest(user,now)
    return processed
