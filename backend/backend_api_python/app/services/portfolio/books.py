from datetime import datetime, timezone
import csv
import io
from uuid import UUID, uuid5
from .ledger import normalize_event, replay_ledger, fingerprint
from .ledger_repository import LedgerRepository, BookConflict
from .positions import quote_currency

class BooksService:
    def __init__(self, repository=None, clock=None):
        self.repo = repository or LedgerRepository()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
    def create(self, user_id, payload):
        name, currency = str(payload.get('name') or '').strip(), payload.get('currency')
        if not 1 <= len(name) <= 100 or currency not in {'VND', 'USD', 'USDT'}: raise ValueError('Name and supported currency are required')
        return self.repo.create(user_id, name, currency, self.clock())
    def state(self, user_id, book_id):
        book = self.repo.load_owned(user_id, book_id)
        return {**book, 'state': replay_ledger(book['events'])}
    def _events(self, book, payload):
        rows = payload.get('events')
        if not isinstance(rows, list) or not 1 <= len(rows) <= 1000: raise ValueError('Provide 1..1000 events')
        return [normalize_event({**row, 'eventId': row.get('eventId') or str(uuid5(UUID(book['id']), str(payload.get('requestKey')) + ':' + str(n)))}, book['currency'], now=self.clock()) for n, row in enumerate(rows)]
    def append(self, user_id, book_id, payload):
        book = self.repo.load_owned(user_id, book_id)
        return self.repo.mutate(user_id, book_id, payload.get('expectedRevision'), payload.get('requestKey'), self._events(book, payload))
    def revise(self, user_id, book_id, event_id, payload):
        book = self.repo.load_owned(user_id, book_id)
        old = next((r for r in book['events'] if r['eventId'] == event_id), None)
        if old is None: raise ValueError('Event not found')
        if payload.get('cancelled') is True:
            # Canonical cancellation is independent of the current edited version.
            row = {'eventId': event_id, 'cancelled': True, 'type': old['type'], 'effectiveAt': old['effectiveAt'], **{k: old[k] for k in ('market','symbol','quantity','unitPrice','amount','fee','tax','notes')}}
        else: row = normalize_event({**payload.get('event', {}), 'eventId': event_id}, book['currency'], now=self.clock())
        return self.repo.mutate(user_id, book_id, payload.get('expectedRevision'), payload.get('requestKey'), replacements={event_id: row})
    def csv_preview(self, user_id, book_id, payload):
        book = self.repo.load_owned(user_id, book_id)
        text = payload.get('csv')
        if not isinstance(text, str) or len(text.encode('utf-8')) > 1048576: raise ValueError('CSV must be UTF-8 text, maximum 1 MB')
        reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
        if not {'type', 'effectiveAt'} <= set(reader.fieldnames or []): raise ValueError('CSV requires type,effectiveAt headers')
        rows, errors = [], []
        for line, raw in enumerate(reader, 2):
            if line > 1001: raise ValueError('Maximum 1000 CSV rows')
            try:
                if None in raw: raise ValueError('Too many columns')
                event = normalize_event(raw, book['currency'], now=self.clock())
                rows.append(event)
            except ValueError as exc: errors.append({'line': line, 'message': str(exc)})
        state = None
        if not rows and not errors: errors.append({'line': 2, 'message': 'No events'})
        if not errors:
            try: state = replay_ledger(book['events'] + [{**row, 'sequence': len(book['events']) + n} for n,row in enumerate(rows)])
            except ValueError as exc: errors.append({'line': None, 'message': str(exc)})
        return {'valid': not errors, 'errors': errors, 'events': rows, 'state': state, 'fingerprint': fingerprint(text), 'revision': book['revision']}
    def csv_commit(self, user_id, book_id, payload):
        text = payload.get('csv')
        if not isinstance(text, str) or len(text.encode('utf-8')) > 1048576: raise ValueError('CSV must be UTF-8 text, maximum 1 MB')
        # Rebuild deterministic IDs for blank eventId, enabling safe request retries.
        raw_rows = list(csv.DictReader(io.StringIO(payload['csv'].lstrip('\ufeff'))))
        return self.append(user_id, book_id, {**payload, 'events': raw_rows})
    def opening_preview(self, user_id, book_id, payload):
        book = self.repo.load_owned(user_id, book_id)
        if book['revision']: raise ValueError('Opening balances require an empty book')
        rows = self.repo.opening_positions(user_id, payload.get('positionIds'))
        events = []
        for row in rows:
            if row.get('side') != 'long' or quote_currency(row) != book['currency']: raise ValueError('Only same-currency long positions may be opened')
            events.append({'type': 'opening_position', 'market': row['market'], 'symbol': row['symbol'], 'quantity': str(row['quantity']), 'unitPrice': str(row['entry_price']), 'effectiveAt': payload.get('effectiveAt'), 'notes': 'Opening manual position ' + str(row['id'])})
        if payload.get('cash') and str(payload['cash']) != '0': events.insert(0, {'type': 'deposit', 'amount': payload['cash'], 'effectiveAt': payload.get('effectiveAt')})
        normalized = self._events(book, {**payload, 'events': events})
        return {'events': normalized, 'state': replay_ledger(normalized), 'fingerprint': fingerprint({'positions': rows, 'cash': payload.get('cash'), 'effectiveAt': payload.get('effectiveAt')})}
    def opening_commit(self, user_id, book_id, payload):
        preview = self.opening_preview(user_id, book_id, payload)
        if preview['fingerprint'] != payload.get('fingerprint'): raise BookConflict('Opening balances changed; preview again')
        return self.repo.mutate(user_id, book_id, payload.get('expectedRevision'), payload.get('requestKey'), preview['events'])
