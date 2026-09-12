#!/usr/bin/env bash
set -euo pipefail
[[ "$(id -u)" == 0 ]] || { echo 'Run calendar installer as root' >&2; exit 1; }
# Optional source directory supports both repository and deployed-release layouts.
calendar_source="${1:-/opt/datavest/current/backend/calendar_worker}"
test -f "$calendar_source/datavest-calendar.service"
calendar_uid="$(id -u datavest-deploy)"
calendar_user_systemctl() {
  runuser -u datavest-deploy -- env XDG_RUNTIME_DIR="/run/user/$calendar_uid" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$calendar_uid/bus" systemctl --user "$@"
}
# Remove the former user/system timer before enabling the long-running scheduler.
calendar_user_systemctl disable --now datavest-calendar.timer >/dev/null 2>&1 || true
calendar_user_systemctl stop datavest-calendar.service >/dev/null 2>&1 || true
systemctl disable --now datavest-calendar.timer >/dev/null 2>&1 || true
systemctl stop datavest-calendar.service >/dev/null 2>&1 || true
install -m 0644 -o root -g root "$calendar_source/datavest-calendar.service" /etc/systemd/system/datavest-calendar.service
systemctl daemon-reload
systemctl enable --now datavest-calendar.service
