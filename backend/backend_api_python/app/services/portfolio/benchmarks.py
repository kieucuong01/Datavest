"""Explicit price-return benchmarks in the account's native currency."""
from datetime import datetime, time, timezone
from decimal import Decimal
from .ledger import money, fingerprint
from .ledger_repository import LedgerRepository
from .history import PortfolioHistoryService
from .nav import VN
from app.services.portfolio_optimizer.market_data import Instrument

REGISTRY = {
 'VND':[{'key':'VNINDEX','market':'VNStock','symbol':'VNINDEX','unit':'INDEX_POINTS'},{'key':'VN30','market':'VNStock','symbol':'VN30','unit':'INDEX_POINTS'}],
 'USDT':[{'key':'BTC/USDT','market':'Crypto','symbol':'BTC/USDT','unit':'USDT'}],
 'USD':[{'key':'XAUUSD','market':'Forex','symbol':'XAUUSD','unit':'USD'}]
}
DISCLAIMER = 'Benchmark uses raw price return, without dividends. Portfolio includes recorded cash dividends and fees. Excess is a percentage-point comparison, not alpha or a total-return index comparison.'
def benchmark_registry(currency): return [{**item,'currency':currency,'returnType':'price return'} for item in REGISTRY.get(currency,[])]
def definition(key,currency):
    item = next((row for row in benchmark_registry(currency) if row['key']==key),None)
    if item is None: raise ValueError('Benchmark must match the book currency')
    return item

def compare_benchmark(nav_points, benchmark_series, *, benchmark_key, currency):
    definition(benchmark_key,currency)
    benchmark = {}
    for row in benchmark_series:
        try:
            price = Decimal(str(row.get('price')))
            if price.is_finite() and price > 0 and row.get('priceMode')=='raw' and row.get('source') and row.get('checksum'): benchmark[row['day']] = row
        except (ArithmeticError,ValueError,TypeError): pass
    nav = sorted(nav_points,key=lambda row:row['day'])
    common = [row for row in nav if row.get('nav') is not None and row['day'] in benchmark]
    result = {'benchmarkKey':benchmark_key,'currency':currency,'priceMode':'raw','returnType':'price return','points':[],'benchmarkReturn':None,'portfolioReturn':None,'excessPctPoints':None,'firstCommonDate':common[0]['day'] if common else None,'lastCommonDate':common[-1]['day'] if common else None,'disclaimer':DISCLAIMER,'sources':sorted({row['source'] for row in benchmark.values()}),'checksum':fingerprint(benchmark)}
    if len(common) < 2: return {**result,'reason':'two_common_valuations_required'}
    first,last = common[0],common[-1]
    begin_b = Decimal(benchmark[first['day']]['price']); begin_p = Decimal(first['nav'])
    if begin_p <= 0: return {**result,'reason':'non_positive_capital'}
    interval = [row for row in nav if first['day'] <= row['day'] <= last['day']]
    interrupted = False
    for row in interval:
        bench = benchmark.get(row['day']); portfolio = None
        if row.get('nav') is None or bench is None: interrupted = True
        elif not interrupted:
            if 'cumulativeReturn' in row:
                if row['cumulativeReturn'] is None or first.get('cumulativeReturn') is None: interrupted = True
                else: portfolio = money((1+Decimal(row['cumulativeReturn']))/(1+Decimal(first['cumulativeReturn']))*100)
            elif any(item.get('externalFlows') for item in interval if first['day'] < item['day'] <= row['day']): interrupted = True
            else: portfolio = money(Decimal(row['nav'])/begin_p*100)
        result['points'].append({'day':row['day'],'benchmark':money(Decimal(bench['price'])/begin_b*100) if bench else None,'portfolio':portfolio,'tradeDate':bench.get('tradeDate') if bench else None})
    result['benchmarkReturn'] = money(Decimal(benchmark[last['day']]['price'])/begin_b-1)
    if not interrupted and result['points'][-1]['portfolio'] is not None:
        result['portfolioReturn'] = money(Decimal(result['points'][-1]['portfolio'])/100-1)
        result['excessPctPoints'] = money((Decimal(result['portfolioReturn'])-Decimal(result['benchmarkReturn']))*100)
    return {**result,'reason':'interrupted_or_unknown_return' if interrupted else None}

class BenchmarkService:
    def __init__(self,repository=None,history=None):
        self.repo = repository or LedgerRepository(); self.history = history or PortfolioHistoryService(self.repo)
    def select(self,user_id,book_id,key):
        with self.repo.connection() as db:
            cur = db.cursor(); book = self.repo._owned(cur,user_id,book_id,lock=True)
            definition(key,book['currency'])
            cur.execute('UPDATE qd_portfolio_books SET benchmark_key=? WHERE id=? AND user_id=?',(key,book_id,user_id)); db.commit(); cur.close()
        return {'benchmarkKey':key,'revision':book['revision']}
    def compare(self,user_id,book_id,key=None,start=None,end=None):
        book = self.repo.load_owned(user_id,book_id)
        registry = benchmark_registry(book['currency']); key = key or book.get('benchmark_key')
        if not key: return {'registry':registry,'benchmarkKey':None,'points':[],'excessPctPoints':None,'revision':book['revision']}
        item = definition(key,book['currency']); begin, finish = self.history.bounds(start,end)
        nav = self.history.history(user_id,book_id,begin.isoformat(),finish.isoformat())
        quotes = []
        try:
            from datetime import timedelta, date
            series = self.history.gateway.fetch_daily(Instrument(item['market'],item['symbol'],book['currency'],market_type='spot' if item['market']=='Crypto' else ''),start_date=(begin-timedelta(days=10)).isoformat(),end_date=finish.isoformat(),price_mode='raw')
            for row in nav['points']:
                day = date.fromisoformat(row['day'])
                quote = self.history.quote(series,item['market'],day,datetime.combine(day,time.max,tzinfo=VN).astimezone(timezone.utc),allow_index=True)
                if quote.get('status') in {'AVAILABLE','PREVIOUS_CLOSE'}: quotes.append({**quote,'day':row['day']})
        except Exception: pass
        result = compare_benchmark(nav['points'],quotes,benchmark_key=key,currency=book['currency'])
        return {**result,'registry':registry,'revision':nav['revision'],'priceUnit':item['unit']}
