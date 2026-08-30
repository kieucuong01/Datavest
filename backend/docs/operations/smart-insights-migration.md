# Smart Insights legacy production migration

The importer moves source-backed evidence from the old DataVest PostgreSQL
schema into the QuantDinger-first schema. It is intentionally read-only on
the source and runs as a dry-run unless `--apply` is supplied.

It imports:

- verified `data_providers` into `data_sources`;
- `provider_runs` into `collector_runs`;
- validated metric evidence from `metric_observations`;
- validated economic events as explicit `macro.economic_event` evidence;
- a new immutable destination snapshot for the imported evidence window.

It does not import `app_users`, password hashes, organizations, sessions,
broker credentials, portfolios, AI prompts, or provider secrets. Old rows are
never updated or deleted.

## Prerequisites

Set a read-only source DSN and the local destination DSN without printing
either value:

```powershell
$env:SOURCE_DATABASE_URL = '<old-production-read-only-dsn>'
$env:DATABASE_URL = '<local-datavest-dsn>'
```

The source must be a PostgreSQL database containing the old DataVest tables.
The destination must have completed the QuantDinger migrations, including
`20260825_smart_insights_production_sources.sql`.

## Dry-run

```powershell
& .\backend_api_python\.venv\Scripts\python.exe `
  -m app.tools.migrate_smart_insights `
  --report .\reports\smart-insights-migration-dry-run.json
```

Review `sourcesKnown`, `observationsSkipped`, `skippedReasons`, and checksum
dedupe counts. A successful dry-run does not write destination rows.

## Apply to local/staging

Take a destination backup first, then run the explicit apply command:

```powershell
& .\backend_api_python\.venv\Scripts\python.exe `
  -m app.tools.migrate_smart_insights `
  --apply `
  --report .\reports\smart-insights-migration-apply.json
```

The importer refuses an apply when source and destination resolve to the same
database. Re-running the same command is safe: observation checksums and
snapshot evidence checksums dedupe the import.

## Production gate

Do not place a production DSN in the repository or command history. Use a
temporary environment injection or a secure dump/restore workflow. The
operator must verify the dry-run report, restore backup, destination row
counts, Smart Insights Data Health, and the immutable snapshot before any
production cutover.
