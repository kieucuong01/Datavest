from __future__ import annotations

import sys
from pathlib import Path

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.state import StateIsolationError, resolve_user_state


def test_parallel_runs_isolate_provider_language_and_fetch_context():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from tradingagents.dataflows.config import get_config, set_config, isolated_config
    from tradingagents.agents.analysts.sentiment_analyst import _run_bounded_fetch

    original = get_config()
    barrier = Barrier(2)

    def run(language):
        with isolated_config():
            set_config({"output_language": language, "data_cache_dir": language})
            barrier.wait(timeout=5)
            config = _run_bounded_fetch(get_config, label="test", timeout_seconds=2)
            return config["output_language"], config["data_cache_dir"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(run, ["Vietnamese", "English"])) == [("Vietnamese", "Vietnamese"), ("English", "English")]
    assert get_config() == original


def test_user_state_paths_are_isolated_and_reject_traversal(tmp_path: Path) -> None:
    user_a = resolve_user_state(tmp_path, "user-a")
    user_b = resolve_user_state(tmp_path, "user-b")
    user_a.create_directories()
    user_b.create_directories()

    assert user_a.root != user_b.root
    assert user_a.memory_log_path != user_b.memory_log_path
    assert user_a.reports_dir != user_b.reports_dir
    assert user_a.checkpoints_dir != user_b.checkpoints_dir
    assert user_a.memory_log_path.is_relative_to(user_a.root)
    assert user_b.memory_log_path.is_relative_to(user_b.root)
    assert user_a.reports_dir.is_dir()
    assert user_b.checkpoints_dir.is_dir()

    with pytest.raises(StateIsolationError, match="safe identifier"):
        resolve_user_state(tmp_path, "user-a/../user-b")
