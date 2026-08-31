# DataVest VPS deployment

DataVest runs directly on the shared VPS to minimize RAM and disk usage. Nginx
serves the built Vue files, Gunicorn/Celery/Celery Beat/scheduler run as bounded systemd
services, and DataVest uses its own PostgreSQL database plus isolated Redis
namespace/database numbers. Tử Vi and Radar BDS services are not restarted by
this deployment.

## Private operator files

Files below `.local/deploy/` are ignored by Git:

- `deploy.env`: VPS address, deploy user, port and SSH key path;
- `datavest_ci_ed25519`: dedicated deployment private key;
- `.env.production`: backup of `/opt/datavest/shared/.env`.

Never add them with `git add -f`. The server env is authoritative. It contains
the generated DataVest database/admin secrets. DeepSeek is configured separately
for DataVest; deployment never reads another application's `.env`.

## Automatic deployment

Every push to `main` runs `.github/workflows/deploy-vps.yml`:

1. install pinned frontend dependencies and build Vue;
2. package backend source and static frontend under the full Git SHA;
3. checksum and upload over locked SSH;
4. create a release virtualenv, install the lockfile and back up PostgreSQL;
5. run migrations, switch `/opt/datavest/current`, restart only DataVest units;
6. verify local readiness and public HTTPS.

GitHub Actions secrets:

- `DATAVEST_VPS_HOST`
- `DATAVEST_VPS_PORT`
- `DATAVEST_VPS_USER`
- `DATAVEST_VPS_SSH_KEY`
- `DATAVEST_VPS_KNOWN_HOSTS`

Application/API/database secrets remain only on the VPS and in the ignored local
backup; they are not GitHub secrets.

## Manual deployment

Use a clean checkout at the exact pushed commit:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/deploy-vps.ps1
```

The wrapper refuses a dirty tree. It performs the same build/package/upload and
remote activation as GitHub Actions.

## Common operations

```bash
systemctl --user status datavest-api datavest-celery datavest-beat datavest-scheduler
journalctl --user -u datavest-api -u datavest-celery -u datavest-beat -u datavest-scheduler -n 200 --no-pager
curl -fsS http://127.0.0.1:5100/api/health/ready
curl -fsS https://datavest.vn/api/health/ready
readlink -f /opt/datavest/current
readlink -f /opt/datavest/previous
```

Each unit has a memory ceiling: API 700 MB, Celery 500 MB and scheduler 350 MB.
PostgreSQL/Redis are shared processes, but DataVest has a dedicated database,
role, cache namespace and Celery Redis DB numbers 8/9.

## Rollback and recovery

If activation fails after switching releases, the deploy script returns the
`current` symlink to the prior release and restarts DataVest units. Database
migrations must remain additive. Seven compressed database backups are retained
under `/opt/datavest/backups/`, and three release directories are retained.

Before any manual database restore, stop DataVest writes and confirm the exact
backup and intended data loss. Deployment never alters Tử Vi/Radar BDS databases,
units or Nginx files.
