from __future__ import annotations

import pytest


class FakeRepository:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def latest_completed(self, *, asset_key, report_kind, locale):
        matches = [
            row for row in self.rows
            if row["asset_key"] == asset_key
            and row["report_kind"] == report_kind
            and row["locale"] == locale
            and row["status"] == "complete"
        ]
        return max(matches, key=lambda row: row["effective_date"], default=None)

    def latest_status(self, *, asset_key, report_kind, locale):
        matches = [
            row for row in self.rows
            if row["asset_key"] == asset_key
            and row["report_kind"] == report_kind
            and row["locale"] == locale
        ]
        return max(matches, key=lambda row: row["effective_date"], default=None)

    def list_completed(self, *, asset_key, report_kind, locale, limit):
        matches = [
            row for row in self.rows
            if row["asset_key"] == asset_key
            and row["report_kind"] == report_kind
            and row["locale"] == locale
            and row["status"] == "complete"
        ]
        return sorted(matches, key=lambda row: row["effective_date"], reverse=True)[:limit]


def _row(*, effective_date, status="complete", payload=None):
    return {
        "asset_key": "crypto:BTC/USDT",
        "report_kind": "deep",
        "locale": "vi-VN",
        "effective_date": effective_date,
        "status": status,
        "generated_at": f"{effective_date}T07:15:00+07:00",
        "payload": payload or {"title": "BTC", "summary": "Công khai", "prompt": "private"},
    }


def test_latest_rejects_assets_outside_the_fixed_public_scope():
    from app.services.smart_insights.public_reports import PublicResearchReportsService

    service = PublicResearchReportsService(repository=FakeRepository())

    with pytest.raises(ValueError, match="unsupported_public_asset"):
        service.get_latest("crypto:ETH/USDT", "deep")


def test_public_research_rejects_retired_quick_reports():
    from app.services.smart_insights.public_reports import PublicResearchReportsService

    service = PublicResearchReportsService(repository=FakeRepository())

    with pytest.raises(ValueError, match="unsupported_public_report_kind"):
        service.get_latest("crypto:BTC/USDT", "quick")


def test_failed_current_period_returns_the_previous_completed_projection():
    from app.services.smart_insights.public_reports import PublicResearchReportsService

    service = PublicResearchReportsService(repository=FakeRepository([
        _row(effective_date="2026-09-12"),
        _row(effective_date="2026-09-13", status="failed"),
    ]))

    result = service.get_latest("crypto:BTC/USDT", "deep")

    assert result["effectiveDate"] == "2026-09-12"
    assert result["isFallback"] is True
    assert result["title"] == "BTC"


def test_latest_returns_the_public_report_when_the_ui_locale_is_not_vietnamese():
    from app.services.smart_insights.public_reports import PublicResearchReportsService

    service = PublicResearchReportsService(repository=FakeRepository([
        _row(effective_date="2026-09-13"),
    ]))

    result = service.get_latest("crypto:BTC/USDT", "deep", locale="en-US")

    assert result["summary"] == "Công khai"
    assert result["locale"] == "vi-VN"


def test_public_projection_drops_internal_payload_fields():
    from app.services.smart_insights.public_reports import PublicResearchReportsService

    result = PublicResearchReportsService.public_projection(_row(
        effective_date="2026-09-13",
        payload={
            "title": "BTC",
            "summary": "An toàn",
            "body": "Nội dung công khai",
            "prompt": "secret",
            "runId": "private-run",
            "storagePath": "/private/path",
        },
    ))

    assert result == {
        "assetKey": "crypto:BTC/USDT",
        "reportKind": "deep",
        "locale": "vi-VN",
        "effectiveDate": "2026-09-13",
        "generatedAt": "2026-09-13T07:15:00+07:00",
        "title": "BTC",
        "summary": "An toàn",
        "body": "Nội dung công khai",
        "isFallback": False,
    }


def test_public_projection_reads_the_postgres_payload_json_column():
    from app.services.smart_insights.public_reports import PublicResearchReportsService

    row = _row(effective_date="2026-09-13")
    row.pop("payload", None)
    row["payload_json"] = {
        "title": "BTC",
        "summary": "Nội dung từ payload_json",
        "body": "Báo cáo chuyên sâu",
        "sections": [{"title": "Luận điểm", "items": ["Dữ liệu đã được lưu"]}],
        "decision": "BUY",
        "confidence": 78,
    }

    result = PublicResearchReportsService.public_projection(row)

    assert result["summary"] == "Nội dung từ payload_json"
    assert result["body"] == "Báo cáo chuyên sâu"
    assert result["sections"][0]["items"] == ["Dữ liệu đã được lưu"]


def test_history_returns_safe_public_entries_without_private_run_identifiers_or_body():
    from app.services.smart_insights.public_reports import PublicResearchReportsService

    service = PublicResearchReportsService(repository=FakeRepository([
        _row(
            effective_date="2026-09-14",
            payload={"title": "BTC", "summary": "Công khai", "body": "Báo cáo đầy đủ", "runId": "private"},
        ),
    ]))

    result = service.list_history("crypto:BTC/USDT", "deep")

    assert result[0]["effectiveDate"] == "2026-09-14"
    assert result[0]["source"] == "PUBLIC_RESEARCH_REPORT"
    assert "body" not in result[0]
    assert "sourceRunId" not in result[0]
