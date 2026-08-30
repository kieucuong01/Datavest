"""Durable heartbeat records for long-lived backend process roles."""

from __future__ import annotations

import json
import socket
from typing import Any

from app.utils.db import get_db_connection


class WorkerHeartbeat:
    def __init__(
        self,
        role: str,
        *,
        worker_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.role = role
        self.worker_id = worker_id or f"{role}:{socket.gethostname()}"
        self.metadata_json = json.dumps(metadata or {})

    def record_running(self) -> None:
        with get_db_connection() as db:
            cur = db.cursor()
            try:
                cur.execute(
                    """
                    INSERT INTO qd_worker_heartbeats
                        (worker_id, role, status, metadata_json, started_at, heartbeat_at)
                    VALUES (?, ?, 'running', ?::jsonb, NOW(), NOW())
                    ON CONFLICT (worker_id) DO UPDATE
                    SET role = EXCLUDED.role, status = 'running',
                        metadata_json = EXCLUDED.metadata_json,
                        heartbeat_at = NOW(), updated_at = NOW()
                    RETURNING worker_id
                    """,
                    (self.worker_id, self.role, self.metadata_json),
                )
                db.commit()
            finally:
                cur.close()
    def mark_stopped(self) -> None:
        with get_db_connection() as db:
            cur = db.cursor()
            try:
                cur.execute(
                    """
                    UPDATE qd_worker_heartbeats
                    SET status = 'stopped', heartbeat_at = NOW(), updated_at = NOW()
                    WHERE worker_id = ?
                    """,
                    (self.worker_id,),
                )
                db.commit()
            finally:
                cur.close()
