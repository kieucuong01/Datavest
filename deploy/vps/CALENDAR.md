# Economic calendar operations

`datavest-calendar.timer` runs at minute 00 and 30 in Asia/Ho_Chi_Minh
(up to 30 seconds jitter). The oneshot service exits after each refresh;
Chrome is not kept running. The whole job has a 240 second limit.

The default job refreshes the free WallstreetCN/AkShare provider directly.
Investing rendered-DOM refresh is opt-in with
`ECONOMIC_CALENDAR_PROVIDER=investing_browser`; when enabled, it has a
90-second deadline and falls back to WallstreetCN/AkShare on failure. It does
not bypass HTTP 403 or access challenges. The snapshot and API explicitly
identify the actual provider and fallback reason.
No previous value is substituted for a missing forecast. AkShare UTC+8
event times are converted to Vietnam time before import.
AkShare Chinese event labels are enriched with validated `name_vi` and
`name_en` fields during this same scheduled job. Common labels use a
deterministic dictionary; uncached labels use the server-side DeepSeek key
when configured and are stored in `event-name-translations.json`. The browser
never receives or calls the DeepSeek credential.
Each refresh translates at most 10 uncached labels, so the 30-minute timer
remains bounded; later refreshes continue from the cache.

Crawl and import are one job, with separate atomic snapshots in
`/opt/datavest/shared/data/economic-calendar/`:

- `investing-browser.json`: Investing only; a fallback run cannot replace it.
- `wallstreetcn.json`: the optional fallback, selected explicitly in the UI.
- `event-name-translations.json`: validated event-label translations shared by
  future refreshes.

The default API and UI read the fresh free WallstreetCN/AkShare snapshot.
Investing remains available only when explicitly selected/configured and is
currently marked paused in the UI while the VPS cannot access it.
`GET /api/global-market/calendar?source=akshare_wallstreetcn` reads only the
fallback. Old mixed-file releases are handled defensively: a fallback inside
the Investing file is accessible only through explicit fallback selection,
never labelled as Investing. Underspecified translations retain the original
event name rather than replacing it with an indistinguishable generic label.
If both providers fail, the last good snapshot is retained, and becomes
STALE after two hours. Fallback coverage is marked PARTIAL even when recent;
it is not guaranteed to contain the same country/event universe as Investing.

The calendar uses the system manager, running as `datavest-deploy`, not root.
One-time installation/migration as root (also called by bootstrap):

```sh
bash /path/to/repo/deploy/vps/install-calendar.sh
```

This stops the old user timer before enabling the system timer. CI deployments
verify that the system timer is active; they do not install user calendar units
or need new sudo permissions. Its executable follows `/opt/datavest/current`.
After editing unit files, re-run the installer as root with the new release's
`backend/calendar_worker` directory. Inspect operations as root:

```sh
systemctl list-timers datavest-calendar.timer
systemctl start datavest-calendar.service
journalctl -u datavest-calendar.service -n 80 --no-pager
```

The API caches for 60 seconds. Smart Insights expires its calendar cache
after five minutes and refreshes while visible. “Refresh” reloads the API
snapshot; it does not launch a browser or bypass the scheduler.

Verify a release by checking the timer, last service result, snapshot
`fetched_at`, `source`, and real `actual` / `forecast` coverage separately.
Future events, speeches and holidays may legitimately lack numeric fields.

VPS diagnosis (2026-09-12): user systemd confinement prevented Chrome's
SUID sandbox from starting. The system-manager probe with non-root User and
NoNewPrivileges=false launched Chrome successfully, while retaining
ProtectSystem=strict, ProtectHome and PrivateTmp. This narrowly permits the
root-owned Chrome SUID helper; it does not run the application as root.
The host AppArmor policy remains unchanged. Do not add `--no-sandbox`, disable
AppArmor globally, or claim Investing is restored from successful fallback
imports. A separate direct source probe returned HTTP 403. Both browser
startup and legitimate provider access require independent verification.
