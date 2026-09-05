"""Per-user filesystem boundaries for native TradingAgents state."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


class StateIsolationError(ValueError):
    """Raised when an identifier could escape its assigned state directory."""


def require_safe_identifier(value: str, *, field: str) -> str:
    if not isinstance(value, str) or not _SAFE_IDENTIFIER.fullmatch(value):
        raise StateIsolationError(f"{field} must be a safe identifier")
    return value


@dataclass(frozen=True)
class UserStatePaths:
    root: Path
    results_dir: Path
    reports_dir: Path
    data_cache_dir: Path
    checkpoints_dir: Path
    memory_log_path: Path

    def create_directories(self) -> None:
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.data_cache_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.memory_log_path.parent.mkdir(parents=True, exist_ok=True)


def resolve_user_state(state_root: str | Path, user_id: str) -> UserStatePaths:
    """Return paths confined to one user without accepting path-like IDs."""

    safe_user_id = require_safe_identifier(user_id, field="user_id")
    root = Path(state_root).resolve()
    user_root = (root / "users" / safe_user_id).resolve()
    if not user_root.is_relative_to(root):
        raise StateIsolationError("user state must remain inside the configured state root")

    results_dir = user_root / "results"
    data_cache_dir = user_root / "cache"
    return UserStatePaths(
        root=user_root,
        results_dir=results_dir,
        reports_dir=results_dir / "reports",
        data_cache_dir=data_cache_dir,
        checkpoints_dir=data_cache_dir / "checkpoints",
        memory_log_path=user_root / "memory" / "trading_memory.md",
    )
