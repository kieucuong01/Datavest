"""Weekly report validity and bounded recovery of unowned/terminal jobs."""
from datetime import date, datetime, timedelta, timezone
from app.utils.timeutil import vietnam_calendar_date

RETRYABLE_FAILURES = ('dispatch_failed', 'creation_failed', 'trading_agents_failed', 'trading_agents_cancelled')
RETRY_SQL = """
{table}.attempt_count < 3
AND {table}.updated_at <= NOW() - INTERVAL '15 minutes'
AND (({table}.status = 'failed' AND {table}.failure_code IN
      ('dispatch_failed', 'creation_failed', 'trading_agents_failed', 'trading_agents_cancelled'))
     OR ({table}.status = 'pending' AND {table}.source_run_id IS NULL
         AND {table}.updated_at <= NOW() - INTERVAL '3 hours'))
"""


def can_retry(row, *, now=None):
    now = now or datetime.now(timezone.utc)
    updated = row.get('updated_at')
    if not updated:
        return False
    if not isinstance(updated, datetime):
        updated = datetime.fromisoformat(str(updated).replace('Z', '+00:00'))
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    age = now - updated
    if int(row.get('attempt_count') or 1) >= 3 or age < timedelta(minutes=15):
        return False
    return (row.get('status') == 'failed' and row.get('failure_code') in RETRYABLE_FAILURES) or (
        row.get('status') == 'pending' and not row.get('source_run_id') and age >= timedelta(hours=3))


def report_validity(effective_date, *, today=None):
    effective = date.fromisoformat(str(effective_date)[:10])
    monday = effective - timedelta(days=effective.weekday())
    end = monday + timedelta(days=7)
    current = today or date.fromisoformat(vietnam_calendar_date())
    expired = current >= end
    return {'validUntil': f'{end.isoformat()}T00:00:00+07:00',
            'isExpired': expired, 'actionable': monday <= current < end,
            'freshness': 'STALE' if expired else 'FUTURE' if current < monday else 'FRESH'}
