"""Daily valuation and guarded cash-flow-adjusted estimates, never synthetic TWR."""
from datetime import date, timedelta
from decimal import Decimal, localcontext
from zoneinfo import ZoneInfo
from .ledger import replay_ledger, fingerprint, money, timestamp
VN = ZoneInfo('Asia/Ho_Chi_Minh')

def build_nav_snapshot(events, prices, *, cutoff, ledger_revision):
    with localcontext() as ctx:
        ctx.prec = 70
        return _build_nav_snapshot(events,prices,cutoff=cutoff,ledger_revision=ledger_revision)

def _build_nav_snapshot(events, prices, *, cutoff, ledger_revision):
    state = replay_ledger(events, cutoff)
    day = cutoff.astimezone(VN).date().isoformat()
    positions = []; valued = Decimal(state['cash']); available = 0
    for row in state['positions']:
        quote = prices.get((row['market'], row['symbol']), {})
        valid = quote.get('priceMode') == 'raw' and quote.get('source') and quote.get('checksum') and quote.get('tradeDate', '9999') <= day and quote.get('status') in {'AVAILABLE', 'PREVIOUS_CLOSE'}
        try:
            price = Decimal(str(quote.get('price')))
            valid = valid and price.is_finite() and price > 0
        except Exception: price = Decimal(0); valid = False
        value = Decimal(row['quantity']) * price if valid else None
        if valid: available += 1; valued += value
        positions.append({**row, 'price': money(price) if valid else None, 'marketValue': money(value) if valid else None, 'quote': quote, 'valuationStatus': quote.get('status', 'UNAVAILABLE') if valid else 'UNAVAILABLE'})
    complete = available == len(positions)
    applied = [e for e in events if timestamp(e['effectiveAt']) <= cutoff]
    ordered = sorted(applied,key=lambda e:(timestamp(e['effectiveAt']),e.get('sequence',0)))
    for flow in state['externalFlows']:
        index = next(i for i,e in enumerate(ordered) if e['eventId']==flow['eventId'])
        before = replay_ledger(ordered[:index])
        if not before['positions']:
            flow['valuationAtFlow'] = before['cash']
    snapshot = {'day': day, 'cutoff': cutoff.isoformat(), 'ledgerRevision': ledger_revision, 'ledgerChecksum': fingerprint(applied), 'cash': state['cash'], 'nav': money(valued) if complete else None, 'valuedNav': money(valued), 'coverage': f'{available}/{len(positions)}', 'status': 'AVAILABLE' if complete else 'UNAVAILABLE' if not available else 'PARTIAL', 'positions': positions, 'externalFlows': state['externalFlows'], 'priceMode': 'raw'}
    snapshot['checksum'] = fingerprint(snapshot)
    return snapshot

def modified_dietz(begin_nav, end_nav, flows, start_at, end_at):
    result = {'return': None, 'reason': None, 'method': 'Modified Dietz estimate'}
    try:
        begin, end = Decimal(str(begin_nav)), Decimal(str(end_nav))
        seconds = Decimal(str((end_at - start_at).total_seconds()))
        if not begin.is_finite() or not end.is_finite() or seconds <= 0: raise ValueError()
        total = weighted = Decimal(0)
        for flow in flows:
            at = timestamp(flow['effectiveAt'])
            if not start_at < at <= end_at: continue
            amount = Decimal(str(flow['amount']))
            if not amount.is_finite(): raise ValueError()
            valuation = Decimal(str(flow.get('valuationAtFlow'))) if flow.get('valuationAtFlow') is not None else None
            if abs(amount) >= abs(begin) * Decimal('0.1') and amount and (valuation is None or not valuation.is_finite() or valuation < 0):
                return {**result, 'reason': 'large_flow_requires_valuation'}
            total += amount
            weighted += amount * Decimal(str((end_at-at).total_seconds())) / seconds
        denominator = begin + weighted
        if denominator <= 0: return {**result, 'reason': 'non_positive_capital'}
        return {**result, 'return': money((end-begin-total)/denominator)}
    except (ValueError, TypeError, ArithmeticError): return {**result, 'reason': 'invalid_or_missing_valuation'}

def performance_points(points):
    output = []; cumulative = Decimal(1); valid_chain = True
    for n, point in enumerate(points):
        row = {**point, 'periodReturn': None, 'cumulativeReturn': None, 'returnReason': None}
        if point.get('nav') is None or point.get('status') != 'AVAILABLE': valid_chain = False; row['returnReason'] = 'missing_valuation'
        elif n == 0: row['cumulativeReturn'] = '0' if Decimal(point['nav']) > 0 else None
        else:
            previous = points[n-1]
            if (date.fromisoformat(point['day']) - date.fromisoformat(previous['day'])).days != 1: valid_chain = False
            estimate = modified_dietz(previous.get('nav'), point['nav'], point.get('externalFlows', []), timestamp(previous['cutoff']), timestamp(point['cutoff']))
            row['periodReturn'] = estimate['return']; row['returnReason'] = estimate['reason']
            if estimate['return'] is None: valid_chain = False
            if valid_chain:
                cumulative *= 1 + Decimal(estimate['return'])
                row['cumulativeReturn'] = money(cumulative-1)
        output.append(row)
    return output
