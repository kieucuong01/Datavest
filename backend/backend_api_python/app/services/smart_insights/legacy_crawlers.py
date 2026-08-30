"""Adapters that connect the legacy rendered collectors to QuantDinger."""

from __future__ import annotations

from datetime import datetime, timezone

from .coinglass import _parse_margin, _parse_maxpain
from .collectors import CollectorUnavailable
from .contracts import Observation
from .legacy_browser import BrowserDocument, NodriverBrowserClient, observation
from .sources import source_for_code


def _has_headers(html: str, headers: tuple[str, ...]) -> bool:
    lowered = html.casefold()
    return all(header.casefold() in lowered for header in headers) and "<tbody" in lowered


class CoinGlassMarginBrowserCollector:
    source_code = "coinglass-margin-borrow"

    def __init__(self, *, browser: NodriverBrowserClient | None = None) -> None:
        self.source = source_for_code(self.source_code)
        self.browser = browser or NodriverBrowserClient()

    def collect(self, as_of: datetime) -> tuple[Observation, ...]:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        document = self.browser.fetch(
            self.source,
            self.source.urls[0],
            ready=lambda html: _has_headers(
                html,
                ("Time", "Annualized Interest Rate", "Daily Interest Rate", "Hourly Interest Rate"),
            ),
        )
        values = _parse_margin(document.html, as_of)
        return tuple(
            observation(
                source=self.source,
                document=document,
                metric=metric,
                value=value,
                unit="percent",
                effective_at=effective_at,
                dimensions={"exchange": "Binance", "quote_asset": "USDT"},
            )
            for metric, value, effective_at in values
        )


class CoinGlassMaxPainBrowserCollector:
    source_code = "coinglass-liquidation-maxpain"

    def __init__(
        self,
        *,
        browser: NodriverBrowserClient | None = None,
        symbols: frozenset[str] = frozenset({"BTC", "ETH", "SOL"}),
    ) -> None:
        if not symbols:
            raise ValueError("At least one crypto symbol is required")
        self.source = source_for_code(self.source_code)
        self.browser = browser or NodriverBrowserClient()
        self.symbols = symbols

    def collect(self, as_of: datetime) -> tuple[Observation, ...]:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        document = self.browser.fetch(
            self.source,
            self.source.urls[0],
            ready=lambda html: "short max pain" in html.casefold() and "long max pain" in html.casefold() and "<tbody" in html.casefold(),
        )
        values = _parse_maxpain(document.html, as_of, self.symbols)
        return tuple(
            observation(
                source=self.source,
                document=document,
                metric=metric,
                value=value,
                unit="ratio" if "distance" in metric else "USD",
                effective_at=as_of.astimezone(timezone.utc),
                symbol=symbol,
                dimensions=dimensions,
            )
            for metric, symbol, value, dimensions in values
        )


__all__ = ["CoinGlassMarginBrowserCollector", "CoinGlassMaxPainBrowserCollector"]
