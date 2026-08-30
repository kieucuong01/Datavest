"""Fail-closed evidence policies shared by opinions, AI and optimization."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .contracts import EvidencePolicyError


_REQUIRED_PROVENANCE = frozenset(
    {
        "id",
        "dataClass",
        "source",
        "sourceUrl",
        "observedAt",
        "effectiveAt",
        "methodologyVersion",
        "checksum",
    }
)


def require_live_evidence(
    evidence: Sequence[Mapping[str, object]],
) -> tuple[Mapping[str, object], ...]:
    """Return validated LIVE evidence or reject the entire calculation."""
    if not evidence:
        raise EvidencePolicyError("MISSING_EVIDENCE")
    accepted: list[Mapping[str, object]] = []
    for item in evidence:
        if item.get("dataClass") != "LIVE":
            raise EvidencePolicyError("DEMO_EVIDENCE_FORBIDDEN")
        if any(item.get(field) in (None, "") for field in _REQUIRED_PROVENANCE):
            raise EvidencePolicyError("INCOMPLETE_PROVENANCE")
        source_url = str(item.get("sourceUrl"))
        if not source_url.startswith("https://"):
            raise EvidencePolicyError("INCOMPLETE_PROVENANCE")
        checksum = str(item.get("checksum"))
        if len(checksum) != 64:
            raise EvidencePolicyError("INCOMPLETE_PROVENANCE")
        accepted.append(item)
    return tuple(accepted)


def build_live_explanation_context(
    evidence: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Build model context only after the production evidence gate passes."""
    return [dict(item) for item in require_live_evidence(evidence)]
