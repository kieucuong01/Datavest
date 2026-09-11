import json
from datetime import datetime, timezone, timedelta

import pytest

from app.services.smart_insights.collectors import CollectorUnavailable
from app.services.smart_insights.transport import HttpResponse


def test_bitview_closed_days_units_provenance_and_dedupe():
    from app.services.smart_insights.bitview import BitviewCollector
    collector = BitviewCollector(transport=FixtureTransport(), history_days=3)
    now = datetime(2026, 9, 11, 12, tzinfo=timezone.utc)
    rows = collector.collect(now)
    nupl = next(r for r in rows if r.value['metric'] == 'crypto.onchain.nupl')
    assert nupl.symbol == 'BTC'
    assert nupl.effective_at.isoformat() == '2026-09-09T00:00:00+00:00'
    assert nupl.value['value'] == '0.3'
    assert nupl.data_class == 'LIVE'
    assert nupl.source_url.startswith('https://bitview.space/api/series/')
    assert all(r.effective_at.day < 11 for r in rows)
    profit = next(r for r in rows if r.value['metric'].endswith('supply_in_profit_pct'))
    assert profit.value['value'] == '65'
    assert profit.value['unit'] == '%'
    assert [r.checksum for r in rows] == [r.checksum for r in collector.collect(now + timedelta(hours=1))]
    waves = [r for r in rows if r.value['metric'].endswith('hodl_waves') and r.effective_at.day == 9]
    assert len(waves) == 7
    assert sum(float(r.value['value']) for r in waves) == pytest.approx(100)
    assert len({r.value['dimensions']['dimension'] for r in waves}) == 7


@pytest.mark.parametrize('fault', ['wrong_index', 'misaligned', 'invalid_date', 'invalid_number', 'out_of_range', 'http_error'])
def test_bitview_rejects_corrupt_data(fault):
    from app.services.smart_insights.bitview import BitviewCollector
    with pytest.raises(CollectorUnavailable):
        BitviewCollector(transport=FixtureTransport(fault)).collect(datetime(2026, 9, 11, tzinfo=timezone.utc))


def test_bitview_missing_values_do_not_become_zero():
    from app.services.smart_insights.bitview import BitviewCollector
    rows = BitviewCollector(transport=FixtureTransport('null')).collect(datetime(2026, 9, 11, tzinfo=timezone.utc))
    assert not any(r.value['metric'] == 'crypto.onchain.nupl' for r in rows)


class FixtureTransport:
    def __init__(self, fault=None):
        self.fault = fault

    def fetch(self, url, **kwargs):
        from urllib.parse import urlsplit
        series = urlsplit(url).path.split('/')[-2]
        value = {'nupl': 0.3, 'supply_in_profit_share': 65, 'sopr_24h': 1.01,
                 'supply': 20, 'lth_supply': 15, 'sth_supply': 5,
                 'realized_price': 50000, 'lth_realized_price': 45000, 'sth_realized_price': 70000,
                 'utxos_under_1m_old_supply': 1, 'utxos_under_3m_old_supply': 2,
                 'utxos_under_6m_old_supply': 3, 'utxos_under_1y_old_supply': 4,
                 'utxos_under_2y_old_supply': 5, 'utxos_under_3y_old_supply': 6}.get(series, 1.5)
        data = ['2026-09-09', '2026-09-10', '2026-09-11'] if series == 'date' else [value] * 3
        payload = dict(version=1, index='day1', type='Date' if series == 'date' else 'StoredF32',
                       start=6460, end=6463, stamp='2026-09-11T12:00:00Z', data=data)
        if self.fault == 'wrong_index':
            payload['index'] = 'height'
        if self.fault == 'misaligned' and series == 'nupl':
            payload['start'] = 6459
        if self.fault == 'invalid_date' and series == 'date':
            payload['data'][0] = 'not-a-date'
        if series == 'nupl' and self.fault in ('invalid_number', 'null'):
            payload['data'] = ['NaN' if self.fault == 'invalid_number' else None] * 3
        if self.fault == 'out_of_range' and series == 'supply_in_profit_share':
            payload['data'] = [150] * 3
        return HttpResponse(503 if self.fault == 'http_error' else 200, url, json.dumps(payload).encode())


def test_onchain_read_model_keeps_holder_bands_provenance_and_full_history():
    from app.services.smart_insights.crypto_pulse import _onchain_tab
    rows = []
    for i in range(365):
        for band in range(7):
            rows.append(dict(id=f'{i}-{band}', source='bitview-onchain', symbol='BTC', dataClass='LIVE',
                             sourceUrl='https://bitview.space/api/series/supply/day1', checksum='a' * 64,
                             effectiveAt=(datetime(2025, 9, 11, tzinfo=timezone.utc) + timedelta(days=i)).isoformat(),
                             observedAt='2026-09-11T10:00:00Z', methodologyVersion='bitview-daily-v1',
                             value=dict(metric='crypto.onchain.hodl_waves', value='10', unit='%',
                                        dimensions=dict(dimension=f'band-{band}', label=f'band-{band}'))))
    group = next(g for g in _onchain_tab(rows)['groups'] if g['key'] == 'holders')
    assert len(group['series']) == 2555
    assert group['series'][0]['dimension'] == 'band-0'
    assert group['metrics'][0]['sourceUrl'].startswith('https://bitview.space/')
    assert group['metrics'][0]['checksum'] == 'a' * 64
