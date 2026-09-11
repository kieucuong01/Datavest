"""Free Bitview/BRK daily BTC data; no credentials, browser or Bitcoin node.

Provider definitions: https://bitview.space/api/series/<identifier>
Daily dates come from the provider's date series, never an assumed index epoch.
BRK holder threshold is 150 days, NOT Glassnode's 155-day convention.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
from urllib.parse import urlencode

from .collectors import CollectorUnavailable
from .contracts import Observation
from .sources import source_for_code
from .transport import RequestsTransport

METRICS = {
    'mvrv': ('mvrv', 'ratio'),
    'nupl': ('nupl', 'ratio'),
    'supply_in_profit_share': ('supply_in_profit_pct', '%'),
    'sopr_24h': ('sopr', 'ratio'),
    'lth_supply': ('lth_supply', 'BTC'),
    'sth_supply': ('sth_supply', 'BTC'),
    'realized_price': ('realized_price', 'USD'),
    'lth_realized_price': ('cost_basis_lth', 'USD'),
    'sth_realized_price': ('cost_basis_sth', 'USD'),
}
AGE_SERIES = tuple(f'utxos_under_{age}_old_supply' for age in ('1m', '3m', '6m', '1y', '2y', '3y'))
AGE_BANDS = ('0–30d', '30–90d', '90–180d', '180–365d', '365–730d', '730–1095d', '1095d+')


def _number(raw):
    if raw is None:
        return None
    try:
        value = Decimal(str(raw))
    except InvalidOperation as exc:
        raise CollectorUnavailable('INVALID_VALUE') from exc
    if not value.is_finite():
        raise CollectorUnavailable('INVALID_VALUE')
    return value


class BitviewCollector:
    def __init__(self, *, transport=None, history_days=370):
        if not 1 <= history_days <= 730:
            raise ValueError('history_days must be between 1 and 730')
        self.transport = transport or RequestsTransport()
        self.source = source_for_code('bitview-onchain')
        self.history_days = history_days

    def collect(self, as_of):
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError('as_of must be timezone-aware')
        cutoff = as_of.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        start = cutoff - timedelta(days=self.history_days)
        query = urlencode({'start': start.date().isoformat(), 'end': cutoff.date().isoformat()})

        def fetch(series):
            url = f'{self.source.urls[0]}/{series}/day1?{query}'
            response = self.transport.fetch(url, timeout_seconds=20, max_bytes=250_000)
            if response.status != 200 or response.url != url:
                raise CollectorUnavailable('SOURCE_UNAVAILABLE')
            try:
                payload = json.loads(response.body)
            except (ValueError, UnicodeError) as exc:
                raise CollectorUnavailable('INVALID_RESPONSE') from exc
            if (not isinstance(payload, dict) or payload.get('index') != 'day1'
                    or not isinstance(payload.get('data'), list)
                    or type(payload.get('start')) is not int or type(payload.get('end')) is not int
                    or payload['end'] - payload['start'] != len(payload['data'])
                    or len(payload['data']) > self.history_days + 1):
                raise CollectorUnavailable('SCHEMA_DRIFT')
            return payload

        calendar = fetch('date')
        try:
            dates = [datetime.strptime(d, '%Y-%m-%d').replace(tzinfo=timezone.utc) for d in calendar['data']]
        except (ValueError, TypeError) as exc:
            raise CollectorUnavailable('INVALID_TIMESTAMP') from exc
        if any(b - a != timedelta(days=1) for a, b in zip(dates, dates[1:])):
            raise CollectorUnavailable('INVALID_TIMESTAMP')
        data = {}
        for series in (*METRICS, 'supply', *AGE_SERIES):
            payload = fetch(series)
            if (payload['start'], payload['end']) != (calendar['start'], calendar['end']):
                raise CollectorUnavailable('MISALIGNED_SERIES')
            data[series] = [_number(v) for v in payload['data']]

        rows = []
        def emit(day, metric, value, unit, provider_series, **dimensions):
            rows.append(Observation.create(
                source_code=self.source.code, source_url=f'{self.source.urls[0]}/{provider_series}/day1',
                market='crypto', symbol='BTC', effective_at=day, observed_at=as_of,
                methodology_version=self.source.methodology_version, data_class='LIVE',
                value={'metric': f'crypto.onchain.{metric}', 'value': str(value), 'unit': unit,
                       'dimensions': {'providerMetric': provider_series, 'frequency': 'daily',
                                      'holderThresholdDays': 150, **dimensions}},
            ))

        for i, day in enumerate(dates):
            if not start <= day < cutoff:
                continue
            for series, (metric, unit) in METRICS.items():
                value = data[series][i]
                if value is None:
                    continue
                if ((series != 'nupl' and value < 0) or (series == 'nupl' and value > 1)
                        or (unit == '%' and value > 100)):
                    raise CollectorUnavailable('INVALID_VALUE')
                emit(day, metric, value, unit, series)
            total = data['supply'][i]
            cumulative = [data[s][i] for s in AGE_SERIES]
            if total is None or total <= 0 or any(v is None for v in cumulative):
                continue
            edges = [Decimal(0), *cumulative, total]
            if any(b < a for a, b in zip(edges, edges[1:])):
                raise CollectorUnavailable('INVALID_HODL_DISTRIBUTION')
            for band, lower, upper in zip(AGE_BANDS, edges, edges[1:]):
                emit(day, 'hodl_waves', (upper - lower) / total * 100, '%', 'supply',
                     dimension=band, label=band, calculation='difference-of-cumulative-supply / supply * 100',
                     inputSeries=list(AGE_SERIES), lowerSupplyBtc=str(lower),
                     upperSupplyBtc=str(upper), totalSupplyBtc=str(total))
        if not rows:
            raise CollectorUnavailable('NO_CLOSED_DAY_DATA')
        return tuple(rows)
