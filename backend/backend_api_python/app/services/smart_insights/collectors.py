"""Audited Smart Insights collector orchestration."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
import os
from typing import Protocol

from .contracts import Observation
from .repository import SmartInsightsRepository


_CRYPTOETF_SNAPSHOT_SOURCES = (
    "cryptoetf-btc-etf", "cryptoetf-eth-etf", "cryptoetf-sol-etf", "cryptoetf-xrp-etf",
    "cryptoetf-hyp-etf", "cryptoetf-doge-etf", "cryptoetf-link-etf", "cryptoetf-avax-etf",
    "cryptoetf-hbar-etf", "cryptoetf-ltc-etf", "cryptoetf-bnb-etf", "cryptoetf-dot-etf",
    "cryptoetf-sui-etf",
)


class CollectorUnavailable(RuntimeError):
    pass


class CollectorRepository(Protocol):
    def load_refresh_request(self, run_id: str) -> Mapping[str, object]: ...
    def mark_run_running(self, run_id: str) -> None: ...
    def resolve_data_source(self, code: str) -> int: ...
    def upsert_observation(
        self, observation: Observation, *, data_source_id: int, collector_run_id: str | None
    ) -> tuple[str, bool]: ...
    def mark_run_succeeded(
        self,
        run_id: str,
        *,
        records_fetched: int,
        records_persisted: int,
        warnings: tuple[str, ...],
    ) -> None: ...

    def mark_run_partial(
        self,
        run_id: str,
        *,
        records_fetched: int,
        records_persisted: int,
        warnings: tuple[str, ...],
    ) -> None: ...
    def mark_run_failed(
        self, run_id: str, *, error_code: str, warnings: tuple[str, ...]
    ) -> None: ...


Collector = Callable[[], Sequence[Observation]]


class RefreshCoordinator:
    def __init__(
        self,
        *,
        repository: CollectorRepository,
        collector_registry: Mapping[str, Collector],
        snapshot_publisher=None,
    ) -> None:
        self.repository = repository
        self.collector_registry = dict(collector_registry)
        self.snapshot_publisher = snapshot_publisher

    def execute(self, run_id: str) -> dict:
        request = self.repository.load_refresh_request(run_id)
        source_codes = tuple(str(code) for code in (request.get("sourceCodes") or ()))
        try:
            self.repository.mark_run_running(run_id)
        except ValueError as exc:
            # A late Celery redelivery must not turn a refresh another worker
            # already owns into a failed run.  The claiming update is atomic.
            if str(exc) == "refresh_run_not_queued":
                return {
                    "runId": run_id,
                    "status": "SKIPPED",
                    "reason": "already_claimed",
                }
            raise
        fetched = 0
        persisted = 0
        warnings: list[str] = []
        persisted_rows: list[tuple[str, Observation]] = []
        completed_sources = 0
        failed_sources = 0
        try:
            if not source_codes:
                self.repository.mark_run_failed(
                    run_id, error_code="COLLECTOR_UNAVAILABLE", warnings=()
                )
                raise CollectorUnavailable("COLLECTOR_UNAVAILABLE")
            for source_code in source_codes:
                collector = self.collector_registry.get(source_code)
                if collector is None:
                    failed_sources += 1
                    warnings.append(f"SOURCE_NOT_IMPLEMENTED:{source_code}")
                    continue
                try:
                    data_source_id = self.repository.resolve_data_source(source_code)
                    for observation in collector():
                        if not isinstance(observation, Observation):
                            raise ValueError("INVALID_COLLECTOR_OUTPUT")
                        if observation.source_code != source_code:
                            raise ValueError("SOURCE_IDENTITY_MISMATCH")
                        fetched += 1
                        observation_id, created = self.repository.upsert_observation(
                            observation,
                            data_source_id=data_source_id,
                            collector_run_id=run_id,
                        )
                        persisted += int(created)
                        persisted_rows.append((observation_id, observation))
                        warnings.extend(observation.warnings)
                    completed_sources += 1
                except CollectorUnavailable as exc:
                    failed_sources += 1
                    warnings.append(f"SOURCE_UNAVAILABLE:{source_code}:{str(exc)}")
                except (ValueError, RuntimeError) as exc:
                    failed_sources += 1
                    warnings.append(f"SOURCE_FAILED:{source_code}:{type(exc).__name__}")
                except Exception:
                    failed_sources += 1
                    warnings.append(f"SOURCE_FAILED:{source_code}:UNEXPECTED_ERROR")
            normalized_warnings = tuple(dict.fromkeys(warnings))
            snapshots = (
                self.snapshot_publisher(persisted_rows)
                if self.snapshot_publisher is not None and persisted_rows
                else []
            )
            if completed_sources == 0:
                self.repository.mark_run_failed(
                    run_id, error_code="COLLECTOR_UNAVAILABLE", warnings=normalized_warnings
                )
                raise CollectorUnavailable("COLLECTOR_UNAVAILABLE")
            status = "PARTIAL" if failed_sources else "SUCCEEDED"
            if status == "PARTIAL":
                self.repository.mark_run_partial(
                    run_id,
                    records_fetched=fetched,
                    records_persisted=persisted,
                    warnings=normalized_warnings,
                )
            else:
                self.repository.mark_run_succeeded(
                    run_id,
                    records_fetched=fetched,
                    records_persisted=persisted,
                    warnings=normalized_warnings,
                )
            result = {
                "runId": run_id,
                "status": status,
                "recordsFetched": fetched,
                "recordsPersisted": persisted,
                "warnings": list(normalized_warnings),
            }
            if snapshots:
                result["snapshots"] = snapshots
            return result
        except CollectorUnavailable:
            raise
        except Exception as exc:
            self.repository.mark_run_failed(
                run_id, error_code="COLLECTOR_FAILED", warnings=tuple(dict.fromkeys(warnings))
            )
            raise RuntimeError("COLLECTOR_FAILED") from exc


def default_collector_registry(*, repository: SmartInsightsRepository | None = None) -> dict[str, Collector]:
    """Specialty collectors are registered without exposing provider secrets."""
    from .defillama import DefiLlamaStablecoinsCollector
    from .defillama import DefiLlamaChainsCollector
    from .coinmetrics import CoinMetricsCollector, CoinMetricsPriceHistoryCollector
    from .legacy_browser import NodriverBrowserClient
    from .legacy_crawlers import CoinGlassMarginBrowserCollector, CoinGlassMaxPainBrowserCollector
    from .coinshares_browser import CoinSharesBrowserCollector
    from .fred import FredCollector
    from .alternative_fng import AlternativeFearGreedCollector
    from .farside import FarsideEtfCollector
    from .mempool import MempoolCollector
    from .cycle import AltcoinSeasonCollector, CbbiCollector
    from .openbb_deribit import OpenBBDeribitCollector
    from .bybit_derivatives import BybitDerivativesCollector
    from .binance_usdm_derivatives import BinanceUsdmDerivativesCollector
    from .deribit_public_derivatives import DeribitPublicDerivativesCollector
    from .snapshot_collectors import SnapshotObservationCollector

    def collect_fred_core() -> tuple[Observation, ...]:
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=45)).date()
        end = now.date()
        collector = FredCollector()
        rows: list[Observation] = []
        for series_id in ("DGS2", "DGS10", "DFII10", "DTWEXBGS"):
            rows.extend(collector.collect(series_id, start, end))
        return tuple(rows)

    def collect_coinmetrics_core() -> tuple[Observation, ...]:
        now = datetime.now(timezone.utc)
        # The long BTC price series is compact (one row per day) and is kept
        # separate from the wider 370-day on-chain collection. It lets cycle
        # models use the same audited free provider rather than sample data.
        return (
            *CoinMetricsCollector().collect(now),
            *CoinMetricsPriceHistoryCollector().collect(now),
        )

    browser = NodriverBrowserClient(
        timeout_seconds=float(os.getenv("SMART_INSIGHTS_BROWSER_TIMEOUT_SEC", "60")),
        poll_interval_seconds=float(os.getenv("SMART_INSIGHTS_BROWSER_POLL_SEC", "1")),
    )

    return {
        "bybit-derivatives": lambda: BybitDerivativesCollector().collect(datetime.now(timezone.utc)),
        "binance-usdm-derivatives": lambda: BinanceUsdmDerivativesCollector().collect(datetime.now(timezone.utc)),
        "deribit-public-derivatives": lambda: DeribitPublicDerivativesCollector().collect(datetime.now(timezone.utc)),
        "openbb-deribit": lambda: OpenBBDeribitCollector().collect(datetime.now(timezone.utc)),
        "fred": collect_fred_core,
        "defillama-stablecoins": lambda: DefiLlamaStablecoinsCollector().collect(
            datetime.now(timezone.utc)
        ),
        "defillama-chains": lambda: DefiLlamaChainsCollector().collect(datetime.now(timezone.utc)),
        "coinmetrics-community": collect_coinmetrics_core,
        "coinglass-margin-borrow": lambda: CoinGlassMarginBrowserCollector(browser=browser).collect(datetime.now(timezone.utc)),
        "coinglass-liquidation-maxpain": lambda: CoinGlassMaxPainBrowserCollector(browser=browser).collect(datetime.now(timezone.utc)),
        "bitinfocharts-top-addresses": SnapshotObservationCollector("bitinfocharts-top-addresses"),
        "coinshares-weekly": SnapshotObservationCollector("coinshares-weekly"),
        "alternative-fng": SnapshotObservationCollector("alternative-fng"),
        "mempool-space": lambda: MempoolCollector().collect(datetime.now(timezone.utc)),
        "farside-btc-etf": SnapshotObservationCollector("farside-btc-etf"),
        "farside-eth-etf": SnapshotObservationCollector("farside-eth-etf"),
        "farside-sol-etf": SnapshotObservationCollector("farside-sol-etf"),
        **{source: SnapshotObservationCollector(source) for source in _CRYPTOETF_SNAPSHOT_SOURCES},
        "xoomar-btc-etf": SnapshotObservationCollector("xoomar-btc-etf"),
        "xoomar-eth-etf": SnapshotObservationCollector("xoomar-eth-etf"),
        "cbbi-public": SnapshotObservationCollector("cbbi-public"),
        "blockchaincenter-altcoin-season": SnapshotObservationCollector("blockchaincenter-altcoin-season"),
    }


def execute_refresh(run_id: str) -> dict:
    from .snapshot_pipeline import SnapshotMaterializer

    repository = SmartInsightsRepository()
    materializer = SnapshotMaterializer(repository=repository)
    return RefreshCoordinator(
        repository=repository,
        collector_registry=default_collector_registry(repository=repository),
        snapshot_publisher=materializer.publish_observations,
    ).execute(run_id)


__all__ = [
    "CollectorUnavailable",
    "RefreshCoordinator",
    "default_collector_registry",
    "execute_refresh",
]
