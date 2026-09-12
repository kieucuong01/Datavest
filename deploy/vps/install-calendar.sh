#!/usr/bin/env bash
set -euo pipefail
[[ "$(id -u)" == 0 ]] || { echo 'Run calendar installer as root' >&2; exit 1; }
# Optional source directory supports both repository and deployed-release layouts.
calendar_source="${1:-/opt/datavest/current/backend/calendar_worker}"
test -f "$calendar_source/datavest-calendar.service"
test -f "$calendar_source/datavest-calendar.timer"
calendar_uid="$(id -u datavest-deploy)"
calendar_user_systemctl() {
  runuser -u datavest-deploy -- env XDG_RUNTIME_DIR="/run/user/$calendar_uid" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$calendar_uid/bus" systemctl --user "$@"
}
if calendar_user_systemctl cat datavest-calendar.timer >/dev/null 2>&1; then
  calendar_user_systemctl disable --now datavest-calendar.timer
  calendar_user_systemctl stop datavest-calendar.service
fi
install -m 0644 -o root -g root "$calendar_source/datavest-calendar.service" /etc/systemd/system/datavest-calendar.service
install -m 0644 -o root -g root "$calendar_source/datavest-calendar.timer" /etc/systemd/system/datavest-calendar.timer
systemctl daemon-reload
systemctl enable --now datavest-calendar.timer
systemctl start --no-block datavest-calendar.service
