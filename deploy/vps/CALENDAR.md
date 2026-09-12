# Economic calendar operations

`datavest-calendar.timer` runs at minute 00 and 30 in Asia/Ho_Chi_Minh
(up to 30 seconds jitter). The oneshot service exits after each refresh;
Chrome is not kept running. The whole job has a 240 second limit.

The job tries Investing rendered DOM first (90 second deadline), then the
existing free WallstreetCN/AkShare provider if Investing is unavailable.
It does not bypass HTTP 403 or access challenges. The fallback snapshot
and API explicitly identify the actual provider and fallback reason.
No previous value is substituted for a missing forecast. AkShare UTC+8
event times are converted to Vietnam time before import.

Crawl and import are one job, with separate atomic snapshots in
`/opt/datavest/shared/data/economic-calendar/`:

- `investing-browser.json`: Investing only; a fallback run cannot replace it.
- `wallstreetcn.json`: the optional fallback, selected explicitly in the UI.

The default API and UI always read Investing, even when its snapshot is stale.
`GET /api/global-market/calendar?source=akshare_wallstreetcn` reads only the
fallback. Old mixed-file releases are handled defensively: a fallback inside
the Investing file is accessible only through explicit fallback selection,
never labelled as Investing. Underspecified translations retain the original
event name rather than replacing it with an indistinguishable generic label.
If both providers fail, the last good snapshot is retained, and becomes
STALE after two hours. Fallback coverage is marked PARTIAL even when recent;
it is not guaranteed to contain the same country/event universe as Investing.

As datavest-deploy (user systemd environment configured):

```sh
systemctl --user list-timers datavest-calendar.timer
systemctl --user start datavest-calendar.service
journalctl --user -u datavest-calendar.service -n 80 --no-pager
```

The API caches for 60 seconds. Smart Insights expires its calendar cache
after five minutes and refreshes while visible. “Refresh” reloads the API
snapshot; it does not launch a browser or bypass the scheduler.

Verify a release by checking the timer, last service result, snapshot
`fetched_at`, `source`, and real `actual` / `forecast` coverage separately.
Future events, speeches and holidays may legitimately lack numeric fields.

Known VPS blocker (2026-09-12): user systemd confinement prevents Chrome's
SUID sandbox from starting; the alternative user-namespace sandbox is also
restricted by the host's AppArmor policy. Do not add `--no-sandbox`, disable
AppArmor globally, or claim Investing is restored from successful fallback
imports. A separate direct source probe returned HTTP 403. Both browser
startup and legitimate provider access require independent verification.
