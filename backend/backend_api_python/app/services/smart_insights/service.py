"""Smart Insights application service and input boundary validation."""

from __future__ import annotations

from datetime import date, datetime, timezone
from functools import lru_cache

from app.utils.request_guard import cache_key, guarded_cached
from app.utils.timeutil import vietnam_calendar_date

from .repository import SmartInsightsRepository
from .data_contract import attach_data_contract, freshness_for_status


_MARKETS = frozenset({"crypto", "macro", "vn", "us", "gold", "all"})
_MODES = {"live": "LIVE", "demo": "DEMO"}


def _market(value: str | None, *, allow_none: bool = False) -> str | None:
    if value in (None, "") and allow_none:
        return None
    normalized = str(value or "all").strip().lower()
    if normalized not in _MARKETS:
        raise ValueError("invalid_market")
    return normalized


def _mode(value: str | None) -> tuple[str, str]:
    normalized = str(value or "live").strip().lower()
    if normalized not in _MODES:
        raise ValueError("invalid_mode")
    return normalized, _MODES[normalized]


def _as_of(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError("invalid_as_of") from exc


class SmartInsightsService:
    def __init__(
        self,
        repository: SmartInsightsRepository | None = None,
        watchlist_loader=None,
    ) -> None:
        self.repository = repository or SmartInsightsRepository()
        if watchlist_loader is None:
            from app.services.market.watchlist import get_user_watchlist_pairs

            watchlist_loader = get_user_watchlist_pairs
        self.watchlist_loader = watchlist_loader

    def get_overview(
        self,
        *,
        user_id: int,
        as_of: str | None,
        market: str | None,
        mode: str | None,
    ) -> dict:
        normalized_mode, data_class = _mode(mode)
        normalized_market = _market(market)
        normalized_as_of = _as_of(as_of)
        # Resolve this from the authenticated user, never from client-supplied
        # opinion data. An empty list is meaningful: return no Asset Opinions.
        watchlist_pairs = self.watchlist_loader(int(user_id))
        imported = self._production_import(int(user_id), "briefing") if data_class == "LIVE" else None
        imported_as_of = str((imported or {}).get("payload", {}).get("localDate") or "")
        # A production import is a migration compatibility source, not a
        # freshness override. Once a live snapshot exists for this market
        # scope, the default view must use that snapshot instead of silently
        # returning an older imported briefing.
        live_dates = self._snapshot_dates(normalized_market, data_class="LIVE") if data_class == "LIVE" else []
        requested_live_snapshot = (
            normalized_as_of in live_dates if normalized_as_of else bool(live_dates)
        )
        if (
            imported
            and imported_as_of
            and not requested_live_snapshot
            and (not normalized_as_of or imported_as_of == normalized_as_of)
        ):
            from .production_account_view import build_imported_overview

            result = build_imported_overview(
                imported["payload"],
                checksum=imported["checksum"],
                market=str(normalized_market),
                watchlist_pairs=watchlist_pairs,
            )
            result["mode"] = normalized_mode
            return result
        if normalized_market == "all":
            result = self.repository.get_overview_all(
                user_id=int(user_id),
                as_of=normalized_as_of,
                data_class=data_class,
                watchlist_pairs=watchlist_pairs,
            )
        else:
            result = self.repository.get_overview(
                user_id=int(user_id),
                as_of=normalized_as_of,
                market=str(normalized_market),
                data_class=data_class,
                watchlist_pairs=watchlist_pairs,
            )
        result["mode"] = normalized_mode
        return result

    def list_dates(self, *, user_id: int, market: str | None, mode: str | None) -> dict:
        normalized_mode, data_class = _mode(mode)
        normalized_market = _market(market, allow_none=True)
        dates = self._snapshot_dates(normalized_market, data_class=data_class)
        if data_class == "LIVE":
            imported = self._production_import(int(user_id), "briefing")
            imported_date = str((imported or {}).get("payload", {}).get("localDate") or "")
            if imported_date and imported_date not in dates:
                dates = sorted([*dates, imported_date], reverse=True)
        return {"mode": normalized_mode, "dates": dates}

    def _snapshot_dates(self, market: str | None, *, data_class: str) -> list[str]:
        """Return snapshot dates for a UI scope, with ``all`` as a union."""
        loader = getattr(self.repository, "list_dates", None)
        if not callable(loader):
            # Keep lightweight repository doubles and clean installs
            # compatible; the real repository always implements this method.
            return []
        query_market = None if market == "all" else market
        return list(loader(market=query_market, data_class=data_class) or [])

    def get_evidence(self, *, user_id: int, evidence_id: str) -> dict | None:
        del user_id
        if not evidence_id or len(evidence_id) > 128:
            raise ValueError("invalid_evidence_id")
        return self.repository.get_evidence(evidence_id)

    def get_data_health(self, *, user_id: int) -> dict:
        del user_id
        sources = self.repository.data_health()
        fresh_count = sum(1 for row in sources if str(row.get("freshness") or "").upper() == "FRESH")
        status = "COMPLETE" if sources and fresh_count == len(sources) else "PARTIAL" if fresh_count or sources else "UNAVAILABLE"
        return attach_data_contract(
            {"status": status, "sources": sources},
            requested_as_of=None,
            resolved_as_of=vietnam_calendar_date(),
            fetched_at=datetime.now(timezone.utc),
            coverage={"sources": len(sources), "freshSources": fresh_count},
        )

    def get_crypto_market_pulse(
        self, *, user_id: int, as_of: str | None, mode: str | None,
        compact: bool = False,
    ) -> dict:
        normalized_mode, data_class = _mode(mode)
        normalized_as_of = _as_of(as_of)
        if compact:
            return guarded_cached(
                cache_key(
                    "smart-insights",
                    "crypto-pulse",
                    "compact-v1",
                    int(user_id),
                    normalized_mode,
                    normalized_as_of or "latest",
                ),
                lambda: self._build_crypto_market_pulse(
                    user_id=int(user_id),
                    normalized_mode=normalized_mode,
                    data_class=data_class,
                    as_of=normalized_as_of,
                    compact=True,
                ),
                ttl_sec=300,
                stale_ttl_sec=1800,
                timeout_sec=20,
                namespace="smart-insights-pulse",
                max_concurrent=2,
            )
        return self._build_crypto_market_pulse(
            user_id=int(user_id),
            normalized_mode=normalized_mode,
            data_class=data_class,
            as_of=normalized_as_of,
            compact=False,
        )

    def _build_crypto_market_pulse(
        self,
        *,
        user_id: int,
        normalized_mode: str,
        data_class: str,
        as_of: str | None,
        compact: bool,
    ) -> dict:
        if data_class == "LIVE":
            imported_pulse = self._production_import(int(user_id), "crypto_pulse")
            if imported_pulse:
                from .crypto_pulse import build_crypto_market_pulse
                from .production_account_view import (
                    build_imported_crypto_market_pulse,
                    merge_imported_crypto_market_pulse,
                )

                imported_calendar = self._production_import(int(user_id), "calendar")
                imported = build_imported_crypto_market_pulse(
                    imported_pulse["payload"],
                    (imported_calendar or {}).get("payload", {}),
                    checksum=imported_pulse["checksum"],
                    mode=normalized_mode,
                )
                repository_kwargs = {
                    "data_class": data_class,
                    "as_of": as_of,
                }
                if compact:
                    repository_kwargs["compact"] = True
                runtime = build_crypto_market_pulse(
                    self.repository.list_pulse_observations(**repository_kwargs),
                    mode=normalized_mode,
                )
                return self._attach_pulse_contract(
                    merge_imported_crypto_market_pulse(imported, runtime),
                    requested_as_of=as_of,
                )
        from .crypto_pulse import build_crypto_market_pulse

        repository_kwargs = {
            "data_class": data_class,
            "as_of": as_of,
        }
        if compact:
            repository_kwargs["compact"] = True
        return self._attach_pulse_contract(
            build_crypto_market_pulse(
                self.repository.list_pulse_observations(**repository_kwargs),
                mode=normalized_mode,
            ),
            requested_as_of=as_of,
        )

    @staticmethod
    def _attach_pulse_contract(payload: dict, *, requested_as_of: str | None) -> dict:
        tabs = payload.get("tabs") if isinstance(payload.get("tabs"), dict) else {}
        available_tabs = sum(
            1 for value in tabs.values()
            if isinstance(value, dict) and str(value.get("status") or "").upper() == "AVAILABLE"
        )
        total_tabs = len(tabs)
        resolved_as_of = str(payload.get("asOf") or requested_as_of or "").strip() or None
        historical = bool(resolved_as_of and resolved_as_of != vietnam_calendar_date())
        freshness = freshness_for_status(payload.get("status"), historical=historical)
        result = attach_data_contract(
            payload,
            requested_as_of=requested_as_of,
            resolved_as_of=resolved_as_of,
            fetched_at=datetime.now(timezone.utc),
            freshness=freshness,
            coverage={
                "availableTabs": available_tabs,
                "totalTabs": total_tabs,
                "ratio": round(available_tabs / total_tabs, 4) if total_tabs else 0.0,
            },
        )
        calendar = result.get("calendar")
        if isinstance(calendar, dict):
            result["calendar"] = attach_data_contract(
                calendar,
                requested_as_of=requested_as_of,
                resolved_as_of=resolved_as_of,
                fetched_at=datetime.now(timezone.utc),
                coverage={"events": len(calendar.get("events") or [])},
            )
        return result

    def _production_import(self, user_id: int, data_type: str) -> dict | None:
        """Imports are optional for clean installs and lightweight repository doubles."""
        loader = getattr(self.repository, "get_production_account_import", None)
        return loader(user_id=user_id, data_type=data_type) if callable(loader) else None

    def queue_refresh(
        self,
        *,
        requested_by_user_id: int,
        market: str | None,
        source_codes: tuple[str, ...],
    ) -> dict:
        normalized_market = _market(market, allow_none=True)
        normalized_sources = tuple(
            dict.fromkeys(code.strip().lower() for code in source_codes if code and code.strip())
        )
        if "cbbi-public" in normalized_sources:
            raise ValueError("retired_source_code")
        if len(normalized_sources) > 50 or any(len(code) > 120 for code in normalized_sources):
            raise ValueError("invalid_source_codes")
        run_id = self.repository.create_refresh_request(
            requested_by_user_id=int(requested_by_user_id),
            market=normalized_market,
            source_codes=normalized_sources,
        )
        from app.tasks.smart_insights import run_smart_insights_refresh

        run_smart_insights_refresh.delay(run_id)
        return {"status": "QUEUED", "runId": run_id}


@lru_cache(maxsize=1)
def get_smart_insights_service() -> SmartInsightsService:
    return SmartInsightsService()


__all__ = ["SmartInsightsService", "get_smart_insights_service"]
