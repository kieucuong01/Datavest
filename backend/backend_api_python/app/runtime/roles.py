"""Explicit process roles for the backend deployment."""

from __future__ import annotations

import os
from enum import Enum


class ProcessRole(str, Enum):
    API = "api"
    SCHEDULER = "scheduler"
    CELERY = "celery"


def current_process_role() -> ProcessRole:
    raw = os.getenv("QD_PROCESS_ROLE", ProcessRole.API.value).strip().lower()
    try:
        return ProcessRole(raw)
    except ValueError as exc:
        allowed = ", ".join(role.value for role in ProcessRole)
        raise RuntimeError(f"Invalid QD_PROCESS_ROLE={raw!r}; expected one of: {allowed}") from exc
