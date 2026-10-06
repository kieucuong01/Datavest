from datetime import datetime, timezone
from decimal import Decimal
import pytest
from app.services.portfolio.nav import build_nav_snapshot, modified_dietz, performance_points
from app.services.portfolio.ledger import normalize_event
START = datetime(2026,10,1,tzinfo=timezone.utc)
END = datetime(2026,10,3,tzinfo=timezone.utc)
def test_dietz_flows_dividend_and_large_flow_guard():
    flow = [{'amount':'50','effectiveAt':'2026-10-02T00:00:00Z','valuationAtFlow':'125'}]
    assert modified_dietz('100','150',flow,START,END)['return'] == '0'
    assert Decimal(modified_dietz('100','160',flow,START,END)['return']) == Decimal('0.08')
    assert modified_dietz('100','120',[{'amount':'20','effectiveAt':'2026-10-02T00:00:00Z'}],START,END)['reason'] == 'large_flow_requires_valuation'
    assert modified_dietz('100','110',[],START,END)['return'] == '0.1'
    assert modified_dietz('0','0',[],START,END)['return'] is None
    assert modified_dietz('100','100',[{'amount':'50','effectiveAt':START.isoformat()}],START,END)['return'] == '0'

def test_snapshot_missing_raw_and_historical_quantity():
    rows = [normalize_event({'type':'deposit','amount':'1000','effectiveAt':'2026-10-01T00:00:00Z'},'VND',now=END),normalize_event({'type':'buy','market':'VNStock','symbol':'FPT','quantity':'10','unitPrice':'10','effectiveAt':'2026-10-01T01:00:00Z'},'VND',now=END),normalize_event({'type':'sell','market':'VNStock','symbol':'FPT','quantity':'5','unitPrice':'12','effectiveAt':'2026-10-03T00:00:00Z'},'VND',now=END)]
    cutoff = datetime(2026,10,2,16,59,59,tzinfo=timezone.utc)
    prices = {('VNStock','FPT'):{'price':'11','priceMode':'raw','tradeDate':'2026-10-02','source':'fixture','checksum':'abc','status':'AVAILABLE'}}
    snap = build_nav_snapshot(rows, prices, cutoff=cutoff, ledger_revision=3)
    assert snap['nav'] == '1010'
    assert snap['positions'][0]['quantity'] == '10'
    assert build_nav_snapshot(rows,{},cutoff=cutoff,ledger_revision=3)['nav'] is None
    prices[('VNStock','FPT')]['priceMode'] = 'total_return'
    assert build_nav_snapshot(rows,prices,cutoff=cutoff,ledger_revision=3)['nav'] is None
    prices[('VNStock','FPT')].update(priceMode='raw',tradeDate='2026-10-03')
    assert build_nav_snapshot(rows,prices,cutoff=cutoff,ledger_revision=3)['nav'] is None

def test_performance_does_not_chain_across_gap():
    points = [{'day':'2026-10-01','cutoff':'2026-10-01T17:00:00Z','nav':'100','status':'AVAILABLE','externalFlows':[]}, {'day':'2026-10-02','cutoff':'2026-10-02T17:00:00Z','nav':None,'status':'PARTIAL','externalFlows':[]}, {'day':'2026-10-03','cutoff':'2026-10-03T17:00:00Z','nav':'110','status':'AVAILABLE','externalFlows':[]}]
    assert performance_points(points)[-1]['cumulativeReturn'] is None
