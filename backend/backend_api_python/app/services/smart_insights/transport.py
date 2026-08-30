"""Bounded HTTP transport for public Smart Insights sources."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.utils.http import global_session

from .collectors import CollectorUnavailable


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    url: str
    body: bytes


class Transport(Protocol):
    def fetch(
        self,
        url: str,
        *,
        timeout_seconds: float,
        max_bytes: int,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse: ...


class RequestsTransport:
    def fetch(
        self,
        url: str,
        *,
        timeout_seconds: float,
        max_bytes: int,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        try:
            response = global_session.get(
                url,
                timeout=timeout_seconds,
                allow_redirects=False,
                stream=True,
                headers=headers,
            )
            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise CollectorUnavailable("RESPONSE_TOO_LARGE")
                chunks.append(chunk)
            return HttpResponse(int(response.status_code), str(response.url), b"".join(chunks))
        except CollectorUnavailable:
            raise
        except Exception as exc:
            raise CollectorUnavailable("SOURCE_UNAVAILABLE") from exc


__all__ = ["HttpResponse", "RequestsTransport", "Transport"]
