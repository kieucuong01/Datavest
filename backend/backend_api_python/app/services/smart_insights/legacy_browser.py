"""Bounded browser acquisition for the legacy DataVest crypto sources.

The three sources in this module are public, fixed allow-listed pages.  The
browser is only used to obtain a rendered snapshot; source-specific parsers
still validate the resulting HTML before an observation can be persisted.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
import time
from typing import Any, Callable
from urllib.parse import urlsplit

from .collectors import CollectorUnavailable
from .contracts import Observation
from .sources import SourceDefinition


@dataclass(frozen=True, slots=True)
class BrowserDocument:
    html: str
    final_url: str
    observed_at: datetime


ReadyPredicate = Callable[[str], bool]


def _source_hosts(source: SourceDefinition) -> set[str]:
    return {
        parsed.hostname.lower()
        for raw_url in source.urls
        if (parsed := urlsplit(raw_url)).scheme == "https" and parsed.hostname
    }


async def _close_browser(browser: Any, process: Any) -> None:
    try:
        if browser is not None:
            targets = tuple(getattr(browser, "targets", ()))
            if targets:
                await asyncio.gather(
                    *(target.aclose() for target in targets),
                    return_exceptions=True,
                )
            try:
                await asyncio.wait_for(browser.aclose(), timeout=3)
            except Exception:
                pass
    finally:
        if process is not None and getattr(process, "returncode", None) is None:
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=3)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass


async def _fetch_nodriver(
    url: str,
    *,
    ready: ReadyPredicate,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> tuple[str, str]:
    results = await _fetch_nodriver_many(
        (url,), ready=ready, timeout_seconds=timeout_seconds, poll_interval_seconds=poll_interval_seconds
    )
    return results[0]


async def _fetch_nodriver_many(
    urls: tuple[str, ...],
    *,
    ready: ReadyPredicate,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> tuple[tuple[str, str], ...]:
    try:
        import nodriver
    except Exception as exc:  # pragma: no cover - dependency/runtime boundary
        raise CollectorUnavailable("BROWSER_UNAVAILABLE") from exc

    browser = None
    process = None
    try:
        try:
            browser = await nodriver.start(
                headless=True,
                browser_executable_path="/usr/bin/chromium",
                browser_args=[
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--window-size=1280,900",
                ],
                sandbox=False,
            )
        except Exception as exc:  # pragma: no cover - host runtime boundary
            raise CollectorUnavailable("BROWSER_LAUNCH_FAILED") from exc
        process = getattr(browser, "_process", None)
        page = await browser.get("about:blank")
        documents: list[tuple[str, str]] = []
        for url in urls:
            page = await page.get(url)
            deadline = time.monotonic() + timeout_seconds
            while True:
                try:
                    html = await page.get_content()
                except Exception:
                    html = ""
                if isinstance(html, str) and html.strip() and ready(html):
                    break
                if time.monotonic() >= deadline:
                    raise CollectorUnavailable("SCHEMA_DRIFT")
                await asyncio.sleep(poll_interval_seconds)
            try:
                final_url = await page.evaluate("window.location.href", return_by_value=True)
            except Exception:
                final_url = ""
            documents.append((html, final_url if isinstance(final_url, str) else ""))
        return tuple(documents)
    finally:
        await _close_browser(browser, process)


class NodriverBrowserClient:
    """Render one fixed public page with a hard outer timeout."""

    def __init__(
        self,
        *,
        browser_fetch: Callable[[str, ReadyPredicate], tuple[str, str]] | None = None,
        clock: Callable[[], datetime] | None = None,
        timeout_seconds: float = 60,
        poll_interval_seconds: float = 1,
        max_html_bytes: int = 20_000_000,
    ) -> None:
        if min(timeout_seconds, poll_interval_seconds, max_html_bytes) <= 0:
            raise ValueError("Browser limits must be positive")
        self._browser_fetch = browser_fetch
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._timeout_seconds = timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._max_html_bytes = max_html_bytes

    def fetch(
        self,
        source: SourceDefinition,
        url: str,
        *,
        ready: ReadyPredicate,
    ) -> BrowserDocument:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in _source_hosts(source):
            raise CollectorUnavailable("URL_NOT_ALLOWLISTED")
        if self._browser_fetch is not None:
            html, final_url = self._browser_fetch(url, ready)
        else:
            try:
                html, final_url = asyncio.run(
                    asyncio.wait_for(
                        _fetch_nodriver(
                            url,
                            ready=ready,
                            timeout_seconds=self._timeout_seconds,
                            poll_interval_seconds=self._poll_interval_seconds,
                        ),
                        timeout=self._timeout_seconds + 5,
                    )
                )
            except CollectorUnavailable:
                raise
            except (asyncio.TimeoutError, TimeoutError) as exc:
                raise CollectorUnavailable("TIMEOUT") from exc
            except Exception as exc:
                raise CollectorUnavailable("BROWSER_FETCH_FAILED") from exc
        if final_url != url:
            raise CollectorUnavailable("REDIRECT_REJECTED")
        if not isinstance(html, str) or not html.strip() or not ready(html):
            raise CollectorUnavailable("SCHEMA_DRIFT")
        if len(html.encode("utf-8")) > self._max_html_bytes:
            raise CollectorUnavailable("RESPONSE_TOO_LARGE")
        return BrowserDocument(html=html, final_url=final_url, observed_at=self._clock())

    def fetch_many(
        self,
        source: SourceDefinition,
        urls: tuple[str, ...],
        *,
        ready: ReadyPredicate,
    ) -> tuple[BrowserDocument, ...]:
        """Fetch a small allow-listed batch in one browser process.

        This is used for a fixed top-address cohort only; it deliberately does
        not expose a generic bulk scraping primitive.
        """
        if not urls or len(urls) > 20 or len(set(urls)) != len(urls):
            raise CollectorUnavailable("INVALID_BATCH")
        for url in urls:
            parsed = urlsplit(url)
            if parsed.scheme != "https" or parsed.hostname not in _source_hosts(source):
                raise CollectorUnavailable("URL_NOT_ALLOWLISTED")
        if self._browser_fetch is not None:
            return tuple(self.fetch(source, url, ready=ready) for url in urls)
        try:
            rows = asyncio.run(
                asyncio.wait_for(
                    _fetch_nodriver_many(
                        urls,
                        ready=ready,
                        timeout_seconds=self._timeout_seconds,
                        poll_interval_seconds=self._poll_interval_seconds,
                    ),
                    timeout=(self._timeout_seconds + 5) * len(urls),
                )
            )
        except CollectorUnavailable:
            raise
        except (asyncio.TimeoutError, TimeoutError) as exc:
            raise CollectorUnavailable("TIMEOUT") from exc
        except Exception as exc:
            raise CollectorUnavailable("BROWSER_FETCH_FAILED") from exc
        documents: list[BrowserDocument] = []
        for requested_url, (html, final_url) in zip(urls, rows, strict=True):
            if final_url != requested_url:
                raise CollectorUnavailable("REDIRECT_REJECTED")
            if not isinstance(html, str) or not html.strip() or not ready(html):
                raise CollectorUnavailable("SCHEMA_DRIFT")
            if len(html.encode("utf-8")) > self._max_html_bytes:
                raise CollectorUnavailable("RESPONSE_TOO_LARGE")
            documents.append(BrowserDocument(html=html, final_url=final_url, observed_at=self._clock()))
        return tuple(documents)


def observation(
    *,
    source: SourceDefinition,
    document: BrowserDocument,
    metric: str,
    value: object,
    unit: str,
    effective_at: datetime,
    symbol: str | None = None,
    dimensions: dict[str, str] | None = None,
    warnings: tuple[str, ...] = (),
    published_at: datetime | None = None,
) -> Observation:
    return Observation.create(
        source_code=source.code,
        source_url=document.final_url,
        market=source.market,
        symbol=symbol,
        effective_at=effective_at,
        observed_at=document.observed_at,
        published_at=published_at,
        methodology_version=source.methodology_version,
        value={
            "metric": metric,
            "value": str(value),
            "unit": unit,
            "dimensions": dimensions or {},
        },
        warnings=warnings,
        data_class="LIVE",
    )


__all__ = ["BrowserDocument", "NodriverBrowserClient", "ReadyPredicate", "observation"]
