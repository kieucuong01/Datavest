"""Fail-closed runtime feature flags for DataVest surfaces."""

from __future__ import annotations

import os


_ENABLED_VALUES = frozenset({"1", "true", "yes", "on"})


def is_enabled(env_name: str) -> bool:
    """Return true only when a feature flag is explicitly enabled."""
    return os.getenv(env_name, "").strip().lower() in _ENABLED_VALUES


__all__ = ["is_enabled"]
