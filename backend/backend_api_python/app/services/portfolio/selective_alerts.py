from decimal import Decimal
from urllib.parse import urlsplit, quote
from .ledger import fingerprint, timestamp, money
from .report_changes import report_change

DEFAULTS = {'enabled':False,'concentrationPct':50,'dataQuality':True,'reports':True,'events':False,'digestHours':24,'cooldownHours':6}
def normalize_preferences(payload,existing=None):
    settings = {**DEFAULTS,**(existing or {}),**{k:v for k,v in payload.items() if k in DEFAULTS}}
    for key in ('enabled','dataQuality','reports','events'):
        if not isinstance(settings[key],bool): raise ValueError(key + ' must be boolean')
    for key,minimum,maximum in [('concentrationPct',1,100),('digestHours',6,168),('cooldownHours',6,168)]:
        value = settings[key]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not minimum <= value <= maximum: raise ValueError(key + ' outside supported range')
    return settings
def safe_url(value):
    try:
        parsed = urlsplit(str(value or ''))
        return str(value)[:2000] if parsed.scheme in {'https','http'} and parsed.hostname and not parsed.username and not any(ord(c)<32 for c in str(value)) else ''
    except ValueError: return ''
def _alloc(snapshot,threshold):
    if not snapshot or not snapshot.get('fresh') or snapshot.get('status')!='AVAILABLE' or snapshot.get('nav') is None: return None
    nav = Decimal(snapshot['nav'])
    if nav <= 0: return None
    return {f"{p['market'].lower()}:{p['symbol']}":{'active':Decimal(str(p['marketValue']))/nav*100 > Decimal(str(threshold)),'pct':money(Decimal(str(p['marketValue']))/nav*100),'quote':p.get('quote',{})} for p in snapshot.get('positions',[]) if p.get('marketValue') is not None}
def evaluate_selective_alerts(settings,current,previous):
    if not settings.get('enabled') or previous is None: return []
    alerts = []; observed = current.get('asOf') or (current.get('snapshot') or {}).get('cutoff')
    def add(rule,asset,active,evidence,token=None):
        alerts.append({'rule':rule,'assetKey':asset,'active':active,'observedAt':observed,'evidence':evidence,'fingerprint':token or fingerprint({'rule':rule,'asset':asset,'active':active})})
    old,new = _alloc(previous.get('allocationSnapshot') or previous.get('snapshot'),settings['concentrationPct']),_alloc(current.get('snapshot'),settings['concentrationPct'])
    if old is not None and new is not None:
        for asset in old.keys() | new.keys():
            before,after = old.get(asset,{}),new.get(asset,{})
            if bool(before.get('active')) != bool(after.get('active')):
                add('allocation',asset,bool(after.get('active')),{'percent':after.get('pct','0'),'threshold':str(settings['concentrationPct']),'tradeDate':after.get('quote',{}).get('tradeDate'),'source':after.get('quote',{}).get('source')})
    if settings.get('dataQuality'):
        before,after = previous.get('snapshot'),current.get('snapshot')
        def degraded(snapshot): return not snapshot or not snapshot.get('fresh') or snapshot.get('nav') is None or snapshot.get('status')!='AVAILABLE'
        old_bad,new_bad = degraded(before),degraded(after)
        if old_bad != new_bad:
            evidence = after or {}
            add('data_quality','book',new_bad,{'day':evidence.get('day'),'status':'UNAVAILABLE' if not after else 'STALE' if not after.get('fresh') else after.get('status'),'checksum':evidence.get('checksum')})
    if settings.get('reports'):
        old_reports = {(r.get('assetKey'),r.get('reportKind'),r.get('locale')):r for r in previous.get('reports',[])}
        for report in current.get('reports',[]):
            old_report = old_reports.get((report.get('assetKey'),report.get('reportKind'),report.get('locale')))
            change = report_change(old_report,report)
            if change: add('report_change',report['assetKey'],True,{'fields':change['fields'],'effectiveDate':change['effectiveDate'],'generatedAt':change['generatedAt'],'sourceUrl':'/api/smart-insights/research/reports/' + quote(report['assetKey'],safe='') + '/deep?effective_date=' + change['effectiveDate'],'interpretation':'Final-manager text changed; conditions have not been evaluated'},change['fingerprint'])
    if settings.get('events'):
        known = {(r.get('source'),r.get('eventId')) for r in previous.get('events',[])}
        for event in current.get('events',[]):
            link = safe_url(event.get('sourceUrl'))
            try: new_date = timestamp(previous.get('baselineAt') or previous['asOf']) < timestamp(event['availableAt']) <= timestamp(current['asOf'])
            except (KeyError,ValueError): new_date = False
            if event.get('eventId') and event.get('source') and link and event.get('assetKey') and new_date and (event['source'],event['eventId']) not in known:
                add('asset_event',event['assetKey'],True,{k:event.get(k) for k in ('eventId','source','availableAt','title')} | {'sourceUrl':link},fingerprint({'source':event['source'],'id':event['eventId']}))
    return alerts
