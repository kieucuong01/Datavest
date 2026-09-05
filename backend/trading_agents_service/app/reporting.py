"""Artifact metadata for reports written by the native TradingAgents graph."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .state import UserStatePaths, require_safe_identifier


class ReportArtifactError(RuntimeError):
    """Raised when the upstream graph writes outside its assigned report root."""


@dataclass(frozen=True)
class RunArtifact:
    path: Path
    sha256: str
    size_bytes: int


def save_native_report(
    graph: Any,
    *,
    final_state: dict[str, Any],
    ticker: str,
    run_id: str,
    paths: UserStatePaths,
) -> RunArtifact:
    """Invoke upstream report writing, then record immutable file metadata."""

    report_root = paths.reports_dir / "runs" / require_safe_identifier(run_id, field="run_id")
    report_path = Path(graph.save_reports(final_state, ticker, save_path=report_root)).resolve()
    resolved_root = report_root.resolve()
    if not report_path.is_relative_to(resolved_root):
        raise ReportArtifactError("upstream report must remain inside the user report root")
    if not report_path.is_file():
        raise ReportArtifactError("upstream report was not created")

    content = report_path.read_bytes()
    return RunArtifact(
        path=report_path,
        sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
    )
