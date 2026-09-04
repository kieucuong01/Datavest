import unittest
from unittest.mock import patch

from app.services import portfolio_monitor


class DailyWatchlistAiAnalysisTests(unittest.TestCase):
    def test_system_daily_watchlist_monitor_is_marked_and_uses_a_7am_daily_cadence(self):
        config = portfolio_monitor.build_system_daily_watchlist_monitor_config(
            market="Crypto",
            symbol="BTC/USDT",
            language="vi-VN",
        )

        self.assertEqual(config["schedule_kind"], portfolio_monitor.SYSTEM_DAILY_WATCHLIST_SCHEDULE)
        self.assertEqual(config["run_interval_minutes"], 24 * 60)
        self.assertEqual(config["market"], "Crypto")
        self.assertEqual(config["symbol"], "BTC/USDT")
        self.assertEqual(config["language"], "vi-VN")
        self.assertTrue(portfolio_monitor.is_system_daily_watchlist_monitor(config))


    def test_user_defined_monitor_is_not_mistaken_for_the_system_daily_schedule(self):
        self.assertFalse(portfolio_monitor.is_system_daily_watchlist_monitor({
            "market": "Crypto",
            "symbol": "BTC/USDT",
            "run_interval_minutes": 24 * 60,
        }))

    def test_updating_a_personal_schedule_keeps_its_asset_identity(self):
        merged = portfolio_monitor.merge_user_monitor_config(
            {"market": "Crypto", "symbol": "BTC/USDT", "language": "vi-VN", "run_interval_minutes": 240},
            {"run_interval_minutes": 60},
        )

        self.assertEqual(merged["market"], "Crypto")
        self.assertEqual(merged["symbol"], "BTC/USDT")
        self.assertEqual(merged["language"], "vi-VN")
        self.assertEqual(merged["run_interval_minutes"], 60)
        self.assertNotIn("schedule_kind", merged)

    def test_daily_runner_analyses_every_watched_asset_and_keeps_personal_schedules_separate(self):
        rows = [
            {"user_id": 7, "market": "Crypto", "symbol": "BTC/USDT", "name": "Bitcoin"},
            {"user_id": 7, "market": "Forex", "symbol": "XAUUSD", "name": "Gold"},
        ]

        class Cursor:
            def execute(self, *_args, **_kwargs):
                return None

            def fetchall(self):
                return rows

            def close(self):
                return None

        class Database:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def cursor(self):
                return Cursor()

        ensured = []
        executed = []
        with (
            patch.object(portfolio_monitor, "get_db_connection", return_value=Database()),
            patch.object(
                portfolio_monitor,
                "ensure_system_daily_watchlist_monitor",
                side_effect=lambda **asset: ensured.append(asset) or len(ensured),
            ),
            patch.object(
                portfolio_monitor,
                "run_single_monitor",
                side_effect=lambda monitor_id, **kwargs: executed.append((monitor_id, kwargs)) or {"success": True},
            ),
        ):
            outcome = portfolio_monitor.run_daily_watchlist_ai_analysis()

        self.assertEqual(outcome["completed"], 2)
        self.assertEqual(outcome["failed"], 0)
        self.assertEqual([item["symbol"] for item in ensured], ["BTC/USDT", "XAUUSD"])
        self.assertEqual(executed, [
            (1, {"user_id": 7, "skip_notification": True}),
            (2, {"user_id": 7, "skip_notification": True}),
        ])
