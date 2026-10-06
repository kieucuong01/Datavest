from decimal import Decimal
import pytest
from app.services.portfolio.benchmarks import benchmark_registry, compare_benchmark, BenchmarkService
from tests.test_portfolio_ledger_repository import repository
from app.services.portfolio.books import BooksService

def benchmark(days, prices):
    return [{'day':day,'price':str(price),'source':'fixture','checksum':'hash','priceMode':'raw'} for day,price in zip(days,prices)]
def test_aligned_returns_and_native_currency():
    nav = [{'day':'2026-10-01','nav':'100','externalFlows':[]},{'day':'2026-10-02','nav':'108','externalFlows':[]}]
    result = compare_benchmark(nav,benchmark(['2026-09-30','2026-10-01','2026-10-02'],[90,100,110]),benchmark_key='VNINDEX',currency='VND')
    assert result['firstCommonDate'] == '2026-10-01'
    assert Decimal(result['excessPctPoints']) == -2
    assert Decimal(result['points'][-1]['benchmark']) == 110
    with pytest.raises(ValueError): compare_benchmark(nav,[],benchmark_key='XAUUSD',currency='VND')
    assert benchmark_registry('EUR') == []
    assert result['priceMode'] == 'raw' and 'price return' in result['disclaimer']

def test_partial_single_and_unknown_flow_do_not_create_excess():
    days = ['2026-10-01','2026-10-02','2026-10-03']
    nav = [{'day':days[0],'nav':'100'}, {'day':days[1],'nav':None}, {'day':days[2],'nav':'108'}]
    result = compare_benchmark(nav,benchmark(days,[100,105,110]),benchmark_key='VNINDEX',currency='VND')
    assert result['excessPctPoints'] is None and result['portfolioReturn'] is None
    assert compare_benchmark(nav[:1],benchmark(days,[100,105,110]),benchmark_key='VNINDEX',currency='VND')['excessPctPoints'] is None
    nav = [{'day':days[0],'nav':'100','cumulativeReturn':'0'}, {'day':days[1],'nav':'150','cumulativeReturn':None,'externalFlows':[{'amount':'50'}]}]
    assert compare_benchmark(nav,benchmark(days,[100,105,110]),benchmark_key='VNINDEX',currency='VND')['portfolioReturn'] is None

def test_selection_owner_scoped_without_changing_ledger(repository):
    svc = BooksService(repository)
    book = svc.create(1, {'name':'VND','currency':'VND'})
    benchmark_svc = BenchmarkService(repository=repository)
    benchmark_svc.select(1,book['id'],'VN30')
    assert svc.state(1,book['id'])['benchmark_key'] == 'VN30'
    assert svc.state(1,book['id'])['revision'] == 0
    with pytest.raises(LookupError): benchmark_svc.select(2,book['id'],'VNINDEX')
    with pytest.raises(ValueError): benchmark_svc.select(1,book['id'],'BTC/USDT')
