"""Manual audited backfill: python -m app.tools.refresh_bitview --days 370."""
import argparse
from datetime import datetime, timezone
import json

from app.services.smart_insights.bitview import BitviewCollector
from app.services.smart_insights.collectors import RefreshCoordinator
from app.services.smart_insights.repository import SmartInsightsRepository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days', type=int, default=370, choices=range(1, 731), metavar='1..730')
    args = parser.parse_args()
    repository = SmartInsightsRepository()
    run_id = repository.create_refresh_request(requested_by_user_id=None, market='crypto', source_codes=('bitview-onchain',))
    result = RefreshCoordinator(repository=repository, collector_registry={
        'bitview-onchain': lambda: BitviewCollector(history_days=args.days).collect(datetime.now(timezone.utc)),
    }).execute(run_id)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
