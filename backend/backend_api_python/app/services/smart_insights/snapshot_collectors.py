"""Convert validated Browser Use snapshots into Smart Insights observations."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path

from .browser_snapshots import SnapshotUnavailable, load_snapshot, snapshot_root
from .collectors import CollectorUnavailable
from .contracts import Observation
from .sources import source_for_code


_SYMBOLS = {"Bitcoin": "BTC", "Ethereum": "ETH", "Solana": "SOL", "XRP": "XRP"}


def _time(value: object) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise CollectorUnavailable("INVALID_TIMESTAMP") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CollectorUnavailable("INVALID_TIMESTAMP")
    return parsed.astimezone(timezone.utc)


class SnapshotObservationCollector:
    """Callable source collector backed only by one local validated snapshot."""

    def __init__(
        self,
        source_code: str,
        *,
        root: Path | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.source = source_for_code(source_code)
        self.root = root or snapshot_root()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def __call__(self) -> tuple[Observation, ...]:
        return self.collect()

    def collect(self) -> tuple[Observation, ...]:
        try:
            payload = load_snapshot(self.source.code, root=self.root, now=self.clock())
        except SnapshotUnavailable as exc:
            raise CollectorUnavailable(str(exc)) from exc
        records = payload.get("records")
        if not isinstance(records, list):
            raise CollectorUnavailable("REQUIRED_RECORDS")
        observed_at = _time(payload.get("fetched_at"))
        source_url = str(payload.get("source_url") or self.source.urls[0])
        rows = tuple(self._observation(record, source_url=source_url, observed_at=observed_at) for record in records)
        if not rows:
            raise CollectorUnavailable("REQUIRED_RECORDS")
        return rows

    def _observation(self, record: object, *, source_url: str, observed_at: datetime) -> Observation:
        if not isinstance(record, Mapping):
            raise CollectorUnavailable("INVALID_RECORD")
        metric = str(record.get("metric") or "").strip()
        value = str(record.get("value") or "").strip()
        unit = str(record.get("unit") or "").strip()
        if not metric or not value or not unit:
            raise CollectorUnavailable("INVALID_RECORD")
        dimensions = {
            str(key): str(value)
            for key, value in record.items()
            if key not in {"effective_at", "metric", "value", "unit", "symbol", "warnings"}
            and value not in {None, ""}
        }
        raw_warnings = record.get("warnings")
        if isinstance(raw_warnings, (list, tuple)):
            warnings = tuple(str(item) for item in raw_warnings if str(item).strip())
        elif raw_warnings not in {None, ""}:
            warnings = (str(raw_warnings),)
        else:
            warnings = ()
        label = dimensions.get("label")
        symbol = str(record.get("symbol") or record.get("asset") or _SYMBOLS.get(label or "") or "").strip() or None
        return Observation.create(
            source_code=self.source.code,
            source_url=source_url,
            market=self.source.market,
            symbol=symbol,
            effective_at=_time(record.get("effective_at")),
            observed_at=observed_at,
            methodology_version=self.source.methodology_version,
            value={"metric": metric, "value": value, "unit": unit, "dimensions": dimensions},
            data_class="LIVE",
            warnings=warnings,
        )


__all__ = ["SnapshotObservationCollector"]
