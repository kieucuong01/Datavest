"""Atomic owner-scoped revision storage. Old revisions are immutable evidence."""
from datetime import datetime, timezone
import json
from uuid import uuid4
from zoneinfo import ZoneInfo
from app.utils.db import get_db_connection
from .ledger import fingerprint, replay_ledger, timestamp

class BookNotFound(LookupError): pass
class BookConflict(ValueError): pass

class LedgerRepository:
    def __init__(self, connection=get_db_connection): self.connection = connection
    def _owned(self, cur, user_id, book_id, lock=False):
        cur.execute('SELECT * FROM qd_portfolio_books WHERE id=? AND user_id=?' + (' FOR UPDATE' if lock else ''), (book_id, user_id))
        row = cur.fetchone()
        if not row: raise BookNotFound('Book not found')
        return dict(row)
    def _events(self, cur, book_id, revision):
        if not revision: return []
        cur.execute('SELECT events_json FROM qd_portfolio_ledger_revisions WHERE book_id=? AND revision=?', (book_id, revision))
        return json.loads(cur.fetchone()['events_json'])
    def create(self, user_id, name, currency, now):
        book = dict(id=str(uuid4()), user_id=user_id, name=name, currency=currency, revision=0, created_at=now.isoformat())
        with self.connection() as db:
            cur = db.cursor()
            cur.execute('INSERT INTO qd_portfolio_books(id,user_id,name,currency,created_at) VALUES(?,?,?,?,?)', (book['id'], user_id, name, currency, book['created_at']))
            db.commit(); cur.close()
        return book
    def list_owned(self, user_id):
        with self.connection() as db:
            cur = db.cursor(); cur.execute('SELECT * FROM qd_portfolio_books WHERE user_id=? ORDER BY created_at,id', (user_id,))
            rows = cur.fetchall(); cur.close()
            return [dict(row) for row in rows]
    def load_owned(self, user_id, book_id):
        with self.connection() as db:
            cur = db.cursor(); book = self._owned(cur, user_id, book_id)
            book['events'] = self._events(cur, book_id, book['revision']); cur.close()
            return book
    @staticmethod
    def _validate_request(expected_revision, request_key):
        if not isinstance(request_key, str) or not 1 <= len(request_key) <= 100: raise ValueError('requestKey is required, max 100 characters')
        if not isinstance(expected_revision, int) or isinstance(expected_revision, bool): raise ValueError('expectedRevision must be integer')
    @staticmethod
    def _replayed(cur, book_id, request_key, request_hash):
        cur.execute('SELECT revision,request_hash FROM qd_portfolio_ledger_revisions WHERE book_id=? AND request_key=?', (book_id, request_key))
        prior = cur.fetchone()
        if prior:
            if prior['request_hash'] != request_hash: raise BookConflict('requestKey already used with a different payload')
            return {'id': book_id, 'revision': prior['revision'], 'replayedRequest': True}
    def replay_request(self, user_id, book_id, expected_revision, request_key, command):
        self._validate_request(expected_revision, request_key)
        with self.connection() as db:
            cur = db.cursor(); self._owned(cur, user_id, book_id)
            result = self._replayed(cur, book_id, request_key, fingerprint(command)); cur.close()
            return result
    def mutate(self, user_id, book_id, expected_revision, request_key, events=(), replacements=None, command=None):
        self._validate_request(expected_revision, request_key)
        request_hash = fingerprint(command if command is not None else {'events': events, 'replacements': replacements})
        with self.connection() as db:
            cur = db.cursor(); book = self._owned(cur, user_id, book_id, lock=True)
            replayed = self._replayed(cur, book_id, request_key, request_hash)
            if replayed: cur.close(); return replayed
            if book['revision'] != expected_revision: raise BookConflict('Book changed; reload before saving')
            current = self._events(cur, book_id, book['revision'])
            ids = {row['eventId'] for row in current}
            dirty_dates = []
            for event_id, replacement in (replacements or {}).items():
                if event_id not in ids: raise BookNotFound('Event not found')
                old = next(row for row in current if row['eventId'] == event_id)
                dirty_dates.append(timestamp(old['effectiveAt']).astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date().isoformat())
                replacement = {**replacement, 'sequence': old['sequence']}
                current = [replacement if row['eventId'] == event_id else row for row in current]
                dirty_dates.append(timestamp(replacement['effectiveAt']).astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date().isoformat())
            for row in events:
                if row['eventId'] in ids: raise ValueError('Duplicate eventId')
                ids.add(row['eventId']); current.append({**row, 'sequence': len(current)})
                dirty_dates.append(timestamp(row['effectiveAt']).astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date().isoformat())
            if not dirty_dates: raise ValueError('At least one event is required')
            state = replay_ledger(current) # validates later sells/cash after historical edits
            revision = book['revision'] + 1
            cur.execute('INSERT INTO qd_portfolio_ledger_revisions(book_id,revision,request_key,request_hash,events_json,created_at) VALUES(?,?,?,?,?,?)', (book_id, revision, request_key, request_hash, json.dumps(current), datetime.now(timezone.utc).isoformat()))
            for row in current:
                cur.execute('INSERT INTO qd_portfolio_ledger_entries(book_id,revision,event_id,effective_at,quantity,unit_price,amount,fee,tax,event_json) VALUES(?,?,?,?,?,?,?,?,?,?)', (book_id, revision, row['eventId'], row['effectiveAt'], row['quantity'], row['unitPrice'], row['amount'], row['fee'], row['tax'], json.dumps(row)))
            dirty = min(dirty_dates + ([book['dirty_from']] if book.get('dirty_from') else []))
            cur.execute('UPDATE qd_portfolio_books SET revision=?,dirty_from=? WHERE id=? AND user_id=?', (revision, dirty, book_id, user_id))
            self.carry_nav(cur,book_id,book['revision'],revision,dirty)
            cur.execute('DELETE FROM qd_portfolio_nav_retries WHERE book_id=? AND revision<>?', (book_id,revision))
            db.commit(); cur.close()
            return {'id': book_id, 'revision': revision, 'state': state}
    def carry_nav(self, cur, book_id, old_revision, new_revision, dirty):
        cur.execute('SELECT day,snapshot_json,created_at FROM qd_portfolio_nav_snapshots WHERE book_id=? AND revision=? AND day<?', (book_id,old_revision,dirty))
        for row in cur.fetchall():
            snapshot = json.loads(row['snapshot_json'])
            snapshot.update(ledgerRevision=new_revision,derivedFromRevision=old_revision)
            snapshot['checksum'] = fingerprint({k:v for k,v in snapshot.items() if k != 'checksum'})
            cur.execute('INSERT INTO qd_portfolio_nav_snapshots(book_id,day,revision,snapshot_json,created_at) VALUES(?,?,?,?,?)', (book_id,row['day'],new_revision,json.dumps(snapshot),datetime.now(timezone.utc).isoformat()))
            if snapshot.get('nav') is None:
                cur.execute('INSERT INTO qd_portfolio_nav_retries(book_id,day,revision,next_due) VALUES(?,?,?,?)', (book_id,row['day'],new_revision,row['created_at']))
    def revisions(self, user_id, book_id, event_id):
        with self.connection() as db:
            cur = db.cursor(); self._owned(cur, user_id, book_id)
            cur.execute('SELECT revision,event_json FROM qd_portfolio_ledger_entries WHERE book_id=? AND event_id=? ORDER BY revision', (book_id, event_id))
            return [{'revision': row['revision'], 'event': json.loads(row['event_json'])} for row in cur.fetchall()]
    def opening_positions(self, user_id, ids):
        if not isinstance(ids, list) or not 1 <= len(ids) <= 200 or any(not isinstance(i, int) for i in ids): raise ValueError('Select 1..200 positions')
        with self.connection() as db:
            cur = db.cursor(); cur.execute('SELECT * FROM qd_manual_positions WHERE user_id=? AND id IN (' + ','.join('?' for _ in ids) + ') ORDER BY id', (user_id, *ids))
            rows = [dict(row) for row in cur.fetchall()]
            if len(rows) != len(set(ids)): raise BookNotFound('Position not found')
            return rows
