"""Smart Insights application service and input boundary validation."""

from __future__ import annotations

from datetime import date
from functools import lru_cache

from .repository import SmartInsightsRepository


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
        if imported and (not normalized_as_of or imported_as_of == normalized_as_of):
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
        dates = self.repository.list_dates(market=_market(market, allow_none=True), data_class=data_class)
        if data_class == "LIVE":
            imported = self._production_import(int(user_id), "briefing")
            imported_date = str((imported or {}).get("payload", {}).get("localDate") or "")
            if imported_date and imported_date not in dates:
                dates = sorted([*dates, imported_date], reverse=True)
        return {"mode": normalized_mode, "dates": dates}

    def get_evidence(self, *, user_id: int, evidence_id: str) -> dict | None:
        del user_id
        if not evidence_id or len(evidence_id) > 128:
            raise ValueError("invalid_evidence_id")
        return self.repository.get_evidence(evidence_id)

    def get_data_health(self, *, user_id: int) -> dict:
        del user_id
        return {"sources": self.repository.data_health()}

    def get_crypto_market_pulse(
        self, *, user_id: int, as_of: str | None, mode: str | None
    ) -> dict:
        normalized_mode, data_class = _mode(mode)
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
                runtime = build_crypto_market_pulse(
                    self.repository.list_pulse_observations(
                        data_class=data_class, as_of=_as_of(as_of)
                    ),
                    mode=normalized_mode,
                )
                return merge_imported_crypto_market_pulse(imported, runtime)
        from .crypto_pulse import build_crypto_market_pulse

        return build_crypto_market_pulse(
            self.repository.list_pulse_observations(
                data_class=data_class, as_of=_as_of(as_of)
            ),
            mode=normalized_mode,
        )

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
