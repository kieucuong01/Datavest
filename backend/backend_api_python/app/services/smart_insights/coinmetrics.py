"""Coin Metrics Community API collector ported from the DataVest worker."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import re
from urllib.parse import parse_qs, urlencode, urlsplit

from .collectors import CollectorUnavailable
from .contracts import Observation
from .sources import source_for_code
from .transport import RequestsTransport, Transport


_ASSETS = {"btc": "BTC", "eth": "ETH"}
_METRICS = {
    "AdrActCnt": ("crypto.onchain.active_addresses", "addresses"),
    "CapMVRVCur": ("crypto.onchain.mvrv", "ratio"),
    "SplyCur": ("crypto.onchain.circulating_supply_native", "native"),
    "SplyExNtv": ("crypto.onchain.exchange_reserve_native", "native"),
    "FlowInExNtv": ("crypto.onchain.exchange_inflow_native", "native"),
    "FlowOutExNtv": ("crypto.onchain.exchange_outflow_native", "native"),
    "TxCnt": ("crypto.onchain.transaction_count", "count"),
    "TxTfrCnt": ("crypto.onchain.transfer_count", "count"),
    "FeeTotNtv": ("crypto.onchain.total_fees_native", "native"),
    "HashRate": ("crypto.mining.hashrate_hs", "H/s"),
    "IssTotNtv": ("crypto.mining.issuance_native", "native"),
    "CapMrktCurUSD": ("crypto.market.market_cap_usd", "USD"),
    "PriceUSD": ("crypto.market.price_usd", "USD"),
}
_ALLOWED_QUERY = {
    "assets",
    "metrics",
    "start_time",
    "end_time",
    "frequency",
    "page_size",
    "sort",
    "next_page_token",
}
_NANOSECONDS = re.compile(r"(\.\d{6})\d+(?=Z$|[+-]\d\d:\d\d$)")
_MAX_ROWS = 50_000


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise CollectorUnavailable("INVALID_TIMESTAMP")
    normalized = _NANOSECONDS.sub(r"\1", value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise CollectorUnavailable("INVALID_TIMESTAMP") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CollectorUnavailable("INVALID_TIMESTAMP")
    return parsed.astimezone(timezone.utc)


class CoinMetricsCollector:
    """Fetch bounded Coin Metrics daily series and emit source-backed rows."""

    def __init__(
        self,
        *,
        transport: Transport | None = None,
        assets: dict[str, str] | None = None,
        metrics: dict[str, tuple[str, str]] | None = None,
        history_days: int = 370,
    ) -> None:
        if history_days < 1 or history_days > 6_500:
            raise ValueError("history_days must be between 1 and 6500")
        self.source = source_for_code("coinmetrics-community")
        self.transport = transport or RequestsTransport()
        self.assets = dict(assets or _ASSETS)
        self.metrics = dict(metrics or _METRICS)
        self.history_days = history_days

    def collect(self, as_of: datetime) -> tuple[Observation, ...]:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        cutoff = as_of.astimezone(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        query = urlencode(
            {
                "assets": ",".join(self.assets),
                "metrics": ",".join(self.metrics),
                "start_time": (cutoff - timedelta(days=self.history_days)).date().isoformat(),
                "end_time": cutoff.date().isoformat(),
                "frequency": "1d",
                "page_size": "10000",
                "sort": "time",
            }
        )
        next_url: str | None = f"{self.source.urls[0]}?{query}"
        rows: list[tuple[datetime, dict[str, object]]] = []
        last_time_by_asset: dict[str, datetime] = {}

        for _page_index in range(10):
            if next_url is None:
                break
            response = self.transport.fetch(
                next_url, timeout_seconds=30, max_bytes=10_000_000
            )
            if response.status != 200 or response.url != next_url:
                raise CollectorUnavailable("INVALID_RESPONSE")
            try:
                payload = json.loads(response.body)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise CollectorUnavailable("INVALID_RESPONSE") from exc
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                raise CollectorUnavailable("SCHEMA_DRIFT")
            for raw in payload["data"]:
                if not isinstance(raw, dict) or raw.get("asset") not in self.assets:
                    raise CollectorUnavailable("SCHEMA_DRIFT")
                asset = str(raw["asset"])
                effective_at = _timestamp(raw.get("time"))
                last_time = last_time_by_asset.get(asset)
                if last_time is not None and effective_at <= last_time:
                    raise CollectorUnavailable("PAGINATION_ORDER")
                last_time_by_asset[asset] = effective_at
                rows.append((effective_at, raw))
                if len(rows) > _MAX_ROWS:
                    raise CollectorUnavailable("RESPONSE_TOO_LARGE")
            candidate = payload.get("next_page_url")
            if candidate is None:
                next_url = None
            elif isinstance(candidate, str) and self._valid_next_url(candidate):
                next_url = candidate
            else:
                raise CollectorUnavailable("INVALID_PAGINATION")
        else:
            if next_url is not None:
                raise CollectorUnavailable("RESPONSE_TOO_LARGE")

        observations: list[Observation] = []
        for effective_at, raw in rows:
            if effective_at >= cutoff:
                continue
            if effective_at != effective_at.replace(
                hour=0, minute=0, second=0, microsecond=0
            ):
                raise CollectorUnavailable("INVALID_TIMESTAMP")
            asset = str(raw["asset"])
            for provider_metric, (metric_code, unit) in self.metrics.items():
                raw_value = raw.get(provider_metric)
                if raw_value is None:
                    continue
                try:
                    value = Decimal(str(raw_value))
                except InvalidOperation as exc:
                    raise CollectorUnavailable("INVALID_VALUE") from exc
                if not value.is_finite():
                    raise CollectorUnavailable("INVALID_VALUE")
                observations.append(
                    Observation.create(
                        source_code=self.source.code,
                        source_url=self.source.urls[0],
                        market=self.source.market,
                        symbol=self.assets[asset],
                        effective_at=effective_at,
                        observed_at=as_of,
                        methodology_version=self.source.methodology_version,
                        value={
                            "metric": metric_code,
                            "value": str(value),
                            "unit": unit,
                            "dimensions": {
                                "providerMetric": provider_metric,
                                "frequency": "daily",
                            },
                        },
                        data_class="LIVE",
                    )
            )
            inflow, outflow = raw.get("FlowInExNtv"), raw.get("FlowOutExNtv")
            if inflow is not None and outflow is not None:
                try:
                    net_flow = Decimal(str(inflow)) - Decimal(str(outflow))
                except InvalidOperation as exc:
                    raise CollectorUnavailable("INVALID_VALUE") from exc
                if not net_flow.is_finite():
                    raise CollectorUnavailable("INVALID_VALUE")
                observations.append(
                    Observation.create(
                        source_code=self.source.code,
                        source_url=self.source.urls[0],
                        market=self.source.market,
                        symbol=self.assets[asset],
                        effective_at=effective_at,
                        observed_at=as_of,
                        methodology_version=self.source.methodology_version,
                        value={
                            "metric": "crypto.onchain.exchange_netflow_native",
                            "value": str(net_flow),
                            "unit": "native",
                            "dimensions": {"providerMetric": "FlowInExNtv-FlowOutExNtv", "frequency": "daily"},
                        },
                        data_class="LIVE",
                    )
                )
        return tuple(observations)

    def _valid_next_url(self, url: str) -> bool:
        base = urlsplit(self.source.urls[0])
        parsed = urlsplit(url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        return (
            parsed.scheme == "https"
            and parsed.hostname == base.hostname
            and parsed.path == base.path
            and not parsed.username
            and not parsed.password
            and not parsed.fragment
            and "next_page_token" in query
            and set(query) <= _ALLOWED_QUERY
        )


class CoinMetricsPriceHistoryCollector(CoinMetricsCollector):
    """Initial BTC daily price history for transparent local cycle models."""

    def __init__(self, *, transport: Transport | None = None) -> None:
        super().__init__(
            transport=transport,
            assets={"btc": "BTC"},
            metrics={"PriceUSD": _METRICS["PriceUSD"]},
            history_days=6_200,
        )


__all__ = ["CoinMetricsCollector", "CoinMetricsPriceHistoryCollector"]
