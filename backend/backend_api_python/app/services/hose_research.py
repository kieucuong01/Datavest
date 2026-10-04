"""A small discovery registry and a tenant-free view of frozen HOSE evidence."""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from app.services.vietnam_provenance import build_hose_provenance


# Representative sectors with existing provider adapters; not a liquidity ranking
# or a recommendation. No scheduled jobs or market universe are expanded here.
HOSE_RESEARCH_PILOT = (
    {'market': 'VNStock', 'symbol': 'FPT', 'name': 'FPT', 'selectionReason': 'Công nghệ / Technology'},
    {'market': 'VNStock', 'symbol': 'HPG', 'name': 'Hòa Phát', 'selectionReason': 'Thép / Steel'},
    {'market': 'VNStock', 'symbol': 'VCB', 'name': 'Vietcombank', 'selectionReason': 'Ngân hàng / Banking'},
)
METRICS = ('revenue', 'total_operating_income', 'net_income', 'operating_cash_flow',
           'total_debt', 'shareholder_equity', 'earnings_per_share', 'pe_ratio', 'pb_ratio')


def _text(value: Any, limit: int = 200) -> str:
    return str(value or '')[:limit]


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool) or value == '':
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _instant(value: Any) -> datetime | None:
    try:
        result = datetime.fromisoformat(str(value or '').replace('Z', '+00:00'))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)
    except ValueError:
        return None


def _url(value: Any) -> str:
    url = _text(value, 2000)
    try:
        parsed = urlsplit(url)
        return url if parsed.scheme in {'http', 'https'} and parsed.hostname and not parsed.username else ''
    except ValueError:
        return ''


def project_hose_research(raw: Any) -> dict[str, Any] | None:
    """Allowlisted facts only, from the very snapshot consumed by this run."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return None
    if not isinstance(raw, Mapping) or (raw.get('instrument') or {}).get('market') != 'VNStock':
        return None
    instrument = raw.get('instrument') or {}
    cutoff = _instant(raw.get('asOf'))
    provenance = build_hose_provenance(raw)
    price = raw.get('price') or {}
    observed = _instant(provenance['price'].get('observedAt'))
    price_value = _number(price.get('price'))
    price_valid = bool(cutoff and observed and observed <= cutoff and price_value is not None and price_value > 0)
    stale = False
    if price_valid:
        day = observed.astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date()
        end = cutoff.astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date()
        weekdays = 0
        while day < end and weekdays <= 3:
            day += timedelta(days=1)
            weekdays += day.weekday() < 5
        stale = weekdays > 3
    metrics = []
    observations = (raw.get('fundamentals') or {}).get('observations') or []
    for metric in METRICS:
        eligible = [row for row in observations if isinstance(row, Mapping) and row.get('metric') == metric
                    and cutoff and (available := _instant(row.get('availableAt'))) and available <= cutoff
                    and (end := _instant(row.get('periodEnd'))) and end <= cutoff
                    and (not row.get('revisionAt') or ((revision := _instant(row['revisionAt'])) and revision <= cutoff))
                    and row.get('source') and _number(row.get('value')) is not None]
        # Annual flow figures cannot be silently compared to quarterly figures.
        annual = [row for row in eligible if row.get('frequency') == 'ANNUAL']
        candidates = annual or eligible
        row = max(candidates, key=lambda item: (str(item['periodEnd']), item.get('reportScope') == 'CONSOLIDATED', str(item['availableAt'])), default={})
        scope = _text(row.get('reportScope') or 'UNKNOWN')
        growth = None
        growth_sources = []
        if row and scope in {'CONSOLIDATED', 'SEPARATE'} and row.get('frequency') in {'ANNUAL', 'QUARTERLY'}:
            period = _instant(row['periodEnd'])
            previous = [item for item in eligible if item.get('reportScope') == scope
                        and item.get('frequency') == row.get('frequency') and item.get('unit') == row.get('unit')
                        and item.get('source') == row.get('source')
                        and (end := _instant(item['periodEnd'])) and end.year == period.year - 1
                        and (end.month, end.day) == (period.month, period.day)]
            prior = max(previous, key=lambda item: str(item['availableAt']), default={})
            if prior and _number(prior['value']) > 0:
                growth = (_number(row['value']) / _number(prior['value']) - 1) * 100
                growth_sources = [{'periodEnd': _text(item['periodEnd']), 'availableAt': _text(item['availableAt']),
                                   'source': _text(item['source']), 'sourceUrl': _url(item.get('sourceUrl'))} for item in (prior, row)]
        metrics.append({
            'metric': metric, 'value': _number(row.get('value')), 'unit': _text(row.get('unit')),
            'periodEnd': _text(row.get('periodEnd')), 'availableAt': _text(row.get('availableAt')),
            'frequency': _text(row.get('frequency')), 'reportScope': scope,
            'source': _text(row.get('source')), 'sourceUrl': _url(row.get('sourceUrl')),
            'status': 'UNAVAILABLE' if not row else 'AVAILABLE' if scope in {'CONSOLIDATED', 'SEPARATE'} else 'PARTIAL',
            'growthPct': growth, 'growthSources': growth_sources,
        })
    # Show derived valuation only with dated inputs, never from current company shares.
    eps = next(row for row in metrics if row['metric'] == 'earnings_per_share')
    pe = next(row for row in metrics if row['metric'] == 'pe_ratio')
    if price_valid and pe['value'] is None and eps['status'] == 'AVAILABLE' and eps['frequency'] == 'ANNUAL' and eps['unit'] == 'VND' and eps['value'] and eps['value'] > 0:
        pe.update({**eps, 'metric': 'pe_ratio', 'value': price_value / eps['value'], 'unit': 'x'})
        pe.update({'growthPct': None, 'growthSources': []})
    events = []
    for row in [*(raw.get('corporateActions') or []), *(raw.get('disclosures') or [])]:
        if not isinstance(row, Mapping) or not cutoff or not (available := _instant(row.get('availableAt'))) or available > cutoff:
            continue
        events.append({key: _text(row.get(key), 300) for key in ('title', 'type', 'availableAt', 'effectiveDate')}
                      | {'source': _text(row.get('source')), 'sourceUrl': _url(row.get('sourceUrl'))})
    benchmarks = []
    for symbol in ('VNINDEX', 'VN30'):
        row = (raw.get('marketContext') or {}).get(symbol) or {}
        benchmarks.append({'symbol': symbol, 'investable': False,
                           'value': _number(row.get('price')), 'changePct': _number(row.get('changePct')),
                           'tradeDate': _text(row.get('tradeDate')), 'source': _text(row.get('source'))})
    return {
        'symbol': _text(instrument.get('symbol')), 'name': _text(instrument.get('name')),
        'sector': _text(instrument.get('sector')), 'exchange': 'HOSE', 'currency': 'VND',
        'asOf': _text(raw.get('asOf')), 'checksum': _text(raw.get('checksum'), 64),
        'price': {'value': price_value if price_valid else None, 'volume': _number(price.get('volume')) if price_valid else None,
                  'tradeDate': observed.astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date().isoformat() if observed else '',
                  'retrievedAt': provenance['price']['fetchedAt'], 'source': _text(price.get('source')),
                  'status': 'STALE' if stale else 'DAILY' if price_valid and price.get('timeframe') == '1D' else 'UNAVAILABLE',
                  'priceMode': _text(price.get('priceMode'))},
        'metrics': metrics, 'benchmarks': benchmarks, 'events': sorted(events, key=lambda row: row['availableAt'], reverse=True)[:5],
        'dataGaps': [{'field': _text(row.get('field')), 'reason': _text(row.get('reason'))}
                     for row in provenance['dataGaps'][:25]],
        'sources': [{'provider': _text(row.get('provider')), 'url': _url(row.get('url'))} for row in provenance['sources'][:12]],
    }
