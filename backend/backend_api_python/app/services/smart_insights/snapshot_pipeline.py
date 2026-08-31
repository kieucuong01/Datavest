"""Immutable Smart Insights snapshot and evidence-link materialization."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from .contracts import EvidencePolicyError, Observation
from .evidence import require_live_evidence


METHODOLOGY_VERSION = "datavest-smart-insights-v1"


@dataclass(frozen=True, slots=True)
class OpinionDraft:
    symbol: str
    market: str
    stance: str
    score: float
    confidence: float
    rationale: Mapping[str, object]
    explanation: str | None
    explanation_model: str | None
    evidence_validated: bool
    data_class: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SnapshotDraft:
    as_of: datetime
    market: str
    status: str
    methodology_version: str
    summary: Mapping[str, object]
    evidence_checksum: str
    data_class: str
    evidence_ids: tuple[str, ...]
    opinions: tuple[OpinionDraft, ...]


class SnapshotRepository(Protocol):
    def load_snapshot_evidence(self, run_id: str) -> list[dict]: ...
    def publish_snapshot(self, draft: SnapshotDraft) -> tuple[str, bool]: ...


def _parse_time(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise EvidencePolicyError("INCOMPLETE_PROVENANCE")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EvidencePolicyError("INCOMPLETE_PROVENANCE")
    return parsed.astimezone(timezone.utc)


def observation_evidence(identifier: str, observation: Observation) -> dict[str, object]:
    return {
        "id": identifier,
        "market": observation.market,
        "symbol": observation.symbol,
        "source": observation.source_code,
        "sourceUrl": observation.source_url,
        "effectiveAt": observation.effective_at.isoformat(),
        "publishedAt": observation.published_at.isoformat() if observation.published_at else None,
        "observedAt": observation.observed_at.isoformat(),
        "methodologyVersion": observation.methodology_version,
        "warnings": list(observation.warnings),
        "checksum": observation.checksum,
        "dataClass": observation.data_class.value,
        "value": dict(observation.value),
    }


def build_snapshot_draft(
    evidence: Sequence[Mapping[str, object]],
    *,
    market: str,
    mode: str,
    as_of: datetime,
) -> SnapshotDraft:
    if not evidence:
        raise EvidencePolicyError("MISSING_EVIDENCE")
    normalized_mode = mode.strip().lower()
    if normalized_mode not in {"live", "demo"}:
        raise ValueError("invalid_mode")
    data_class = normalized_mode.upper()
    if normalized_mode == "live":
        accepted = require_live_evidence(evidence)
    else:
        accepted = tuple(evidence)
        if any(item.get("dataClass") != "DEMO" for item in accepted):
            raise EvidencePolicyError("LIVE_EVIDENCE_FORBIDDEN_IN_DEMO")
    if any(str(item.get("market", "")).lower() != market.lower() for item in accepted):
        raise EvidencePolicyError("MARKET_EVIDENCE_MISMATCH")

    ordered = tuple(sorted(accepted, key=lambda item: (str(item["checksum"]), str(item["id"]))))
    evidence_checksum = hashlib.sha256(
        json.dumps(
            [str(item["checksum"]) for item in ordered],
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    metrics = sorted(
        {
            str((item.get("value") or {}).get("metric"))
            for item in ordered
            if isinstance(item.get("value"), Mapping) and (item.get("value") or {}).get("metric")
        }
    )
    sources = sorted({str(item["source"]) for item in ordered})
    symbols = sorted({str(item["symbol"]) for item in ordered if item.get("symbol")})
    groups: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for item in ordered:
        if item.get("symbol"):
            groups[str(item["symbol"])].append(item)

    opinions: list[OpinionDraft] = []
    for symbol in sorted(groups):
        rows = groups[symbol]
        symbol_metrics = sorted(
            {
                str((row.get("value") or {}).get("metric"))
                for row in rows
                if isinstance(row.get("value"), Mapping)
            }
        )
        if len(symbol_metrics) < 2:
            continue
        opinions.append(
            OpinionDraft(
                symbol=symbol,
                market=market,
                stance="NEUTRAL",
                score=0.0,
                confidence=float(min(70, 30 + 10 * len(symbol_metrics))),
                rationale={
                    "status": "EVIDENCE_ONLY",
                    "metrics": symbol_metrics,
                    "warning": "No directional model has been validated for this evidence bundle.",
                },
                explanation=None,
                explanation_model=None,
                evidence_validated=True,
                data_class=data_class,
                evidence_ids=tuple(dict.fromkeys(str(row["id"]) for row in rows)),
            )
        )
    summary = {
        "metricCount": len(metrics),
        "observationCount": len(ordered),
        "sourceCount": len(sources),
        "sources": sources,
        "symbols": symbols,
        "metrics": metrics,
        "directionalModelStatus": "UNAVAILABLE",
    }
    status = "COMPLETE" if opinions else "PARTIAL"
    return SnapshotDraft(
        as_of=as_of.astimezone(timezone.utc),
        market=market.lower(),
        status=status,
        methodology_version=METHODOLOGY_VERSION,
        summary=summary,
        evidence_checksum=evidence_checksum,
        data_class=data_class,
        evidence_ids=tuple(dict.fromkeys(str(item["id"]) for item in ordered)),
        opinions=tuple(opinions),
    )


class SnapshotMaterializer:
    def __init__(self, *, repository: SnapshotRepository, clock=None) -> None:
        self.repository = repository
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def publish_for_run(self, run_id: str) -> list[dict[str, object]]:
        return self.publish_evidence(self.repository.load_snapshot_evidence(run_id))

    def publish_observations(
        self, rows: Sequence[tuple[str, Observation]]
    ) -> list[dict[str, object]]:
        return self.publish_evidence([observation_evidence(identifier, row) for identifier, row in rows])

    def publish_evidence(self, evidence: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
        grouped: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
        for item in evidence:
            grouped[(str(item["market"]).lower(), str(item["dataClass"]).lower())].append(item)
        result: list[dict[str, object]] = []
        for (market, mode), rows in sorted(grouped.items()):
            as_of = max((_parse_time(row["observedAt"]) for row in rows), default=self.clock())
            draft = build_snapshot_draft(rows, market=market, mode=mode, as_of=as_of)
            snapshot_id, created = self.repository.publish_snapshot(draft)
            result.append({"snapshotId": snapshot_id, "market": market, "created": created})
        return result


__all__ = [
    "OpinionDraft",
    "SnapshotDraft",
    "SnapshotMaterializer",
    "build_snapshot_draft",
    "observation_evidence",
]
