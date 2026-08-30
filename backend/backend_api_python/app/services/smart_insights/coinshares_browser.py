"""CoinShares rendered-page collector, adapted from the legacy DataVest worker."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from importlib.metadata import version
import re
from typing import Any, Protocol, Sequence
from urllib.parse import urljoin, urlsplit

from app.utils.http import global_session

from .collectors import CollectorUnavailable
from .contracts import Observation
from .legacy_browser import BrowserDocument, NodriverBrowserClient, observation
from .sources import source_for_code


_SOURCE_URL = "https://coinshares.com/insights/research-data/"
_REPORT_RE = re.compile(
    r"(?:https://coinshares\.com)?(?:/us)?/insights/research-data/"
    r"fund-flows-(\d{1,2})-(\d{1,2})-(\d{2}|\d{4})/",
    re.IGNORECASE,
)
_PUBLISHED_RE = re.compile(
    r"published\s+on\s+([A-Za-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?,\s*(\d{4})",
    re.IGNORECASE,
)
_PERIOD_RE = re.compile(
    r"data\s+available\s+as\s+(?:at|of)(?:\s+close)?\s+(\d{1,2}\s+[A-Za-z]+\s+\d{4})",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"^\(?-?\$?\d{1,3}(?:,\d{3})*(?:\.\d+)?\)?$")
_MILLION = Decimal("1000000")
_TOLERANCE = Decimal("100000")
_TRACKED_ASSETS = frozenset({"Bitcoin", "Ethereum", "Solana", "XRP", "Total"})
_IMAGE_HOSTS = frozenset({"a.storyblok.com", "coinshares.com", "www.coinshares.com"})


@dataclass(frozen=True, slots=True)
class OcrToken:
    text: str
    confidence: Decimal
    box: tuple[int, int, int, int]


class OcrEngine(Protocol):
    version: str

    def recognize(self, image: bytes) -> tuple[OcrToken, ...]: ...


@dataclass(frozen=True, slots=True)
class CoinSharesRow:
    label: str
    week_flow_usd: Decimal
    aum_usd: Decimal


@dataclass(frozen=True, slots=True)
class CoinSharesTable:
    dimension: str
    rows: tuple[CoinSharesRow, ...]
    effective_at: datetime
    minimum_confidence: Decimal


class RapidOcrEngine:
    def __init__(self) -> None:
        try:
            from rapidocr import RapidOCR
        except Exception as exc:  # pragma: no cover - dependency/runtime boundary
            raise CollectorUnavailable("OCR_UNAVAILABLE") from exc
        try:
            self._engine = RapidOCR()
            self.version = f"rapidocr-{version('rapidocr')}"
        except Exception as exc:  # pragma: no cover - model/runtime boundary
            raise CollectorUnavailable("OCR_UNAVAILABLE") from exc

    def recognize(self, image: bytes) -> tuple[OcrToken, ...]:
        try:
            result = self._engine(image)
            boxes, texts, scores = result.boxes, result.txts, result.scores
            if boxes is None or texts is None or scores is None:
                return ()
            tokens: list[OcrToken] = []
            for box, text, score in zip(boxes, texts, scores, strict=True):
                points = tuple((float(point[0]), float(point[1])) for point in box)
                if len(points) != 4:
                    raise ValueError("OCR_LAYOUT_DRIFT")
                tokens.append(OcrToken(
                    text=str(text),
                    confidence=Decimal(str(score)),
                    box=(round(min(p[0] for p in points)), round(min(p[1] for p in points)), round(max(p[0] for p in points)), round(max(p[1] for p in points))),
                ))
            return tuple(tokens)
        except CollectorUnavailable:
            raise
        except Exception as exc:
            raise CollectorUnavailable("OCR_LAYOUT_DRIFT") from exc


class _ArticleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.images: list[tuple[str, str]] = []
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() == "img":
            values = {name.casefold(): value or "" for name, value in attrs}
            source = values.get("src") or values.get("data-src")
            if source:
                self.images.append((source, values.get("alt", "")))

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if value:
            self.text.append(value)


def _published_at(html: str) -> datetime:
    parser = _ArticleParser()
    parser.feed(html)
    match = _PUBLISHED_RE.search(" ".join(parser.text))
    if match is None:
        raise CollectorUnavailable("MISSING_PUBLISHED_AT")
    try:
        return datetime.strptime(
            f"{match.group(1)} {match.group(2)} {match.group(3)}", "%b %d %Y"
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.strptime(
                f"{match.group(1)} {match.group(2)} {match.group(3)}", "%B %d %Y"
            ).replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise CollectorUnavailable("INVALID_TIMESTAMP") from exc


def _discover_report(html: str) -> str:
    candidates: list[tuple[datetime, str]] = []
    for match in _REPORT_RE.finditer(html):
        year = int(match.group(3))
        if year < 100:
            year += 2000
        try:
            report_date = datetime(year, int(match.group(2)), int(match.group(1)), tzinfo=timezone.utc)
        except ValueError:
            continue
        url = urljoin("https://coinshares.com", match.group(0))
        candidates.append((report_date, url))
    if not candidates:
        raise CollectorUnavailable("SCHEMA_DRIFT")
    return max(candidates, key=lambda item: (item[0], item[1]))[1]


def _image_urls(html: str, report_url: str) -> dict[str, str]:
    parser = _ArticleParser()
    parser.feed(html)
    result: dict[str, str] = {}
    for raw_url, alt in parser.images:
        normalized = " ".join(alt.casefold().split())
        kind = "asset" if "ranked flows detail" in normalized else "region" if "flows by exchange country" in normalized else None
        if kind is None:
            continue
        url = urljoin(report_url, raw_url)
        if urlsplit(url).scheme != "https" or urlsplit(url).hostname not in _IMAGE_HOSTS:
            raise CollectorUnavailable("REDIRECT_REJECTED")
        if kind in result:
            raise CollectorUnavailable("OCR_LAYOUT_DRIFT")
        result[kind] = url
    if set(result) != {"asset", "region"}:
        raise CollectorUnavailable("MISSING_TABLE")
    return result


def _download_image(url: str) -> bytes:
    try:
        response = global_session.get(url, timeout=(10, 30), allow_redirects=False, stream=True)
        if response.status_code != 200 or str(response.url) != url:
            raise CollectorUnavailable("INVALID_RESPONSE")
        content_type = str(response.headers.get("content-type", "")).split(";", 1)[0].casefold()
        if content_type not in {"image/png", "image/jpeg", "image/webp"}:
            raise CollectorUnavailable("INVALID_RESPONSE")
        body = response.content
        if len(body) > 10_000_000:
            raise CollectorUnavailable("RESPONSE_TOO_LARGE")
        return body
    except CollectorUnavailable:
        raise
    except Exception as exc:
        raise CollectorUnavailable("SOURCE_UNAVAILABLE") from exc


def _center_x(token: OcrToken) -> Decimal:
    return Decimal(token.box[0] + token.box[2]) / Decimal(2)


def _center_y(token: OcrToken) -> Decimal:
    return Decimal(token.box[1] + token.box[3]) / Decimal(2)


def _groups(tokens: Sequence[OcrToken]) -> tuple[tuple[OcrToken, ...], ...]:
    groups: list[list[OcrToken]] = []
    for token in sorted(tokens, key=lambda item: (_center_y(item), _center_x(item))):
        if not groups:
            groups.append([token])
            continue
        center = sum((_center_y(item) for item in groups[-1]), Decimal(0)) / Decimal(len(groups[-1]))
        tolerance = max(Decimal(12), Decimal(token.box[3] - token.box[1]) / Decimal(2))
        if abs(_center_y(token) - center) <= tolerance:
            groups[-1].append(token)
        else:
            groups.append([token])
    return tuple(tuple(sorted(group, key=_center_x)) for group in groups)


def _money(value: str) -> Decimal:
    cleaned = value.strip().replace(" ", "")
    if not _NUMBER.fullmatch(cleaned):
        raise CollectorUnavailable("OCR_LAYOUT_DRIFT")
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    if negative:
        cleaned = cleaned[1:-1]
    try:
        amount = Decimal(cleaned.replace("$", "").replace(",", "")) * _MILLION
    except InvalidOperation as exc:
        raise CollectorUnavailable("OCR_LAYOUT_DRIFT") from exc
    return -amount if negative else amount


def _effective_at(tokens: Sequence[OcrToken], minimum_confidence: Decimal) -> datetime:
    for token in tokens:
        match = _PERIOD_RE.search(token.text)
        if match is None:
            continue
        if token.confidence < minimum_confidence:
            raise CollectorUnavailable("OCR_LOW_CONFIDENCE")
        for fmt in ("%d %B %Y", "%d %b %Y"):
            try:
                return datetime.strptime(match.group(1), fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        raise CollectorUnavailable("INVALID_TIMESTAMP")
    raise CollectorUnavailable("MISSING_PERIOD")


def _header_key(value: str, dimension: str) -> str | None:
    normalized = re.sub(r"[^a-z]", "", value.casefold())
    if dimension == "asset" and normalized == "asset":
        return "label"
    if dimension == "region" and normalized in {"country", "region"}:
        return "label"
    if normalized in {"weekflow", "weekflows"}:
        return "week"
    if normalized == "aum":
        return "aum"
    return None


def reconstruct_table(
    tokens: Sequence[OcrToken],
    *,
    dimension: str,
    minimum_confidence: Decimal = Decimal("0.90"),
) -> CoinSharesTable:
    if dimension not in {"asset", "region"} or not tokens:
        raise CollectorUnavailable("OCR_LAYOUT_DRIFT")
    if not any("us$m" in token.text.casefold().replace(" ", "") for token in tokens):
        raise CollectorUnavailable("INVALID_UNIT")
    effective_at = _effective_at(tokens, minimum_confidence)
    grouped = _groups(tokens)
    header: tuple[OcrToken, ...] | None = None
    columns: list[tuple[Decimal, str]] = []
    for group in grouped:
        keyed = [(_center_x(token), key) for token in group if (key := _header_key(token.text, dimension))]
        if {key for _, key in keyed} >= {"label", "week", "aum"}:
            if header is not None:
                raise CollectorUnavailable("OCR_LAYOUT_DRIFT")
            header = group
            columns = sorted(keyed)
    if header is None:
        raise CollectorUnavailable("OCR_LAYOUT_DRIFT")
    if any(token.confidence < minimum_confidence for token in header):
        raise CollectorUnavailable("OCR_LOW_CONFIDENCE")
    header_y = max(_center_y(token) for token in header)
    rows: list[CoinSharesRow] = []
    used_confidences: list[Decimal] = []
    seen: set[str] = set()
    for group in grouped:
        if min(_center_y(token) for token in group) <= header_y:
            continue
        if any(marker in " ".join(token.text for token in group).casefold() for marker in ("source:", "data available")):
            continue
        assigned: dict[str, list[OcrToken]] = {"label": [], "week": [], "aum": []}
        for token in group:
            _, key = min(columns, key=lambda item: abs(item[0] - _center_x(token)))
            if key in assigned:
                assigned[key].append(token)
        if not any(assigned.values()):
            continue
        if len(assigned["label"]) != 1 or len(assigned["week"]) != 1 or len(assigned["aum"]) != 1:
            raise CollectorUnavailable("OCR_LAYOUT_DRIFT")
        used = (assigned["label"][0], assigned["week"][0], assigned["aum"][0])
        if any(token.confidence < minimum_confidence for token in used):
            raise CollectorUnavailable("OCR_LOW_CONFIDENCE")
        used_confidences.extend(token.confidence for token in used)
        label = assigned["label"][0].text.strip()
        if not label or label.casefold() in seen:
            raise CollectorUnavailable("DUPLICATE_SERIES")
        seen.add(label.casefold())
        rows.append(CoinSharesRow(label=label, week_flow_usd=_money(assigned["week"][0].text), aum_usd=_money(assigned["aum"][0].text)))
    if len(rows) < 2 or any(row.aum_usd < 0 for row in rows):
        raise CollectorUnavailable("OCR_LAYOUT_DRIFT")
    total = next((row for row in rows if row.label.casefold() == "total"), None)
    non_total = tuple(row for row in rows if row.label.casefold() != "total")
    if dimension == "region" and total is None:
        raise CollectorUnavailable("OCR_LAYOUT_DRIFT")
    if total is not None and abs(sum((row.week_flow_usd for row in non_total), Decimal(0)) - total.week_flow_usd) > _TOLERANCE:
        raise CollectorUnavailable("RECONCILIATION_FAILED")
    return CoinSharesTable(dimension=dimension, rows=tuple(rows), effective_at=effective_at, minimum_confidence=min(used_confidences))


class CoinSharesBrowserCollector:
    source_code = "coinshares-weekly"

    def __init__(
        self,
        *,
        browser: NodriverBrowserClient | None = None,
        ocr_engine: OcrEngine | None = None,
    ) -> None:
        self.source = source_for_code(self.source_code)
        self.browser = browser or NodriverBrowserClient()
        self.ocr_engine = ocr_engine

    def collect(self, as_of: datetime) -> tuple[Observation, ...]:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        index = self.browser.fetch(self.source, _SOURCE_URL, ready=lambda html: bool(_REPORT_RE.search(html)))
        report_url = _discover_report(index.html)
        article = self.browser.fetch(self.source, report_url, ready=lambda html: "ranked flows detail" in html.casefold() and "flows by exchange country" in html.casefold())
        published_at = _published_at(article.html)
        if published_at > as_of.astimezone(timezone.utc):
            raise CollectorUnavailable("INVALID_TIMESTAMP")
        image_urls = _image_urls(article.html, report_url)
        engine = self.ocr_engine or RapidOcrEngine()
        tables = {
            kind: reconstruct_table(engine.recognize(_download_image(url)), dimension=kind)
            for kind, url in image_urls.items()
        }
        if tables["asset"].effective_at != tables["region"].effective_at:
            raise CollectorUnavailable("RECONCILIATION_FAILED")
        effective_at = tables["asset"].effective_at
        if effective_at > published_at:
            raise CollectorUnavailable("INVALID_TIMESTAMP")
        rows: list[Observation] = []
        for table in tables.values():
            for item in table.rows:
                symbol = {"Bitcoin": "BTC", "Ethereum": "ETH", "Solana": "SOL", "XRP": "XRP"}.get(item.label)
                dimensions = {"dimension": table.dimension, table.dimension: item.label, "source_unit": "US$m", "ocr_engine": getattr(engine, "version", "unknown")}
                for metric, value in (("crypto.coinshares.net_flow_usd", item.week_flow_usd), ("crypto.coinshares.aum_usd", item.aum_usd)):
                    rows.append(observation(source=self.source, document=article, metric=metric, value=value, unit="USD", effective_at=effective_at, symbol=symbol, dimensions=dimensions, published_at=published_at))
        return tuple(rows)


__all__ = ["CoinSharesBrowserCollector", "OcrToken", "RapidOcrEngine", "reconstruct_table"]
