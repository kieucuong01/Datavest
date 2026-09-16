"""Bounded, tenant-free Smart Insights read model for anonymous visitors."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from functools import lru_cache
from typing import Any, Mapping

from app.utils.timeutil import vietnam_calendar_date

from .crypto_pulse import build_crypto_market_pulse
from .data_contract import attach_data_contract
from .public_reports import (
    PUBLIC_GUEST_ASSET_SCOPE,
    PublicResearchReportsService,
)
from .repository import SmartInsightsRepository, normalize_pulse_load_stage
from .service import SmartInsightsService
from .watchlist_scope import opinion_key


PUBLIC_ASSET_SCOPE = PUBLIC_GUEST_ASSET_SCOPE

PUBLIC_EVIDENCE_FIELDS = frozenset(
    {
        "id",
        "market",
        "symbol",
        "source",
        "sourceName",
        "sourceUrl",
        "effectiveAt",
        "publishedAt",
        "observedAt",
        "methodologyVersion",
        "warnings",
        "checksum",
        "dataClass",
        "reliability",
        "value",
    }
)
PUBLIC_HEALTH_FIELDS = frozenset(
    {"code", "name", "market", "sourceUrl", "freshness", "lastObservedAt", "coverage"}
)
PUBLIC_EVIDENCE_VALUE_FIELDS = frozenset(
    {
        "metric",
        "value",
        "unit",
        "dimensions",
        "requestedMarket",
        "requestedSymbol",
        "timeframe",
        "barCount",
        "evidenceOnly",
    }
)
PUBLIC_EVIDENCE_DIMENSION_FIELDS = frozenset(
    {
        "address",
        "aggregation",
        "asset",
        "chain",
        "classification",
        "cohort",
        "cohort_version",
        "contract",
        "detail_scope",
        "dimension",
        "entity_category",
        "event",
        "exchange",
        "frequency",
        "fund",
        "historyLimited",
        "horizon",
        "impact",
        "instrument",
        "label",
        "label_coverage",
        "label_status",
        "last_activity_at",
        "network",
        "ocr_engine",
        "pegBuckets",
        "providerMetric",
        "providerSeries",
        "quality_tier",
        "quote_asset",
        "rank",
        "scope",
        "source_unit",
        "tenorDays",
        "tokenSymbol",
        "venue",
    }
)


def _validated_as_of(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError as exc:
        raise ValueError("invalid_as_of") from exc


def _public_assets() -> list[dict[str, str]]:
    return [dict(item) for item in PUBLIC_ASSET_SCOPE]


def _public_opinion_keys() -> set[str]:
    return {
        key
        for item in PUBLIC_ASSET_SCOPE
        if (key := opinion_key(item)) is not None
    }


def _allow_fields(row: Mapping[str, Any], fields: frozenset[str]) -> dict[str, Any]:
    return {key: deepcopy(row[key]) for key in fields if key in row}


def _public_scalar(value: Any) -> str | int | float | bool | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return None


def _public_evidence_value(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, Any] = {}
    for key in PUBLIC_EVIDENCE_VALUE_FIELDS - {"dimensions"}:
        if key in value and (safe_value := _public_scalar(value[key])) is not None:
            result[key] = safe_value
    dimensions = value.get("dimensions")
    if isinstance(dimensions, Mapping):
        safe_dimensions = {
            key: safe_value
            for key in PUBLIC_EVIDENCE_DIMENSION_FIELDS
            if key in dimensions
            and (safe_value := _public_scalar(dimensions[key])) is not None
        }
        result["dimensions"] = safe_dimensions
    return result


class PublicSmartInsightsService:
    """Read shared LIVE evidence without resolving an authenticated tenant."""

    def __init__(
        self,
        repository: SmartInsightsRepository | None = None,
        public_reports: PublicResearchReportsService | None = None,
    ) -> None:
        self.repository = repository or SmartInsightsRepository()
        self.public_reports = public_reports or PublicResearchReportsService()

    def get_overview(
        self, *, as_of: str | None = None, locale: str = "vi-VN"
    ) -> dict[str, Any]:
        normalized_as_of = _validated_as_of(as_of)
        assets = _public_assets()
        result = self.repository.get_overview_all(
            user_id=0,
            as_of=normalized_as_of,
            data_class="LIVE",
            watchlist_pairs=assets,
        )
        allowed_keys = _public_opinion_keys()
        result["opinions"] = [
            row
            for row in list(result.get("opinions") or [])
            if isinstance(row, Mapping) and opinion_key(row) in allowed_keys
        ]
        result["assets"] = assets
        result["scope"] = "PUBLIC_COMMON_ASSETS"
        result["mode"] = "live"
        result["locale"] = str(locale or "vi-VN")[:16]
        return result

    def list_dates(self) -> dict[str, Any]:
        return {
            "mode": "live",
            "dates": list(
                self.repository.list_dates(market=None, data_class="LIVE") or []
            ),
        }

    def get_evidence(self, evidence_id: str) -> dict[str, Any] | None:
        normalized_id = str(evidence_id or "").strip()
        if not normalized_id or len(normalized_id) > 128:
            raise ValueError("invalid_evidence_id")
        row = self.repository.get_evidence(normalized_id)
        if not isinstance(row, Mapping) or str(row.get("dataClass") or "").upper() != "LIVE":
            return None
        result = _allow_fields(row, PUBLIC_EVIDENCE_FIELDS)
        result["value"] = _public_evidence_value(row.get("value"))
        return result

    def get_data_health(self) -> dict[str, Any]:
        sources = [
            _allow_fields(row, PUBLIC_HEALTH_FIELDS)
            for row in list(self.repository.data_health() or [])
            if isinstance(row, Mapping)
        ]
        fresh_count = sum(
            1 for row in sources if str(row.get("freshness") or "").upper() == "FRESH"
        )
        status = (
            "COMPLETE"
            if sources and fresh_count == len(sources)
            else "PARTIAL"
            if sources
            else "UNAVAILABLE"
        )
        return attach_data_contract(
            {"status": status, "sources": sources},
            requested_as_of=None,
            resolved_as_of=vietnam_calendar_date(),
            fetched_at=datetime.now(timezone.utc),
            coverage={"sources": len(sources), "freshSources": fresh_count},
        )

    def get_live_assets(self) -> dict[str, Any]:
        from .live_assets import get_live_asset_snapshot

        return get_live_asset_snapshot()

    def get_public_report(
        self, *, asset_key: str, report_kind: str, locale: str = "vi-VN",
        effective_date: date | str | None = None,
    ) -> dict[str, Any] | None:
        if effective_date is not None:
            return self.public_reports.get_for_date(asset_key, report_kind, effective_date, locale)
        return self.public_reports.get_latest(asset_key, report_kind, locale)

    def get_public_report_history(
        self, *, asset_key: str, report_kind: str, locale: str = "vi-VN", limit: int = 100
    ) -> list[dict[str, Any]]:
        return self.public_reports.list_history(asset_key, report_kind, locale, limit)

    def get_crypto_market_pulse(
        self, *, as_of: str | None = None, compact: bool = False,
        stage: str = "full",
    ) -> dict[str, Any]:
        normalized_as_of = _validated_as_of(as_of)
        normalized_stage = normalize_pulse_load_stage(stage)
        repository_kwargs: dict[str, Any] = {
            "data_class": "LIVE",
            "as_of": normalized_as_of,
        }
        if compact:
            repository_kwargs["compact"] = True
        if normalized_stage != "full":
            repository_kwargs["stage"] = normalized_stage
        payload = build_crypto_market_pulse(
            self.repository.list_pulse_observations(**repository_kwargs),
            mode="live",
        )
        result = SmartInsightsService._attach_pulse_contract(
            payload, requested_as_of=normalized_as_of
        )
        result["loadStage"] = normalized_stage
        return result


@lru_cache(maxsize=1)
def get_public_smart_insights_service() -> PublicSmartInsightsService:
    return PublicSmartInsightsService()


__all__ = [
    "PUBLIC_ASSET_SCOPE",
    "PUBLIC_EVIDENCE_FIELDS",
    "PUBLIC_EVIDENCE_VALUE_FIELDS",
    "PUBLIC_EVIDENCE_DIMENSION_FIELDS",
    "PUBLIC_HEALTH_FIELDS",
    "PublicSmartInsightsService",
    "get_public_smart_insights_service",
]
