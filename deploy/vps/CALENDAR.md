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

Crawl and import are one job: atomic replacement of
`/opt/datavest/shared/data/economic-calendar/investing-browser.json`.
The legacy filename remains for API compatibility, NOT source identity.
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
