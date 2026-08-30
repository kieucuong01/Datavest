"""Pinned two-repository release and local Compose contracts."""

from copy import deepcopy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILES = (REPO_ROOT / "docker-compose.yml", REPO_ROOT / "docker-compose.datavest.yml")
APPROVED_SERVICES = {
    "migration",
    "postgres",
    "redis",
    "redis-jobs",
    "backend",
    "scheduler-worker",
    "celery-worker",
    "celery-beat",
    "frontend",
}
_INTERPOLATION = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^{}]*))?\}")


def _environment_map(value) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(key): str(item) for key, item in value.items()}
    result = {}
    for item in value or []:
        key, _, raw_value = str(item).partition("=")
        result[key] = raw_value
    return result


def _merge_compose_documents() -> dict:
    documents = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in COMPOSE_FILES]
    merged = deepcopy(documents[0])
    services = merged.setdefault("services", {})
    for name, override in documents[1]["services"].items():
        base = deepcopy(services.get(name, {}))
        base_environment = _environment_map(base.get("environment"))
        override_environment = _environment_map(override.get("environment"))
        base.update(deepcopy(override))
        if base_environment or override_environment:
            base["environment"] = {**base_environment, **override_environment}
        services[name] = base
    merged["name"] = documents[1].get("name", merged.get("name"))
    return merged


def _interpolate(value, environment: dict[str, str]):
    if isinstance(value, dict):
        return {key: _interpolate(item, environment) for key, item in value.items()}
    if isinstance(value, list):
        return [_interpolate(item, environment) for item in value]
    if not isinstance(value, str):
        return value
    previous = None
    while previous != value:
        previous = value

        def replace(match):
            name, default = match.groups()
            configured = environment.get(name)
            return configured if configured not in (None, "") else (default or "")

        value = _INTERPOLATION.sub(replace, value)
    return value


def _render_datavest_compose(flag_values: dict[str, str | None]) -> dict:
    environment = dict(os.environ)
    for name in (
        "BACKEND_LOCAL_IMAGE",
        "FRONTEND_IMAGE",
        "FRONTEND_TAG",
        "IMAGE_PREFIX",
        "IMAGE_TAG",
        "POSTGRES_IMAGE",
        "REDIS_IMAGE",
        "DATAVEST_SMART_INSIGHTS_ENABLED",
        "DATAVEST_PORTFOLIO_OPTIMIZER_ENABLED",
    ):
        environment.pop(name, None)
    environment["DATAVEST_RELEASE"] = "review-test"
    for name, value in flag_values.items():
        if value is None:
            environment.pop(name, None)
        else:
            environment[name] = value

    docker = shutil.which("docker")
    if docker:
        result = subprocess.run(
            [
                docker,
                "compose",
                "-f",
                str(COMPOSE_FILES[0]),
                "-f",
                str(COMPOSE_FILES[1]),
                "config",
                "--format",
                "json",
            ],
            cwd=REPO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    return _interpolate(_merge_compose_documents(), environment)


def test_release_manifest_pins_both_quantdinger_first_repositories():
    manifest = json.loads((REPO_ROOT / "deploy" / "datavest-release.json").read_text(encoding="utf-8"))

    assert manifest["product"] == "DataVest"
    assert manifest["poweredBy"] == "QuantDinger"
    assert manifest["tradingMode"] == "SIMULATED_ONLY"
    for component in ("backend", "frontend"):
        release = manifest[component]
        assert re.fullmatch(r"[0-9a-f]{7,40}", release["commit"])
        assert re.fullmatch(r"[0-9a-f]{40}", release["fullCommit"])
        assert release["fullCommit"].startswith(release["commit"])


def test_datavest_compose_source_union_is_exactly_approved():
    documents = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in COMPOSE_FILES]
    source_union = set().union(*(document["services"] for document in documents))

    assert source_union == APPROVED_SERVICES


def test_datavest_merged_compose_resolves_approved_services_and_images():
    compose = _render_datavest_compose({})
    services = compose["services"]

    assert compose["name"] == "datavest"
    assert set(services) == APPROVED_SERVICES
    for name in ("migration", "backend", "scheduler-worker", "celery-worker", "celery-beat"):
        assert services[name]["image"] == "datavest-backend:review-test"
    assert services["frontend"]["image"] == "datavest-frontend:review-test"
    assert services["postgres"]["image"] == "postgres:18.3-alpine"
    assert services["redis"]["image"] == "redis:8-alpine"
    assert services["redis-jobs"]["image"] == "redis:8-alpine"
    assert str(services["frontend"]["build"]["context"]).replace("\\", "/").endswith(
        "/frontend"
    )


def test_datavest_merged_compose_enables_smart_insights_and_optimizer_by_default():
    compose = _render_datavest_compose(
        {
            "DATAVEST_SMART_INSIGHTS_ENABLED": None,
            "DATAVEST_PORTFOLIO_OPTIMIZER_ENABLED": None,
        }
    )

    environment = _environment_map(compose["services"]["backend"]["environment"])
    assert environment["DATAVEST_SMART_INSIGHTS_ENABLED"] == "true"
    assert environment["DATAVEST_PORTFOLIO_OPTIMIZER_ENABLED"] == "true"


def test_datavest_merged_compose_feature_flags_interpolate_independently():
    for smart_insights, optimizer in (
        ("false", "false"),
        ("true", "false"),
        ("false", "true"),
        ("true", "true"),
    ):
        compose = _render_datavest_compose(
            {
                "DATAVEST_SMART_INSIGHTS_ENABLED": smart_insights,
                "DATAVEST_PORTFOLIO_OPTIMIZER_ENABLED": optimizer,
            }
        )
        environment = _environment_map(compose["services"]["backend"]["environment"])

        assert environment["DATAVEST_SMART_INSIGHTS_ENABLED"] == smart_insights
        assert environment["DATAVEST_PORTFOLIO_OPTIMIZER_ENABLED"] == optimizer


def test_local_env_example_uses_a_supported_api_process_role():
    env_example = (REPO_ROOT / "backend_api_python" / "env.example").read_text(encoding="utf-8")

    assert "QD_PROCESS_ROLE=api" in env_example
    assert "QD_PROCESS_ROLE=legacy" not in env_example
