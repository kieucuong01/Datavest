from __future__ import annotations

import sys
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.errors import failure_code


def test_failure_code_does_not_depend_on_optional_upstream_error_helper():
    assert failure_code(TimeoutError("provider timed out")) == "provider_timeout"
    assert failure_code(RuntimeError("graph failed")) == "runner_failed"
