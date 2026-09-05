#!/usr/bin/env bash
set -Eeuo pipefail
umask 0027

[[ ${EUID} -eq 0 ]] || { echo 'bootstrap_status=root_required' >&2; exit 1; }
[[ $# -eq 1 ]] || { echo 'usage: bootstrap.sh DEPLOY_PUBLIC_KEY' >&2; exit 2; }
public_key_file="$(realpath -- "$1")"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
grep -Eq '^ssh-ed25519 [A-Za-z0-9+/=]+' "$public_key_file" || { echo 'bootstrap_status=invalid_public_key' >&2; exit 2; }

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  python3 python3-venv python3-dev build-essential libpq-dev \
  nginx postgresql-client redis-tools certbot python3-certbot-nginx

id datavest-deploy >/dev/null 2>&1 || useradd --create-home --shell /bin/bash datavest-deploy
loginctl enable-linger datavest-deploy
install -d -m 0755 -o datavest-deploy -g datavest-deploy /opt/datavest
install -d -m 0755 -o datavest-deploy -g datavest-deploy /opt/datavest/releases
install -d -m 0750 -o datavest-deploy -g datavest-deploy /opt/datavest/shared /opt/datavest/backups
install -d -m 0770 -o datavest-deploy -g datavest-deploy /opt/datavest/incoming
install -d -m 0750 -o datavest-deploy -g datavest-deploy \
  /opt/datavest/shared/data /opt/datavest/shared/logs /opt/datavest/shared/prometheus
install -d -m 0700 -o datavest-deploy -g datavest-deploy /home/datavest-deploy/.ssh
install -m 0600 -o datavest-deploy -g datavest-deploy "$public_key_file" /home/datavest-deploy/.ssh/authorized_keys

install -m 0755 -o datavest-deploy -g datavest-deploy "$script_dir/deploy.sh" /opt/datavest/shared/deploy.sh
install -m 0755 -o root -g root "$script_dir/env_exec.py" /usr/local/bin/datavest-env-exec
install -m 0755 -o root -g root "$script_dir/configure_env.py" /usr/local/bin/configure-datavest-env
/usr/local/bin/configure-datavest-env /dev/null /opt/datavest/shared/.env
chown datavest-deploy:datavest-deploy /opt/datavest/shared/.env
chmod 0600 /opt/datavest/shared/.env

postgres_password="$(sed -n 's/^POSTGRES_PASSWORD=//p' /opt/datavest/shared/.env | tail -1)"
[[ -n "$postgres_password" ]] || { echo 'bootstrap_status=database_password_missing' >&2; exit 1; }
runuser -u postgres -- psql --set=ON_ERROR_STOP=1 --set=role_password="$postgres_password" postgres <<'SQL'
SELECT format('CREATE ROLE datavest LOGIN PASSWORD %L', :'role_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'datavest') \gexec
SELECT format('ALTER ROLE datavest WITH LOGIN PASSWORD %L', :'role_password') \gexec
SELECT 'CREATE DATABASE datavest OWNER datavest'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'datavest') \gexec
REVOKE ALL ON DATABASE datavest FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE datavest TO datavest;
SQL
unset postgres_password

unit_dir=/home/datavest-deploy/.config/systemd/user
install -d -m 0755 -o datavest-deploy -g datavest-deploy "$unit_dir"
install -m 0644 -o datavest-deploy -g datavest-deploy "$script_dir/datavest-api.service" "$unit_dir/datavest-api.service"
install -m 0644 -o datavest-deploy -g datavest-deploy "$script_dir/datavest-celery.service" "$unit_dir/datavest-celery.service"
install -m 0644 -o datavest-deploy -g datavest-deploy "$script_dir/datavest-beat.service" "$unit_dir/datavest-beat.service"
install -m 0644 -o datavest-deploy -g datavest-deploy "$script_dir/datavest-scheduler.service" "$unit_dir/datavest-scheduler.service"
install -m 0644 -o datavest-deploy -g datavest-deploy "$script_dir/datavest-crypto-insights-browser.service" "$unit_dir/datavest-crypto-insights-browser.service"
install -m 0644 -o datavest-deploy -g datavest-deploy "$script_dir/datavest-trading-agents.service" "$unit_dir/datavest-trading-agents.service"

mkdir -p /var/www/datavest-acme
cat > /etc/nginx/sites-available/datavest.conf <<'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name datavest.vn www.datavest.vn;
    location /.well-known/acme-challenge/ { root /var/www/datavest-acme; }
    location / { return 503; }
}
EOF
ln -sfn /etc/nginx/sites-available/datavest.conf /etc/nginx/sites-enabled/datavest.conf
nginx -t
systemctl reload nginx
if [[ ! -f /etc/letsencrypt/live/datavest.vn/fullchain.pem ]]; then
  certbot certonly --webroot -w /var/www/datavest-acme \
    -d datavest.vn -d www.datavest.vn \
    --non-interactive --agree-tos --email kieucuong01@gmail.com
fi
install -m 0644 -o root -g root "$script_dir/nginx.conf" /etc/nginx/sites-available/datavest.conf
nginx -t
systemctl reload nginx

uid="$(id -u datavest-deploy)"
runuser -u datavest-deploy -- env \
  XDG_RUNTIME_DIR="/run/user/$uid" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
  systemctl --user daemon-reload

echo 'bootstrap_status=success'
