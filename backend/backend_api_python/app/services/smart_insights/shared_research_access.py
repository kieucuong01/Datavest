"""Authorization and orchestration boundary for reusable Smart Insights reports."""

from __future__ import annotations

from datetime import date
from typing import Any, Callable, Mapping

from app.services.market.watchlist import list_watchlist
from app.services.smart_insights.public_reports import (
    PUBLIC_RESEARCH_ASSET_SCOPE,
    PUBLIC_RESEARCH_LOCALE,
    PublicResearchReportsRepository,
    PublicResearchReportsService,
    public_asset_key,
)
from app.services.smart_insights.shared_reports import (
    SharedResearchReportsRepository,
    SharedResearchReportsService,
    reporting_period_key,
)


def _display_symbol(symbol: str) -> str:
    clean = str(symbol or "").strip().upper()
    if clean == "XAUUSD":
        return "XAU"
    return clean.split("/", 1)[0]


class SharedResearchAccessService:
    """Resolve safe report state without ever returning account-owned run data."""

    def __init__(
        self,
        *,
        watchlist_loader: Callable[[int], list[dict[str, Any]]] | None = None,
        public_repository: PublicResearchReportsRepository | None = None,
        shared_repository: SharedResearchReportsRepository | None = None,
        dispatch: Callable[[str, str, Mapping[str, str], str], Any] | None = None,
    ) -> None:
        self._watchlist_loader = watchlist_loader or list_watchlist
        self.public_repository = public_repository or PublicResearchReportsRepository()
        self.public_reports = PublicResearchReportsService(repository=self.public_repository)
        self.shared_reports = SharedResearchReportsService(repository=shared_repository)
        self._dispatch = dispatch or self._dispatch_task

    @staticmethod
    def _common_assets() -> dict[str, dict[str, str]]:
        return {public_asset_key(asset): dict(asset) for asset in PUBLIC_RESEARCH_ASSET_SCOPE}

    def assets_for_user(self, user_id: int) -> list[dict[str, str]]:
        common = self._common_assets()
        rows = list(common.values())
        seen = set(common)
        for row in self._watchlist_loader(int(user_id)):
            asset = {
                "market": str(row.get("market") or "").strip(),
                "symbol": str(row.get("symbol") or "").strip(),
                "displaySymbol": _display_symbol(str(row.get("symbol") or "")),
                "name": str(row.get("name") or row.get("symbol") or "").strip(),
            }
            key = public_asset_key(asset)
            if key and key not in seen:
                rows.append(asset)
                seen.add(key)
        return rows

    def resolve_asset(self, user_id: int, asset_key: str) -> tuple[str, dict[str, str]]:
        key = str(asset_key or "").strip()
        common = self._common_assets()
        if key in common:
            return "public_common", common[key]
        for asset in self.assets_for_user(user_id):
            if public_asset_key(asset) == key:
                return "shared_watchlist", asset
        # Do not reveal whether an asset exists or which other users request it.
        raise ValueError("shared_report_not_found")

    def state(self, *, user_id: int, asset_key: str, report_kind: str, today: date | None = None) -> dict[str, Any]:
        scope, _asset = self.resolve_asset(user_id, asset_key)
        period = reporting_period_key(report_kind, today=today)
        if scope == "public_common":
            result = self.public_reports.get_state(
                asset_key, report_kind, effective_date=period, locale=PUBLIC_RESEARCH_LOCALE,
            )
        else:
            result = self.shared_reports.state(asset_key, report_kind, today=today)
        return {**result, "scope": scope}

    def list_states(self, *, user_id: int, today: date | None = None) -> list[dict[str, Any]]:
        states: list[dict[str, Any]] = []
        for asset in self.assets_for_user(user_id):
            key = public_asset_key(asset)
            for kind in ("quick", "deep"):
                states.append({**self.state(user_id=user_id, asset_key=key, report_kind=kind, today=today), "asset": asset})
        return states

    def request(self, *, user_id: int, asset_key: str, report_kind: str, today: date | None = None) -> dict[str, Any]:
        scope, asset = self.resolve_asset(user_id, asset_key)
        period = reporting_period_key(report_kind, today=today)
        if scope == "public_common":
            claimed = self.public_repository.claim_pending(
                asset_key=asset_key, report_kind=report_kind, locale=PUBLIC_RESEARCH_LOCALE,
                effective_date=period,
            )
        else:
            claimed_state = self.shared_reports.claim(asset_key, report_kind, today=today)
            claimed = bool(claimed_state["claimed"])
        if claimed:
            self._dispatch(scope, report_kind, asset, period)
        state = self.state(user_id=user_id, asset_key=asset_key, report_kind=report_kind, today=today)
        return {**state, "claimed": claimed}

    @staticmethod
    def _dispatch_task(scope: str, report_kind: str, asset: Mapping[str, str], period_key: str) -> None:
        from app.tasks.smart_insights import enqueue_shared_research_report
        enqueue_shared_research_report.delay(
            scope=str(scope), report_kind=str(report_kind), asset=dict(asset), period_key=str(period_key)
        )


__all__ = ["SharedResearchAccessService"]
