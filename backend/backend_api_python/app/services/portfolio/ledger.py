"""Pure, long-only native-currency ledger. All money crosses the API as strings."""
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import hashlib
import json
import re
from uuid import UUID, uuid4
from app.utils.supported_markets import normalize_supported_market, canonicalize_supported_symbol
from app.services.portfolio.positions import quote_currency

TYPES = {'deposit', 'withdraw', 'buy', 'sell', 'dividend', 'fee', 'tax', 'split', 'opening_position'}
def decimal(value, *, positive=False):
    try: number = Decimal(str(value or '0'))
    except Exception: raise ValueError('Invalid decimal') from None
    if not number.is_finite() or number < 0 or (positive and number <= 0) or number >= Decimal('1e26') or number.as_tuple().exponent < -12:
        raise ValueError('Amounts must be finite, non-negative NUMERIC(38,12) values')
    return number

def money(value):
    with localcontext() as ctx:
        ctx.prec = 70
        result = Decimal(value).quantize(Decimal('0.000000000001'))
    return format(result, 'f').rstrip('0').rstrip('.') if result else '0'

def timestamp(value):
    try: result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (ValueError, TypeError): raise ValueError('effectiveAt must be an ISO timestamp with timezone') from None
    if result.tzinfo is None: raise ValueError('Timezone is required')
    return result.astimezone(timezone.utc)

def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()

def normalize_event(payload, currency, *, now=None):
    if not isinstance(payload, dict) or currency not in {'VND', 'USD', 'USDT'}: raise ValueError('Invalid event or currency')
    kind = str(payload.get('type', '')).lower()
    if kind not in TYPES: raise ValueError('Unsupported event type')
    at = timestamp(payload.get('effectiveAt'))
    if at > (now or datetime.now(timezone.utc)): raise ValueError('Future events are not allowed')
    try: event_id = str(UUID(str(payload.get('eventId') or uuid4())))
    except ValueError: raise ValueError('eventId must be UUID') from None
    row = {'eventId': event_id, 'type': kind, 'effectiveAt': at.isoformat(), 'market': '', 'symbol': '', 'notes': str(payload.get('notes') or '')[:2000]}
    for key in ('quantity', 'unitPrice', 'amount', 'fee', 'tax'):
        row[key] = money(decimal(payload.get(key), positive=key == 'quantity' and kind in {'buy', 'sell', 'split', 'opening_position'} or key == 'unitPrice' and kind in {'buy', 'sell', 'opening_position'} or key == 'amount' and kind in {'deposit', 'withdraw', 'dividend', 'fee', 'tax'}))
    if kind in {'buy', 'sell', 'split', 'opening_position'}:
        market = normalize_supported_market(payload.get('market'))
        if market not in {'VNStock', 'Crypto', 'Forex'}: raise ValueError('Unsupported holding market')
        symbol = canonicalize_supported_symbol(market, payload.get('symbol'))
        if market == 'VNStock':
            symbol = symbol.removesuffix('.VN')
            if not re.fullmatch(r'[A-Z][A-Z0-9]{2,11}', symbol) or symbol in {'VNINDEX', 'VN30', 'HNXINDEX', 'UPCOMINDEX'}: raise ValueError('An equity symbol is required; indices cannot be holdings')
        if market == 'Crypto' and not re.fullmatch(r'[A-Z0-9]{1,20}/[A-Z0-9]{1,12}', symbol): raise ValueError('Use BASE/QUOTE crypto symbol')
        row.update(market=market, symbol=symbol)
        if quote_currency(row) != currency: raise ValueError('Holding currency must match book currency')
    if kind not in {'buy', 'sell'} and (decimal(row['fee']) or decimal(row['tax'])): raise ValueError('Use a separate fee/tax event for this type')
    return row

def replay_ledger(events, cutoff=None):
    with localcontext() as ctx:
        ctx.prec = 70
        cash = realized = income = Decimal(0)
        positions, flows = {}, []
        seen = set()
        for row in sorted(events, key=lambda e: (timestamp(e['effectiveAt']), e.get('sequence', 0))):
            if cutoff and timestamp(row['effectiveAt']) > cutoff: continue
            if row['eventId'] in seen: raise ValueError('Duplicate eventId')
            seen.add(row['eventId'])
            if row.get('cancelled'): continue
            kind = row['type']
            q, p, amount, fee, tax = (Decimal(row.get(key) or '0') for key in ('quantity', 'unitPrice', 'amount', 'fee', 'tax'))
            if kind in {'deposit', 'withdraw'}:
                flow = amount if kind == 'deposit' else -amount
                cash += flow
                flows.append({'eventId': row['eventId'], 'effectiveAt': row['effectiveAt'], 'amount': money(flow)})
            elif kind == 'dividend': cash += amount; income += amount
            elif kind in {'fee', 'tax'}: cash -= amount; realized -= amount
            else:
                key = (row['market'], row['symbol'])
                pos = positions.setdefault(key, {'quantity': Decimal(0), 'cost': Decimal(0)})
                if kind in {'buy', 'opening_position'}:
                    cost = q * p + fee + tax
                    pos['quantity'] += q; pos['cost'] += cost
                    if kind == 'buy': cash -= cost
                    else: flows.append({'eventId': row['eventId'], 'effectiveAt': row['effectiveAt'], 'amount': money(cost), 'opening': True})
                elif kind == 'sell':
                    if q > pos['quantity']: raise ValueError('Sale exceeds holding quantity')
                    cost = pos['cost'] * q / pos['quantity']
                    proceeds = q * p - fee - tax
                    if proceeds < 0: raise ValueError('Sale fees exceed proceeds')
                    cash += proceeds; realized += proceeds - cost
                    pos['quantity'] -= q; pos['cost'] -= cost
                elif kind == 'split':
                    if pos['quantity'] <= 0: raise ValueError('Split requires an existing holding')
                    pos['quantity'] = q
            if cash < 0: raise ValueError('Event would make cash negative')
        return {'cash': money(cash), 'realizedPnl': money(realized), 'income': money(income), 'externalFlows': flows, 'positions': [{'market': m, 'symbol': s, 'quantity': money(v['quantity']), 'cost': money(v['cost']), 'averageCost': money(v['cost'] / v['quantity'])} for (m, s), v in positions.items() if v['quantity'] > 0]}
