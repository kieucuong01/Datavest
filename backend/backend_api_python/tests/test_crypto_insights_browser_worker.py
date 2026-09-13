from __future__ import annotations

from datetime import datetime, timezone
import json
from zoneinfo import ZoneInfo

from app.services.smart_insights.browser_snapshots import load_snapshot, write_snapshot


NOW = datetime(2026, 8, 30, 2, 0, tzinfo=timezone.utc)


def _payload(source_code: str, records: list[dict[str, str]]) -> dict[str, object]:
    return {
        "source": source_code,
        "source_url": "https://example.test/source",
        "schema_version": 1,
        "fetched_at": NOW.isoformat(),
        "coverage": {
            "record_count": len(records),
            "oldest_effective_at": records[0]["effective_at"],
            "newest_effective_at": records[-1]["effective_at"],
        },
        "records": records,
    }


def _farside_records(value: str = "123000000") -> list[dict[str, str]]:
    return [
        {
            "effective_at": "2026-08-30T00:00:00+00:00",
            "metric": "crypto.etf.net_flow_usd",
            "value": value,
            "unit": "USD",
            "asset": "BTC",
            "fund": "TOTAL",
        }
    ]


def test_backfill_publishes_source_snapshot_and_reports_coverage(tmp_path):
    from crypto_insights_worker.browser_snapshots import backfill

    result = backfill(
        ("farside-btc-etf",),
        collect=lambda code, as_of: _payload(code, _farside_records()),
        root=tmp_path,
        as_of=NOW,
    )

    assert result["farside-btc-etf"] == {
        "status": "ok",
        "recordCount": 1,
        "oldestEffectiveAt": "2026-08-30T00:00:00+00:00",
        "newestEffectiveAt": "2026-08-30T00:00:00+00:00",
    }
    assert load_snapshot("farside-btc-etf", root=tmp_path, now=NOW)["records"][0]["value"] == "123000000"


def test_backfill_keeps_prior_snapshot_when_one_source_collector_crashes(tmp_path):
    write_snapshot("farside-btc-etf", _payload("farside-btc-etf", _farside_records("111")), root=tmp_path)
    from crypto_insights_worker.browser_snapshots import backfill

    result = backfill(
        ("farside-btc-etf",),
        collect=lambda code, as_of: (_ for _ in ()).throw(RuntimeError("layout changed")),
        root=tmp_path,
        as_of=NOW,
    )

    assert result["farside-btc-etf"]["status"] == "failed"
    assert result["farside-btc-etf"]["error"] == "UNEXPECTED:RuntimeError"
    assert load_snapshot("farside-btc-etf", root=tmp_path, now=NOW)["records"][0]["value"] == "111"


def test_daily_sources_are_caught_up_once_when_worker_starts_after_schedule():
    from crypto_insights_worker.browser_snapshots import due_snapshot_sources, scheduled_daily_sources

    seen: set[str] = set()
    after_schedule = datetime(2026, 9, 2, 9, 5, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))

    assert "cbbi-public" not in scheduled_daily_sources()
    assert due_snapshot_sources(after_schedule, seen) == scheduled_daily_sources()
    assert due_snapshot_sources(after_schedule, seen) == ()


def test_daily_sources_start_at_9am_vietnam_time():
    from crypto_insights_worker.browser_snapshots import due_snapshot_sources

    before_schedule: set[str] = set()
    at_schedule: set[str] = set()
    zone = ZoneInfo("Asia/Ho_Chi_Minh")

    assert due_snapshot_sources(datetime(2026, 9, 2, 8, 59, tzinfo=zone), before_schedule) == ()
    assert due_snapshot_sources(datetime(2026, 9, 2, 9, 0, tzinfo=zone), at_schedule)


def test_browser_batch_imports_successful_snapshots_immediately(monkeypatch):
    import asyncio

    from crypto_insights_worker import browser_snapshots as worker

    payloads = {
        source: _payload(source, _farside_records())
        for source in ("alternative-fng", "xoomar-btc-etf")
    }
    events: list[object] = []

    async def collect(source_code, _page, *, as_of):
        events.append(("collect", source_code))
        return {**payloads[source_code], "fetched_at": as_of.isoformat()}

    def write(source_code, _payload):
        events.append(("write", source_code))

    def notify(source_codes, *, observed_at):
        events.append(("import", tuple(source_codes), observed_at))
        assert any(event[0] == "write" for event in events)
        return {"status": "ok", "sourceCount": len(source_codes)}

    monkeypatch.setattr(worker, "collect_source", collect)
    monkeypatch.setattr(worker, "write_snapshot", write)
    monkeypatch.setattr(worker, "notify_snapshot_import", notify)

    result = asyncio.run(worker.browser_backfill(tuple(payloads)))

    assert result["alternative-fng"]["status"] == "ok"
    assert result["xoomar-btc-etf"]["status"] == "ok"
    assert result["import"] == {"status": "ok", "sourceCount": 2}
    assert [event[0] for event in events] == ["collect", "write", "collect", "write", "import"]


def test_browser_batch_does_not_import_when_all_sources_fail(monkeypatch):
    import asyncio

    from crypto_insights_worker import browser_snapshots as worker

    async def collect(_source_code, _page, *, as_of):
        del as_of
        raise worker.SnapshotUnavailable("SOURCE_DOWN")

    called = []

    monkeypatch.setattr(worker, "collect_source", collect)
    monkeypatch.setattr(worker, "notify_snapshot_import", lambda **_kwargs: called.append(True))

    result = asyncio.run(worker.browser_backfill(("xoomar-btc-etf",)))

    assert result["xoomar-btc-etf"] == {"status": "failed", "error": "SOURCE_DOWN"}
    assert result["import"] == {"status": "skipped", "reason": "no_successful_snapshots"}
    assert called == []


def test_snapshot_import_callback_posts_only_source_provenance(monkeypatch):
    from crypto_insights_worker import browser_snapshots as worker

    sent: list[tuple[object, int]] = []

    class Response:
        status = 202

        def read(self, _limit):
            return b'{"accepted":true}'

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_urlopen(request, timeout):
        sent.append((request, timeout))
        return Response()

    monkeypatch.setenv("CRYPTO_INSIGHTS_IMPORT_CALLBACK_URL", "http://127.0.0.1:5100/api/internal/smart-insights/snapshot-import")
    monkeypatch.setenv("CRYPTO_INSIGHTS_IMPORT_CALLBACK_SECRET", "callback-secret-for-tests")
    monkeypatch.setattr(worker, "urlopen", fake_urlopen)
    monkeypatch.setattr(worker.time, "time", lambda: 1_788_400_000)

    result = worker.notify_snapshot_import(("farside-btc-etf", "farside-btc-etf"), observed_at=NOW)

    assert result == {"status": "ok", "sourceCount": 1}
    assert len(sent) == 1
    request, timeout = sent[0]
    assert request.full_url.endswith("/api/internal/smart-insights/snapshot-import")
    assert timeout == 15
    assert json.loads(request.data.decode("utf-8")) == {
        "observedAt": NOW.isoformat(),
        "sourceCodes": ["farside-btc-etf"],
    }
    assert any("smart-insights-signature" in key.casefold() for key in request.headers)
    assert "callback-secret-for-tests" not in repr(request.headers)


def test_public_document_parsers_keep_history_and_current_metrics():
    from crypto_insights_worker.browser_snapshots import (
        parse_altcoin_season,
        parse_coinshares_report,
        parse_farside,
        parse_fear_greed,
    )

    fear_greed = parse_fear_greed(
        json.dumps({"data": [{"value": "67", "value_classification": "Greed", "timestamp": "1788048000"}]})
    )
    assert fear_greed == [
        {
            "effective_at": "2026-08-30T00:00:00+00:00",
            "metric": "crypto.fear_greed.index",
            "value": "67",
            "unit": "index",
            "classification": "Greed",
        }
    ]

    etf = parse_farside("BTC", [["Date", "IBIT", "Total"], ["29 Aug 2026", "101.2", "123.4"]])
    assert etf[0]["value"] == "123400000.0"
    assert etf[0]["asset"] == "BTC"

    altcoin = parse_altcoin_season("Altcoin Season (61) Month (43) Year (37)")
    assert {(row["metric"], row["value"]) for row in altcoin} == {
        ("crypto.cycle.altcoin_season.index", "61"),
        ("crypto.cycle.altcoin_season.month_index", "43"),
        ("crypto.cycle.altcoin_season.year_index", "37"),
    }


def test_altcoin_season_parser_imports_historical_scores_and_provider_statistics():
    from crypto_insights_worker.browser_snapshots import parse_altcoin_season, parse_coinshares_report

    payload = {
        "score": {
            "30": {"2026-08-29": "33", "2026-08-30": "35"},
            "90": {"2026-08-29": "29", "2026-08-30": "31"},
            "365": {"2026-08-29": "35", "2026-08-30": "35"},
        },
        "stats": {
            "90": {
                "days_since_last_alt": 338,
                "days_since_last_btc": 103,
                "avg_gap_alt_to_alt": 67.4,
                "avg_gap_btc_to_btc": 20.3,
                "longest_no_alt_streak": 486,
                "longest_no_btc_streak": 308,
                "avg_alt_run": 16.6,
                "avg_btc_run": 10.1,
                "max_alt_run": 117,
                "max_btc_run": 126,
                "altseasondays": 416,
                "bitcoinseasondays": 955,
            }
        },
    }
    serialized = json.dumps(payload).replace('"', '\\"')
    records = parse_altcoin_season(f'Altcoin Season (31) Month (35) Year (35) <script>{serialized}</script>')

    index_history = [row for row in records if row["metric"] == "crypto.cycle.altcoin_season.index"]
    assert [(row["effective_at"], row["value"]) for row in index_history] == [
        ("2026-08-29T00:00:00+00:00", "29"),
        ("2026-08-30T00:00:00+00:00", "31"),
    ]
    assert {row["metric"] for row in records} >= {
        "crypto.cycle.altcoin_season.stat.days_since_last_alt",
        "crypto.cycle.altcoin_season.stat.avg_gap_alt_to_alt",
        "crypto.cycle.altcoin_season.stat.max_alt_run",
    }

    coinshares = parse_coinshares_report(
        "Digital asset investment products saw inflows totalling US$1.03bn last week.",
        "https://coinshares.com/insights/research-data/fund-flows-25-8-2026/",
    )
    assert coinshares == [
        {
            "effective_at": "2026-08-25T00:00:00+00:00",
            "metric": "crypto.coinshares.net_flow_usd",
            "value": "1030000000",
            "unit": "USD",
            "dimension": "total",
            "label": "Total",
        }
    ]


def test_api_parsers_normalize_free_etf_flow_history_without_mixing_assets():
    from crypto_insights_worker.browser_snapshots import parse_cryptoetf, parse_xoomar

    cryptoetf = parse_cryptoetf("SOL", {
        "symbol": "SOL",
        "days": [
            {"date": "2026-08-28", "netFlowUsdM": 17.3},
            {"date": "2026-08-29", "netFlowUsdM": -2.5},
        ],
    })
    assert cryptoetf == [
        {"effective_at": "2026-08-28T00:00:00+00:00", "metric": "crypto.etf.net_flow_usd", "value": "17300000.0", "unit": "USD", "asset": "SOL", "fund": "TOTAL"},
        {"effective_at": "2026-08-29T00:00:00+00:00", "metric": "crypto.etf.net_flow_usd", "value": "-2500000.0", "unit": "USD", "asset": "SOL", "fund": "TOTAL"},
    ]

    xoomar = parse_xoomar("BTC", {
        "data": [
            {"date": "2026-08-28", "flowUsd": "12000000"},
            {"date": "2026-08-28", "flowUsd": "-2000000"},
            {"date": "2026-08-29", "flowUsd": None},
        ],
    })
    assert xoomar == [
        {"effective_at": "2026-08-28T00:00:00+00:00", "metric": "crypto.etf.net_flow_usd", "value": "10000000", "unit": "USD", "asset": "BTC", "fund": "TOTAL"},
    ]


def test_browser_evaluation_decoder_accepts_browser_use_python_mapping_text():
    from crypto_insights_worker.browser_snapshots import _decode

    assert _decode("{'data': [{'value': '69', 'timestamp': '1788048000'}]}") == {
        "data": [{"value": "69", "timestamp": "1788048000"}]
    }


def test_fear_greed_parser_accepts_browser_use_python_mapping_text():
    from crypto_insights_worker.browser_snapshots import parse_fear_greed

    assert parse_fear_greed("{'data': [{'value': '69', 'value_classification': 'Greed', 'timestamp': '1788048000'}]}")[0]["value"] == "69"


def test_prepare_browser_profile_removes_only_stale_chromium_singleton_locks(tmp_path):
    from crypto_insights_worker.browser_snapshots import prepare_browser_profile

    for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        (tmp_path / name).write_text("stale", encoding="utf-8")
    (tmp_path / "Cookies").write_text("preserve", encoding="utf-8")

    assert prepare_browser_profile(tmp_path) == tmp_path.resolve()
    assert not any((tmp_path / name).exists() for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"))
    assert (tmp_path / "Cookies").read_text(encoding="utf-8") == "preserve"


def test_bitinfocharts_parser_builds_a_heuristic_non_exchange_cohort_with_daily_delta():
    from crypto_insights_worker.browser_snapshots import parse_bitinfocharts_rich_list

    rows = []
    for rank in range(1, 101):
        rows.append({
            "rank": str(rank),
            "address": f"bc1q{'%030d' % rank}",
            "balance": "1,500 BTC",
            "label": "Binance-coldwallet" if rank == 1 else "",
        })

    records = parse_bitinfocharts_rich_list(
        rows,
        as_of=NOW,
        previous_balances={f"bc1q{'%030d' % rank}": 1490 for rank in range(2, 101)},
    )

    metric_values = {record["metric"]: record["value"] for record in records if "address" not in record}
    assert metric_values["crypto.large_address.tracked_address_count"] == "100"
    assert metric_values["crypto.large_address.excluded_address_count"] == "1"
    assert metric_values["crypto.large_address.balance_change_btc"] == "990"
    assert metric_values["crypto.large_address.matched_balance_change_btc"] == "990"
    assert metric_values["crypto.large_address.balance_increase_btc"] == "990"
    assert metric_values["crypto.large_address.balance_decrease_btc"] == "0"
    assert metric_values["crypto.large_address.accumulating_address_count"] == "99"
    assert metric_values["crypto.large_address.distributing_address_count"] == "0"
    assert metric_values["crypto.large_address.matched_address_count"] == "99"
    address_rows = [record for record in records if record["metric"] == "crypto.large_address.address_balance_btc"]
    assert len(address_rows) == 99
    assert address_rows[0]["quality_tier"] == "heuristic"
    delta_rows = [record for record in records if record["metric"] == "crypto.large_address.address_balance_change_btc"]
    assert len(delta_rows) == 99
    assert delta_rows[0]["value"] == "10"


def test_bitinfocharts_detail_parser_keeps_lifetime_context_separate_from_daily_flow():
    from crypto_insights_worker.browser_snapshots import parse_bitinfocharts_detail

    detail = parse_bitinfocharts_detail(
        "Balance: 1,500 BTC Received: 2,000 BTC (12,345 ins), last: 2026-08-30 "
        "Sent: 500 BTC (321 outs), last: 2026-08-29 Unspent outputs: 42"
    )

    assert detail["received_total"] == 2000
    assert detail["sent_total"] == 500
    assert detail["received_count"] == 12345
    assert detail["sent_count"] == 321
    assert detail["unspent_outputs"] == 42
    assert detail["last_activity"].isoformat() == "2026-08-30"
