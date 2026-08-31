#!/usr/bin/env bash
set -Eeuo pipefail
umask 0027

readonly root=/opt/datavest
readonly releases="$root/releases"
readonly incoming="$root/incoming"
readonly shared="$root/shared"
readonly backups="$root/backups"
readonly env_file="$shared/.env"
readonly runtime_uid="$(id -u)"
export XDG_RUNTIME_DIR="/run/user/$runtime_uid"
export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
user_systemctl() { systemctl --user "$@"; }

[[ "$(id -un)" == datavest-deploy ]] || { echo 'deploy_status=deploy_user_required' >&2; exit 1; }
[[ $# -eq 2 ]] || { echo 'usage: deploy-datavest RELEASE_ARCHIVE GIT_SHA' >&2; exit 2; }
archive="$(realpath -- "$1")"
sha="$2"
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || { echo 'deploy_status=invalid_sha' >&2; exit 2; }
[[ "$(dirname -- "$archive")" == "$incoming" ]] || { echo 'deploy_status=archive_outside_incoming' >&2; exit 2; }
[[ "$(basename -- "$archive")" == "datavest-release-${sha:0:12}.tar.gz" ]] || { echo 'deploy_status=archive_name_mismatch' >&2; exit 2; }
[[ -f "$archive.sha256" && ! -L "$archive" && ! -L "$archive.sha256" ]] || { echo 'deploy_status=archive_invalid' >&2; exit 2; }

exec 9>"$shared/deploy.lock"
flock -n 9 || { echo 'deploy_status=already_running' >&2; exit 1; }
cd "$incoming"
sha256sum --check "$(basename -- "$archive").sha256" >/dev/null

release="$releases/$sha"
staging="$releases/.staging-$sha"
old_release=""
[[ -L "$root/current" ]] && old_release="$(readlink -f "$root/current")"
if [[ ! -f "$release/.ready" ]]; then
rm -rf -- "$release"
rm -rf -- "$staging"
install -d -m 0750 "$staging"

python3 - "$archive" "$staging" <<'PY'
import sys, tarfile
from pathlib import Path
archive, target = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
with tarfile.open(archive, "r:gz") as bundle:
    for member in bundle.getmembers():
        resolved = (target / member.name).resolve()
        if target not in resolved.parents and resolved != target:
            raise SystemExit("unsafe archive path")
        if member.issym() or member.islnk():
            raise SystemExit("archive links are not allowed")
    bundle.extractall(target, filter="data")
PY
[[ -f "$staging/backend/requirements.lock" && -f "$staging/frontend/dist/index.html" ]] || {
  echo 'deploy_status=release_layout_invalid' >&2
  exit 2
}
rm -rf -- "$staging/backend/data" "$staging/backend/logs"
ln -s /opt/datavest/shared/data "$staging/backend/data"
ln -s /opt/datavest/shared/logs "$staging/backend/logs"
mv -- "$staging" "$release"

python3 -m venv "$release/.venv"
"$release/.venv/bin/python" -m pip install --disable-pip-version-check --upgrade 'pip>=26.1.2,<27'
"$release/.venv/bin/pip" install --disable-pip-version-check --prefer-binary -r "$release/backend/requirements.lock"

install -d -m 0700 "$backups"
backup="$backups/datavest-$(date -u +%Y%m%dT%H%M%SZ)-${sha:0:12}.sql.gz"
/usr/local/bin/datavest-env-exec --cwd "$release/backend" "$env_file" \
  /usr/bin/pg_dump -h 127.0.0.1 -U datavest -d datavest --no-owner --no-privileges | gzip -9 > "$backup"
chmod 600 "$backup"

/usr/local/bin/datavest-env-exec --cwd "$release/backend" "$env_file" \
  /usr/bin/env SKIP_AUTO_MIGRATE=false "$release/.venv/bin/python" -m app.commands.migrate

touch "$release/.ready"
fi

# Nginx runs outside the deploy user's group. Expose only the immutable
# frontend bundle while keeping backend/runtime files private.
chmod 0755 "$release"
find "$release/frontend" -type d -exec chmod 0755 {} +
find "$release/frontend" -type f -exec chmod 0644 {} +

ln -sfn "$release" "$root/current.new"
mv -Tf "$root/current.new" "$root/current"
if [[ -n "$old_release" && "$old_release" != "$release" ]]; then
  ln -sfn "$old_release" "$root/previous.new"
  mv -Tf "$root/previous.new" "$root/previous"
fi

rollback() {
  status=$?
  if [[ -n "$old_release" && -d "$old_release" ]]; then
    ln -sfn "$old_release" "$root/current.new"
    mv -Tf "$root/current.new" "$root/current"
    user_systemctl restart datavest-api datavest-celery datavest-scheduler || true
  fi
  echo 'deploy_status=failed' >&2
  exit "$status"
}
trap rollback ERR

user_systemctl daemon-reload
user_systemctl enable datavest-api datavest-celery datavest-scheduler >/dev/null
user_systemctl restart datavest-api datavest-celery datavest-scheduler

for _ in {1..36}; do
  if curl -fsS --max-time 5 http://127.0.0.1:5100/api/health/ready >/dev/null && \
     curl -fsS --max-time 5 http://127.0.0.1/health -H 'Host: datavest.vn' >/dev/null; then
    break
  fi
  sleep 5
done
curl -fsS --max-time 10 http://127.0.0.1:5100/api/health/ready >/dev/null
curl -fsS --max-time 10 http://127.0.0.1/health -H 'Host: datavest.vn' >/dev/null
curl -kfsS --max-time 10 https://127.0.0.1/ -H 'Host: datavest.vn' >/dev/null
user_systemctl --no-pager --full status datavest-api datavest-celery datavest-scheduler | sed -n '1,45p'

trap - ERR
printf '%s\n' "$sha" > "$shared/current-release"
rm -f -- "$archive" "$archive.sha256"
find "$backups" -type f -name 'datavest-*.sql.gz' -printf '%T@ %p\n' | sort -nr | tail -n +8 | cut -d' ' -f2- | xargs -r rm -f --
find "$releases" -mindepth 1 -maxdepth 1 -type d -name '[0-9a-f]*' -printf '%T@ %p\n' | sort -nr | tail -n +4 | cut -d' ' -f2- | xargs -r rm -rf --
echo 'deploy_status=success'
echo "release=$sha"
