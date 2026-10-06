from app.services.portfolio.selective_alerts import evaluate_selective_alerts, normalize_preferences
from app.services.portfolio.report_changes import report_change
def snapshot(value='60',nav='100',status='AVAILABLE'):
    return {'fresh':True,'day':'2026-10-05','nav':nav,'status':status,'positions':[{'market':'VNStock','symbol':'FPT','marketValue':value,'quote':{'source':'fixture','tradeDate':'2026-10-05','status':'AVAILABLE'}}]}
def prefs(): return {**normalize_preferences({}), 'enabled':True}

def test_baseline_threshold_recovery_and_partial_valuation():
    settings = prefs()
    assert evaluate_selective_alerts(settings, {'snapshot':snapshot()}, None) == []
    old={'snapshot':snapshot('40')}; current={'snapshot':snapshot('60')}
    alerts=evaluate_selective_alerts(settings,current,old)
    assert len(alerts)==1 and alerts[0]['rule']=='allocation' and alerts[0]['active']
    assert evaluate_selective_alerts(settings,current,current)==[]
    assert evaluate_selective_alerts(settings,old,current)[0]['active'] is False
    assert not any(row['rule']=='allocation' for row in evaluate_selective_alerts(settings,{'snapshot':snapshot('60',None,'PARTIAL')},old))
    assert evaluate_selective_alerts({**settings,'enabled':False},current,old)==[]

def test_data_quality_recovery_and_valid_previous_close():
    settings = prefs()
    old={'snapshot':snapshot()}; bad={'snapshot':snapshot(nav=None,status='UNAVAILABLE')}
    assert evaluate_selective_alerts(settings,bad,old)[0]['rule']=='data_quality'
    assert evaluate_selective_alerts(settings,bad,bad)==[]
    assert evaluate_selective_alerts(settings,old,bad)[0]['active'] is False
    closed=snapshot();closed['positions'][0]['quote']['status']='PREVIOUS_CLOSE'
    assert evaluate_selective_alerts(settings,{'snapshot':closed},old)==[]

def report(day,text,**kw): return {'assetKey':'vnstock:FPT','reportKind':'deep','locale':'vi-VN','status':'complete','effectiveDate':day,'generatedAt':day+'T02:00:00Z','body':'## V. Portfolio Manager\n### Key Risks\n'+text,**kw}
def test_only_comparable_final_report_fields_change():
    old=report('2026-10-01','Debt'); new=report('2026-10-05','Liquidity')
    change=report_change(old,new)
    assert change['fields'] == ['key_risks']
    assert report_change(old,{**new,'locale':'en-US'}) is None
    assert report_change(old,{**new,'effectiveDate':'2026-10-01'}) is None
    assert report_change(old,report('2026-10-05','',body='## V. Portfolio Manager\n### Rating\nHOLD')) is None
    assert report_change(old,report('2026-10-05','Debt\n## VI. Appendix\n### Key Risks\nNoise')) is None

def test_asset_event_requires_id_source_link_and_new_date():
    settings=prefs();settings['events']=True
    current={'asOf':'2026-10-06T00:00:00Z','events':[{'eventId':'123','assetKey':'vnstock:FPT','source':'fixture','sourceUrl':'https://example.com/disclosure','availableAt':'2026-10-05T00:00:00Z','title':'Cash dividend'}]}
    previous={'asOf':'2026-10-04T00:00:00Z','events':[]}
    assert evaluate_selective_alerts(settings,current,previous)[0]['rule']=='asset_event'
    current['events'][0]['sourceUrl']='javascript:alert(1)'
    assert evaluate_selective_alerts(settings,current,previous)==[]
