"""Scheduler process entrypoint."""

from __future__ import annotations

import os


SCHEDULER_HEARTBEAT_INTERVAL_SECONDS = 30


def run_scheduler_loop(*, shutdown, heartbeat, start_services) -> None:
    """Run scheduler services while keeping their durable health record fresh."""
    heartbeat.record_running()
    try:
        start_services()
        while not shutdown.event.wait(SCHEDULER_HEARTBEAT_INTERVAL_SECONDS):
            heartbeat.record_running()
    finally:
        heartbeat.mark_stopped()


def main() -> None:
    os.environ["QD_PROCESS_ROLE"] = "scheduler"

    from app import create_app
    from app.runtime.process import ShutdownSignal
    from app.runtime.worker_heartbeat import WorkerHeartbeat
    from app.startup import _start_scheduler_services
    app = create_app(register_http_routes=False)
    shutdown = ShutdownSignal()
    shutdown.install()
    with app.app_context():
        run_scheduler_loop(
            shutdown=shutdown,
            heartbeat=WorkerHeartbeat("scheduler"),
            start_services=_start_scheduler_services,
        )


if __name__ == "__main__":
    main()
