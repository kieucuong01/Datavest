#!/usr/bin/env python3
"""Execute a command with a dotenv file without evaluating shell syntax."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key.replace("_", "").isalnum():
            raise ValueError(f"invalid environment key: {key!r}")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if "\x00" in value or "\n" in value:
            raise ValueError(f"invalid environment value for {key}")
        values[key] = value
    return values


def main() -> int:
    if len(sys.argv) < 5 or sys.argv[1] != "--cwd":
        print("usage: env_exec.py --cwd DIR ENV_FILE COMMAND [ARGS...]", file=sys.stderr)
        return 2
    cwd = Path(sys.argv[2]).resolve(strict=True)
    env_path = Path(sys.argv[3]).resolve(strict=True)
    command = sys.argv[4:]
    env = os.environ.copy()
    env.update(read_env(env_path))
    os.chdir(cwd)
    os.execvpe(command[0], command, env)
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
