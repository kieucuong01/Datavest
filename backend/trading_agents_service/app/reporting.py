"""Artifact metadata for reports written by the native TradingAgents graph."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .state import UserStatePaths, require_safe_identifier


_SAFE_ARTIFACT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,159}$")


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


def read_native_report(
    *,
    paths: UserStatePaths,
    run_id: str,
    artifact_name: str,
    max_bytes: int = 4 * 1024 * 1024,
) -> tuple[bytes, str]:
    """Read one persisted report without permitting a path to escape its run."""

    clean_run_id = require_safe_identifier(run_id, field="run_id")
    clean_name = str(artifact_name or "").strip()
    if not _SAFE_ARTIFACT_NAME.fullmatch(clean_name):
        raise ReportArtifactError("artifact_name must be a safe report filename")
    if not clean_name.endswith(".md"):
        raise ReportArtifactError("only native markdown reports can be retrieved")
    report_root = (paths.reports_dir / "runs" / clean_run_id).resolve()
    candidate = (report_root / clean_name).resolve()
    if not candidate.is_relative_to(report_root) or not candidate.is_file():
        raise ReportArtifactError("native report is unavailable")
    size = candidate.stat().st_size
    if size < 0 or size > max_bytes:
        raise ReportArtifactError("native report exceeds the retrieval limit")
    return candidate.read_bytes(), "text/markdown; charset=utf-8"
