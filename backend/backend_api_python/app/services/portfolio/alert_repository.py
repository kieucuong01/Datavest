from datetime import timedelta
import json
import re
from .ledger import timestamp
from .ledger_repository import LedgerRepository
from .selective_alerts import normalize_preferences, evaluate_selective_alerts

class AlertRepository:
    def __init__(self,repository=None): self.repo = repository or LedgerRepository()
    def preferences(self,user_id,book_id):
        with self.repo.connection() as db:
            cur = db.cursor(); self.repo._owned(cur,user_id,book_id)
            cur.execute('SELECT * FROM qd_portfolio_alert_preferences WHERE book_id=? AND user_id=?',(book_id,user_id)); row=cur.fetchone(); cur.close()
        return {**normalize_preferences({}),**(json.loads(row['settings_json']) if row else {}),'baselineAt':str(row['baseline_at']) if row else None,'nextDigestAt':str(row['next_digest_at']) if row else None}
    def save_preferences(self,user_id,book_id,payload,now):
        with self.repo.connection() as db:
            cur = db.cursor(); self.repo._owned(cur,user_id,book_id,lock=True)
            cur.execute('SELECT * FROM qd_portfolio_alert_preferences WHERE book_id=? AND user_id=? FOR UPDATE',(book_id,user_id)); row=cur.fetchone()
            old = json.loads(row['settings_json']) if row else normalize_preferences({})
            settings = normalize_preferences(payload,old)
            changed = settings != old
            baseline_changed=any(settings[key]!=old[key] for key in ('enabled','concentrationPct','dataQuality','reports','events'))
            baseline = None if baseline_changed else (row['baseline_json'] if row else None)
            at = now.isoformat() if baseline_changed or not row else row['baseline_at']
            due = (now+timedelta(hours=settings['digestHours'])).isoformat() if changed or not row else row['next_digest_at']
            cur.execute('INSERT INTO qd_portfolio_alert_preferences(book_id,user_id,settings_json,baseline_json,baseline_at,next_digest_at) VALUES(?,?,?,?,?,?) ON CONFLICT(book_id) DO UPDATE SET settings_json=excluded.settings_json,baseline_json=excluded.baseline_json,baseline_at=excluded.baseline_at,next_digest_at=excluded.next_digest_at',(book_id,user_id,json.dumps(settings),baseline,at,due))
            if baseline_changed:
                cur.execute('UPDATE qd_portfolio_alert_state SET episode=episode+1 WHERE book_id=? AND rule IN (?,?)',(book_id,'allocation','data_quality'))
            if not settings['enabled']:
                cur.execute('UPDATE qd_portfolio_alert_pending SET cancelled=1 WHERE book_id=? AND user_id=? AND sent_at IS NULL',(book_id,user_id))
            else:
                cancelled_rules=[]
                if settings['concentrationPct'] != old['concentrationPct']: cancelled_rules.append('allocation')
                for toggle,rule in [('dataQuality','data_quality'),('reports','report_change'),('events','asset_event')]:
                    if not settings[toggle]: cancelled_rules.append(rule)
                for rule in cancelled_rules:
                    cur.execute('UPDATE qd_portfolio_alert_pending SET cancelled=1 WHERE book_id=? AND user_id=? AND sent_at IS NULL AND rule=?',(book_id,user_id,rule))
            db.commit();cur.close()
        return self.preferences(user_id,book_id)
    def evaluate(self,user_id,book_id,current,now):
        current = {**current,'asOf':now.isoformat()}
        with self.repo.connection() as db:
            cur=db.cursor(); book=self.repo._owned(cur,user_id,book_id,lock=True)
            cur.execute('SELECT * FROM qd_portfolio_alert_preferences WHERE book_id=? AND user_id=? FOR UPDATE',(book_id,user_id)); prefs=cur.fetchone()
            if not prefs: db.commit();return 0
            settings=json.loads(prefs['settings_json'])
            if not settings['enabled']: db.commit();return 0
            previous=json.loads(prefs['baseline_json']) if prefs['baseline_json'] else None
            if previous and timestamp(previous['asOf'])>now: db.commit();return 0
            if current.get('snapshot') and current['snapshot'].get('ledgerRevision') is not None and current['snapshot']['ledgerRevision']!=book['revision']:
                current['snapshot']={**current['snapshot'],'fresh':False}
            candidates=evaluate_selective_alerts(settings,current,previous)
            for alert in candidates:
                cur.execute('SELECT * FROM qd_portfolio_alert_state WHERE book_id=? AND rule=? AND asset_key=?',(book_id,alert['rule'],alert['assetKey'])); state=cur.fetchone()
                episode=(state['episode'] if state else 0)
                if alert['rule'] in {'report_change','asset_event'}: episode = 0
                elif alert['active'] and (not state or not state['active']): episode += 1
                cur.execute('INSERT INTO qd_portfolio_alert_state(book_id,rule,asset_key,episode,active,fingerprint) VALUES(?,?,?,?,?,?) ON CONFLICT(book_id,rule,asset_key) DO UPDATE SET episode=excluded.episode,active=excluded.active,fingerprint=excluded.fingerprint',(book_id,alert['rule'],alert['assetKey'],episode,int(alert['active']),alert['fingerprint']))
                self.queue_pending(cur,user_id,book,alert,episode,now)
            current_reports={(r['assetKey'],r['reportKind'],r['locale']):r for r in (previous or {}).get('reports',[])}
            current_reports.update({(r['assetKey'],r['reportKind'],r['locale']):r for r in current.get('reports',[]) if r.get('fields') or r.get('body')})
            current['reports']=list(current_reports.values())
            if current.get('snapshot') and current['snapshot'].get('nav') is not None and current['snapshot'].get('fresh'): current['allocationSnapshot']=current['snapshot']
            elif previous: current['allocationSnapshot']=previous.get('allocationSnapshot') or previous.get('snapshot')
            cur.execute('UPDATE qd_portfolio_alert_preferences SET baseline_json=? WHERE book_id=? AND user_id=?',(json.dumps(current),book_id,user_id)); db.commit();cur.close()
            return len(candidates)
    @staticmethod
    def queue_pending(cur,user_id,book,alert,episode,now):
        payload={**alert,'bookId':book['id'],'bookName':book['name']}
        cur.execute('INSERT INTO qd_portfolio_alert_pending(user_id,book_id,rule,asset_key,episode,fingerprint,payload_json,observed_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(book_id,rule,asset_key,episode,fingerprint) DO NOTHING',(user_id,book['id'],alert['rule'],alert['assetKey'],episode,alert['fingerprint'],json.dumps(payload),now.isoformat()))
    def emit_due_digest(self,user_id,now):
        with self.repo.connection() as db:
            cur=db.cursor()
            cur.execute('INSERT INTO qd_portfolio_alert_delivery(user_id) VALUES(?) ON CONFLICT(user_id) DO NOTHING',(user_id,))
            cur.execute('SELECT * FROM qd_portfolio_alert_delivery WHERE user_id=? FOR UPDATE',(user_id,)); delivery=cur.fetchone()
            cur.execute('SELECT * FROM qd_portfolio_alert_preferences WHERE user_id=? ORDER BY book_id FOR UPDATE',(user_id,)); preferences=cur.fetchall()
            eligible=[]; cooldown=6
            for prefs in preferences:
                settings=json.loads(prefs['settings_json'])
                if settings['enabled'] and timestamp(prefs['next_digest_at'])<=now:
                    eligible.append((prefs['book_id'],settings));cooldown=max(cooldown,settings['cooldownHours'])
            if not eligible or delivery['last_sent_at'] and timestamp(delivery['last_sent_at'])+timedelta(hours=cooldown)>now: db.commit();return 0
            ids=[book for book,_ in eligible]
            cur.execute('SELECT * FROM qd_portfolio_alert_pending WHERE user_id=? AND sent_at IS NULL AND cancelled=0 AND book_id IN ('+','.join('?' for _ in ids)+') ORDER BY observed_at,id LIMIT 200',(user_id,*ids))
            pending=cur.fetchall()
            if not pending: db.commit();return 0
            items=[json.loads(row['payload_json']) for row in pending]
            labels={'allocation':'Tỷ trọng','data_quality':'Chất lượng dữ liệu','report_change':'Nội dung quyết định cuối thay đổi','asset_event':'Sự kiện có nguồn'}
            def plain(value): return re.sub(r'[\x00-\x1f<>]',' ',str(value or ''))[:300]
            message='\n'.join(f"{plain(item['bookName'])} · {plain(item['assetKey'])}: {labels[item['rule']]} · {'Phát sinh' if item['active'] else 'Trở lại ngưỡng'} · {plain(item['observedAt'])}" for item in items)
            cur.execute('INSERT INTO qd_strategy_notifications(user_id,strategy_id,symbol,signal_type,channels,title,message,payload_json,created_at) VALUES(?,NULL,?,?,?,?,?,?,?)',(user_id,'','portfolio_digest','in_app','DataVest · '+str(len(items))+' thay đổi danh mục',message,json.dumps({'type':'portfolio_book_digest','items':items}),now.isoformat()))
            pending_ids=[row['id'] for row in pending]
            cur.execute('UPDATE qd_portfolio_alert_pending SET sent_at=? WHERE user_id=? AND id IN ('+','.join('?' for _ in pending_ids)+')',(now.isoformat(),user_id,*pending_ids))
            cur.execute('UPDATE qd_portfolio_alert_delivery SET last_sent_at=? WHERE user_id=?',(now.isoformat(),user_id))
            for book,settings in eligible:
                cur.execute('UPDATE qd_portfolio_alert_preferences SET next_digest_at=? WHERE book_id=? AND user_id=?',((now+timedelta(hours=settings['digestHours'])).isoformat(),book,user_id))
            db.commit();cur.close();return 1
