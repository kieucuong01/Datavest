from __future__ import annotations

from datetime import date


class FakeRepository:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.claims = set()

    def current(self, *, asset_key, report_kind, locale, period_key):
        return next(
            (
                row
                for row in self.rows
                if row["asset_key"] == asset_key
                and row["report_kind"] == report_kind
                and row["locale"] == locale
                and row["period_key"] == period_key
            ),
            None,
        )

    def latest_completed(self, *, asset_key, report_kind, locale):
        matches = [
            row
            for row in self.rows
            if row["asset_key"] == asset_key
            and row["report_kind"] == report_kind
            and row["locale"] == locale
            and row["status"] == "complete"
        ]
        return max(matches, key=lambda row: row["period_key"], default=None)

    def claim_pending(self, *, asset_key, report_kind, locale, period_key):
        key = (asset_key, report_kind, locale, period_key)
        if key in self.claims or self.current(
            asset_key=asset_key, report_kind=report_kind, locale=locale, period_key=period_key
        ):
            return False
        self.claims.add(key)
        self.rows.append({
            "asset_key": asset_key,
            "report_kind": report_kind,
            "locale": locale,
            "period_key": period_key,
            "status": "pending",
            "payload": {},
            "generated_at": None,
        })
        return True


def _row(*, period_key="2026-09-14", status="complete", payload=None):
    return {
        "asset_key": "crypto:ETH/USDT",
        "report_kind": "quick",
        "locale": "vi-VN",
        "period_key": period_key,
        "status": status,
        "generated_at": "2026-09-14T07:15:00+07:00",
        "payload": payload or {"summary": "Shared ETH", "runId": "private-run"},
    }


def test_period_keys_use_vietnam_calendar_day_and_monday_week():
    from app.services.smart_insights.shared_reports import reporting_period_key

    today = date(2026, 9, 16)  # Wednesday

    assert reporting_period_key("quick", today=today) == "2026-09-16"
    assert reporting_period_key("deep", today=today) == "2026-09-14"


def test_private_shared_report_claims_only_once_for_same_asset_and_period():
    from app.services.smart_insights.shared_reports import SharedResearchReportsService

    repository = FakeRepository()
    service = SharedResearchReportsService(repository=repository)

    first = service.claim("crypto:ETH/USDT", "quick", today=date(2026, 9, 16))
    second = service.claim("crypto:ETH/USDT", "quick", today=date(2026, 9, 16))

    assert first["claimed"] is True
    assert second["claimed"] is False
    assert second["status"] == "pending"


def test_shared_projection_excludes_private_run_and_request_metadata():
    from app.services.smart_insights.shared_reports import SharedResearchReportsService

    service = SharedResearchReportsService(repository=FakeRepository([_row(payload={
        "summary": "Sanitized report",
        "decision": "BUY",
        "sourceRunId": "hidden",
        "request": {"userId": 9},
        "artifactPath": "/private/report.md",
    })]))

    state = service.state("crypto:ETH/USDT", "quick", today=date(2026, 9, 14))

    assert state["status"] == "complete"
    assert state["report"]["summary"] == "Sanitized report"
    assert "sourceRunId" not in state["report"]
    assert "request" not in state["report"]
    assert "artifactPath" not in state["report"]


def test_current_period_missing_keeps_latest_report_but_allows_new_generation():
    from app.services.smart_insights.shared_reports import SharedResearchReportsService

    service = SharedResearchReportsService(repository=FakeRepository([_row(period_key="2026-09-15")]))

    state = service.state("crypto:ETH/USDT", "quick", today=date(2026, 9, 16))

    assert state["status"] == "missing"
    assert state["canCreate"] is True
    assert state["report"]["effectiveDate"] == "2026-09-15"


class FakePublicRepository:
    def current(self, **_kwargs):
        return None

    def latest_completed(self, **_kwargs):
        return None

    def claim_pending(self, **_kwargs):
        return True


def test_non_common_asset_is_visible_only_to_accounts_currently_watching_it():
    from app.services.smart_insights.shared_research_access import SharedResearchAccessService

    dispatched = []
    service = SharedResearchAccessService(
        watchlist_loader=lambda user_id: [{"market": "Crypto", "symbol": "ETH/USDT", "name": "Ethereum"}] if user_id == 7 else [],
        public_repository=FakePublicRepository(),
        shared_repository=FakeRepository(),
        dispatch=lambda *args: dispatched.append(args),
    )

    result = service.request(
        user_id=7, asset_key="crypto:ETH/USDT", report_kind="quick", today=date(2026, 9, 16)
    )

    assert result["scope"] == "shared_watchlist"
    assert result["claimed"] is True
    assert dispatched[0][0] == "shared_watchlist"
    try:
        service.state(user_id=8, asset_key="crypto:ETH/USDT", report_kind="quick", today=date(2026, 9, 16))
    except ValueError as exc:
        assert str(exc) == "shared_report_not_found"
    else:
        raise AssertionError("a user without the asset must not read shared research")
