"""Release contracts for the private TradingAgents VPS runtime."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_vps_release_packages_and_starts_the_private_tradingagents_service():
    workflow = (REPO_ROOT / ".github" / "workflows" / "deploy-vps.yml").read_text(encoding="utf-8")
    deploy_script = (REPO_ROOT / "deploy" / "vps" / "deploy.sh").read_text(encoding="utf-8")
    unit_path = REPO_ROOT / "deploy" / "vps" / "datavest-trading-agents.service"
    celery_unit = (REPO_ROOT / "deploy" / "vps" / "datavest-celery.service").read_text(encoding="utf-8")
    environment = (REPO_ROOT / "deploy" / "vps" / "configure_env.py").read_text(encoding="utf-8")
    manual_deploy = (REPO_ROOT / "scripts" / "deploy-vps.ps1").read_text(encoding="utf-8")

    assert unit_path.is_file()
    unit = unit_path.read_text(encoding="utf-8")

    assert "backend/trading_agents_service/ package/backend/trading_agents_service/" in workflow
    assert "backend/third_party/tradingagents/ package/backend/third_party/tradingagents/" in workflow
    assert "datavest-trading-agents.service" in workflow
    assert "deploy/vps/datavest-celery.service" in workflow
    assert "deploy/vps/configure_env.py" in workflow
    assert "trading_agents_service/requirements.lock" in deploy_script
    assert "third_party/tradingagents" in deploy_script
    assert "trading_agents_runtime_hash" in deploy_script
    assert "find tradingagents cli pyproject.toml" in deploy_script
    assert "from tradingagents.agents.utils.progress import bind_progress_sink" in deploy_script
    assert "python3 \"$shared/configure_env.py\" /dev/null \"$env_file\"" in deploy_script
    assert "datavest-trading-agents" in deploy_script
    assert "datavest-celery.service" in deploy_script
    assert 'install -m 0644 "$shared/datavest-celery.service" "$HOME/.config/systemd/user/datavest-celery.service"' in deploy_script
    assert "user_systemctl cat datavest-celery | grep -F -- '-Q jobs,ai,maintenance,trading-agents'" in deploy_script
    assert "127.0.0.1:8080/internal/health" in deploy_script
    assert "DATAVEST_TRADING_AGENTS_ENABLED" in environment
    assert "DATAVEST_TRADING_AGENTS_SERVICE_SECRET" in environment
    assert "DATAVEST_TRADING_AGENTS_CALLBACK_SECRET" in environment
    assert "DATAVEST_TRADING_AGENTS_SERVICE_URL" in environment
    assert "backend/trading_agents_service" in manual_deploy
    assert "backend/third_party/tradingagents" in manual_deploy
    assert "configure_env.py" in manual_deploy
    assert "datavest-celery.service" in manual_deploy
    assert "--host 127.0.0.1" in unit
    assert "NoNewPrivileges=true" in unit
    assert "ProtectSystem=strict" in unit
    assert "ReadWritePaths=/opt/datavest/shared/data/trading-agents" in unit
    assert "-Q jobs,ai,maintenance,trading-agents" in celery_unit


def test_vps_prunes_only_unreferenced_releases_before_installing_new_venv():
    deploy_script = (REPO_ROOT / "deploy" / "vps" / "deploy.sh").read_text(encoding="utf-8")

    assert 'previous_release="$(readlink -f "$root/previous")"' in deploy_script
    assert '[[ "$candidate" == "$old_release" || "$candidate" == "$previous_release" ]] && continue' in deploy_script
    assert '[[ "$name" =~ ^[0-9a-f]{40}$ ]] || continue' in deploy_script
    assert 'rm -rf -- "$candidate"' in deploy_script
    assert deploy_script.index('echo "deploy_storage_before=') < deploy_script.index('rm -rf -- "$candidate"')
    assert deploy_script.index('rm -rf -- "$candidate"') < deploy_script.index('python3 -m venv "$release/.venv"')
    assert 'PIP_NO_CACHE_DIR=1' in deploy_script
