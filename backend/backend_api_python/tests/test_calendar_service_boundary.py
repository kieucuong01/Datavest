from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_calendar_uses_system_manager_but_non_root_browser():
    unit = (ROOT / 'backend/backend_api_python/calendar_worker/datavest-calendar.service').read_text()
    assert 'User=datavest-deploy' in unit
    assert 'Group=datavest-deploy' in unit
    assert 'NoNewPrivileges=false' in unit
    for protection in ('ProtectSystem=strict', 'ProtectHome=true', 'PrivateTmp=true', 'MemoryMax=700M'):
        assert protection in unit
    assert '--no-sandbox' not in unit


def test_deploy_cannot_recreate_broken_user_calendar_timer():
    deploy = (ROOT / 'deploy/vps/deploy.sh').read_text()
    assert 'user_systemctl enable --now datavest-calendar.timer' not in deploy
    assert 'systemctl is-active --quiet datavest-calendar.timer' in deploy
    installer = (ROOT / 'deploy/vps/install-calendar.sh').read_text()
    assert 'disable --now datavest-calendar.timer' in installer
    assert '/etc/systemd/system' in installer
    assert 'systemctl enable --now datavest-calendar.timer' in installer
