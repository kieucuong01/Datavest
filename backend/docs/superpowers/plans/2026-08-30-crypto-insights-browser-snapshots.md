# Crypto Insights Browser Snapshots Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace fragile live Smart Insights source parsing with validated Browser Use snapshots, run a full local backfill, and schedule daily and CoinShares-specific refreshes.

**Architecture:** A dedicated Browser Use worker writes atomic per-source JSON snapshots to `backend_data`. Snapshot-backed collectors normalize only those local files into the existing `observations` and evidence pipeline. The worker captures the daily sources from 08:15 to 08:50 and CoinShares at 18:00 on Monday and Tuesday; Celery Beat queues source-specific imports after those capture windows. The legacy six-hour bulk refresh excludes these seven source codes.

**Tech Stack:** Python 3.12, browser-use 0.13.8, Chromium, Celery Beat, Redis, Postgres, Docker Compose, pytest.

**Spec:** `docs/superpowers/specs/2026-08-30-crypto-insights-browser-snapshots-design.md`

## Global Constraints

- Browser automation is local and serial; no dashboard request may contact an upstream source.
- Snapshots publish atomically, preserve the last valid version on failure, and include source URL, fetched time, schema version, and coverage.
- Ongoing capture is daily for Fear & Greed, Farside BTC/ETH/SOL, Altcoin Season, and CBBI; CoinShares runs Monday and Tuesday only.
- Backfill imports all public history the source exposes, except Altcoin Season which is current-only.
- Celery timezone is explicitly `Asia/Ho_Chi_Minh`; its scheduled imports run after the worker capture window.
- Tests precede production code and must demonstrate the expected failing state.

---

### Task 1: Define and test the versioned crypto snapshot contract

**Files:**
- Create: `backend_api_python/app/services/smart_insights/browser_snapshots.py`
- Create: `backend_api_python/tests/test_smart_insights_browser_snapshots.py`

**Interfaces:**
- Produces `write_snapshot(source_code: str, payload: Mapping[str, object], *, root: Path) -> Path`.
- Produces `load_snapshot(source_code: str, *, root: Path, now: datetime) -> Mapping[str, object]`.
- Produces `SnapshotUnavailable(code: str)` for invalid, stale, missing, or source-mismatched payloads.
- Snapshot payload shape is `{source, source_url, schema_version, fetched_at, coverage, records}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_write_snapshot_replaces_a_source_file_only_after_validation(tmp_path):
    write_snapshot("alternative-fng", valid_fng_payload(), root=tmp_path)
    with pytest.raises(SnapshotUnavailable, match="REQUIRED_RECORDS"):
        write_snapshot("alternative-fng", {**valid_fng_payload(), "records": []}, root=tmp_path)
    assert load_snapshot("alternative-fng", root=tmp_path, now=NOW)["records"][0]["value"] == "67"

def test_load_snapshot_rejects_wrong_source_and_stale_payload(tmp_path):
    write_json(tmp_path / "alternative-fng.json", {**valid_fng_payload(), "source": "cbbi-public"})
    with pytest.raises(SnapshotUnavailable, match="SOURCE_IDENTITY_MISMATCH"):
        load_snapshot("alternative-fng", root=tmp_path, now=NOW)
```

- [ ] **Step 2: Run the tests to verify RED**

Run: `pytest backend_api_python/tests/test_smart_insights_browser_snapshots.py -q`

Expected: import failure because `browser_snapshots` is not implemented.

- [ ] **Step 3: Implement the minimal contract**

```python
def write_snapshot(source_code: str, payload: Mapping[str, object], *, root: Path) -> Path:
    validate_payload(source_code, payload)
    target = root / f"{source_code}.json"
    # Write JSON to a temporary sibling then Path.replace(target).
    return target

def load_snapshot(source_code: str, *, root: Path, now: datetime) -> Mapping[str, object]:
    payload = json.loads((root / f"{source_code}.json").read_text(encoding="utf-8"))
    validate_payload(source_code, payload, now=now)
    return payload
```

- [ ] **Step 4: Run the contract tests to verify GREEN**

Run: `pytest backend_api_python/tests/test_smart_insights_browser_snapshots.py -q`

Expected: all tests pass.

- [ ] **Step 5: Inspect only the focused diff**

Run: `git -c safe.directory="C:/Users/ASUS/Documents/Claude/Projects/Financial Platform/Datavest" diff --check -- backend_api_python/app/services/smart_insights/browser_snapshots.py backend_api_python/tests/test_smart_insights_browser_snapshots.py`

Expected: no whitespace errors. Do not stage, commit, push, or touch unrelated Economic Calendar changes.

### Task 2: Add a Browser Use worker for capture, validation, and backfill

**Files:**
- Create: `backend_api_python/crypto_insights_worker/__init__.py`
- Create: `backend_api_python/crypto_insights_worker/browser_snapshots.py`
- Create: `backend_api_python/crypto_insights_worker/requirements.txt`
- Create: `backend_api_python/crypto_insights_worker/Dockerfile`
- Modify: `docker-compose.calendar.yml`
- Test: `backend_api_python/tests/test_crypto_insights_browser_worker.py`

**Interfaces:**
- Produces `collect_source(source_code: str, page: Any, *, as_of: datetime) -> dict`.
- Produces `backfill(source_codes: Sequence[str]) -> Mapping[str, object]`.
- CLI accepts `--once`, `--backfill`, and `--sources alternative-fng,farside-btc-etf`.
- Worker writes under `/app/data/crypto-insights/<source-code>.json` and never writes to Postgres.

- [ ] **Step 1: Write failing extraction and backfill tests**

```python
def test_worker_backfill_publishes_all_available_farside_rows(tmp_path, fake_browser):
    result = backfill(("farside-btc-etf",), browser=fake_browser, root=tmp_path, as_of=NOW)
    snapshot = load_snapshot("farside-btc-etf", root=tmp_path, now=NOW)
    assert result["farside-btc-etf"]["status"] == "ok"
    assert snapshot["coverage"] == {"oldestEffectiveAt": "2024-01-11T00:00:00+00:00", "recordCount": 2}

def test_worker_leaves_prior_snapshot_when_a_source_layout_drifts(tmp_path, fake_browser):
    write_snapshot("blockchaincenter-altcoin-season", valid_altcoin_payload(), root=tmp_path)
    with pytest.raises(SnapshotUnavailable, match="SCHEMA_DRIFT"):
        collect_and_publish("blockchaincenter-altcoin-season", browser=fake_browser, root=tmp_path, as_of=NOW)
    assert load_snapshot("blockchaincenter-altcoin-season", root=tmp_path, now=NOW)["records"][0]["horizon"] == "season_90d"
```

- [ ] **Step 2: Run the tests to verify RED**

Run: `pytest backend_api_python/tests/test_crypto_insights_browser_worker.py -q`

Expected: import failure because the worker package does not exist.

- [ ] **Step 3: Implement source adapters with Browser Use**

```python
async def collect_source(source_code: str, page: Any, *, as_of: datetime) -> dict[str, object]:
    await page.goto(SOURCE_URLS[source_code])
    await asyncio.sleep(PAGE_WAIT_SECONDS)
    records = await EXTRACTORS[source_code](page, as_of=as_of)
    return build_payload(source_code, records=records, fetched_at=as_of)
```

Implement the seven adapters: Alternative Fear & Greed history, Farside BTC/ETH/SOL tables, BlockchainCenter three horizons, CBBI history/components, and CoinShares public archive reports. The Browser Use worker must use visible DOM/page data, one session, serial navigation, bounded retries, and a small delay between sources.

- [ ] **Step 4: Run worker tests to verify GREEN**

Run: `pytest backend_api_python/tests/test_crypto_insights_browser_worker.py -q`

Expected: all extraction, coverage, and prior-snapshot preservation tests pass.

- [ ] **Step 5: Add the isolated Docker service**

```yaml
crypto-insights-browser:
  build:
    context: ./backend_api_python
    dockerfile: crypto_insights_worker/Dockerfile
  environment:
    CRYPTO_INSIGHTS_SNAPSHOT_ROOT: /app/data/crypto-insights
    TZ: Asia/Ho_Chi_Minh
  volumes:
    - backend_data:/app/data
```

Reuse the browser-use and Chromium image pattern from `calendar_worker/Dockerfile`; do not add Browser Use to the backend API image.

- [ ] **Step 6: Inspect only worker, compose, and test files**

Run: `git -c safe.directory="C:/Users/ASUS/Documents/Claude/Projects/Financial Platform/Datavest" diff --check -- backend_api_python/crypto_insights_worker docker-compose.calendar.yml backend_api_python/tests/test_crypto_insights_browser_worker.py`

Expected: no whitespace errors. Do not stage or commit the user's existing changes.

### Task 3: Normalize local snapshots through the existing observations pipeline

**Files:**
- Create: `backend_api_python/app/services/smart_insights/snapshot_collectors.py`
- Modify: `backend_api_python/app/services/smart_insights/collectors.py`
- Modify: `backend_api_python/tests/test_smart_insights_public_collectors.py`
- Test: `backend_api_python/tests/test_smart_insights_snapshot_collectors.py`

**Interfaces:**
- Produces `SnapshotObservationCollector(source_code: str, *, root: Path, clock: Callable[[], datetime])`.
- `collect()` returns `tuple[Observation, ...]` with the current source code, metric names, effective times, and `LIVE` data class.
- `default_collector_registry()` maps these seven codes to snapshot-backed collectors and keeps all other source mappings unchanged.

- [ ] **Step 1: Write failing normalization tests**

```python
def test_snapshot_collector_normalizes_farside_and_coinshares_records(tmp_path):
    write_snapshot("farside-btc-etf", valid_farside_payload(), root=tmp_path)
    write_snapshot("coinshares-weekly", valid_coinshares_payload(), root=tmp_path)
    btc = SnapshotObservationCollector("farside-btc-etf", root=tmp_path, clock=lambda: NOW).collect()
    flows = SnapshotObservationCollector("coinshares-weekly", root=tmp_path, clock=lambda: NOW).collect()
    assert btc[0].value["metric"] == "crypto.etf.net_flow_usd"
    assert {row.value["metric"] for row in flows} == {"crypto.coinshares.net_flow_usd", "crypto.coinshares.aum_usd"}

def test_registry_never_falls_back_to_a_live_http_parser_for_snapshot_sources(tmp_path, monkeypatch):
    monkeypatch.setenv("CRYPTO_INSIGHTS_SNAPSHOT_ROOT", str(tmp_path))
    registry = default_collector_registry()
    assert registry["cbbi-public"].__module__.endswith("snapshot_collectors")
```

- [ ] **Step 2: Run the tests to verify RED**

Run: `pytest backend_api_python/tests/test_smart_insights_snapshot_collectors.py -q`

Expected: import failure because `SnapshotObservationCollector` is not implemented.

- [ ] **Step 3: Implement source-to-observation mappings**

```python
class SnapshotObservationCollector:
    def collect(self) -> tuple[Observation, ...]:
        payload = load_snapshot(self.source_code, root=self.root, now=self.clock())
        return tuple(self._observation(record, payload) for record in payload["records"])
```

Keep exact live metric keys already consumed by the app: `crypto.fear_greed.index`, `crypto.etf.net_flow_usd`, `crypto.coinshares.net_flow_usd`, `crypto.coinshares.aum_usd`, `crypto.cycle.altcoin_season.*`, and `crypto.cycle.cbbi.*`. Invalid local snapshots raise `CollectorUnavailable` and therefore preserve old DB observations.

- [ ] **Step 4: Run focused collector tests to verify GREEN**

Run: `pytest backend_api_python/tests/test_smart_insights_snapshot_collectors.py backend_api_python/tests/test_smart_insights_public_collectors.py -q`

Expected: all tests pass and no seven-source registry path uses direct HTTP or nodriver.

- [ ] **Step 5: Inspect only snapshot collector changes and tests**

Run: `git -c safe.directory="C:/Users/ASUS/Documents/Claude/Projects/Financial Platform/Datavest" diff --check -- backend_api_python/app/services/smart_insights/snapshot_collectors.py backend_api_python/app/services/smart_insights/collectors.py backend_api_python/tests/test_smart_insights_snapshot_collectors.py`

Expected: no whitespace errors and no staging or commit.

### Task 4: Route source-specific scheduled imports and prevent overlap

**Files:**
- Modify: `backend_api_python/app/tasks/smart_insights.py`
- Modify: `backend_api_python/app/celery_app.py`
- Modify: `docker-compose.datavest.yml`
- Modify: `backend_api_python/tests/test_celery_boundaries.py`
- Create: `backend_api_python/tests/test_smart_insights_schedule.py`

**Interfaces:**
- Produces `enqueue_smart_insights_refresh_for_sources(source_codes: Sequence[str]) -> dict`.
- Adds Celery Beat keys `crypto-insights-daily-import` and `crypto-insights-coinshares-import`.
- The default bulk refresh source list excludes the seven snapshot-backed source codes.

- [ ] **Step 1: Write failing schedule tests**

```python
def test_beat_queues_daily_snapshot_sources_after_capture_window():
    daily = celery_app.conf.beat_schedule["crypto-insights-daily-import"]
    assert daily["task"] == "datavest.tasks.enqueue_smart_insights_refresh_for_sources"
    assert daily["args"] == (("alternative-fng", "farside-btc-etf", "farside-eth-etf", "farside-sol-etf", "blockchaincenter-altcoin-season", "cbbi-public"),)

def test_coinshares_schedule_has_monday_and_tuesday_entries_only():
    entries = [value for key, value in celery_app.conf.beat_schedule.items() if key.startswith("crypto-insights-coinshares-import")]
    assert {entry["schedule"].day_of_week for entry in entries} == {"mon", "tue"}
```

- [ ] **Step 2: Run tests to verify RED**

Run: `pytest backend_api_python/tests/test_celery_boundaries.py backend_api_python/tests/test_smart_insights_schedule.py -q`

Expected: missing task and Beat entries.

- [ ] **Step 3: Implement granular queueing and schedule configuration**

```python
@celery_app.task(name="datavest.tasks.enqueue_smart_insights_refresh_for_sources")
def enqueue_smart_insights_refresh_for_sources(source_codes: tuple[str, ...]) -> dict:
    run_id = SmartInsightsRepository().create_refresh_request(
        requested_by_user_id=None, market="crypto", source_codes=source_codes
    )
    run_smart_insights_refresh.delay(run_id)
    return {"queued": True, "runId": run_id, "sourceCount": len(source_codes)}
```

Use Celery `crontab` entries at 09:15 for the six daily source imports and 18:15 Monday/Tuesday for CoinShares, after their Browser Use snapshots. Set `TZ=Asia/Ho_Chi_Minh` on backend, scheduler, worker, and beat services. Add a Redis lock using `SET key token NX EX 3600` around source-specific imports; release it only when the token still matches so duplicate queue delivery cannot overlap a run.

- [ ] **Step 4: Run schedule tests to verify GREEN**

Run: `pytest backend_api_python/tests/test_celery_boundaries.py backend_api_python/tests/test_smart_insights_schedule.py -q`

Expected: all schedule routing assertions pass.

- [ ] **Step 5: Inspect only source scheduling, compose environment, and test files**

Run: `git -c safe.directory="C:/Users/ASUS/Documents/Claude/Projects/Financial Platform/Datavest" diff --check -- backend_api_python/app/tasks/smart_insights.py backend_api_python/app/celery_app.py docker-compose.datavest.yml backend_api_python/tests/test_celery_boundaries.py backend_api_python/tests/test_smart_insights_schedule.py`

Expected: no whitespace errors and no staging or commit.

### Task 5: Build locally, run the full Browser Use backfill, and verify persisted data

**Files:**
- No additional production files.
- Verification output: `backend_api_python/data/crypto-insights/*.json` in the `backend_data` volume and Postgres `observations`/`collector_runs` rows.

**Interfaces:**
- Backfill command: `python -m crypto_insights_worker.browser_snapshots --backfill`.
- Verification command is source-specific and reads only the local Docker database and API health endpoint.

- [ ] **Step 1: Build the worker and backend images**

Run: `docker compose -f docker-compose.yml -f docker-compose.datavest.yml -f docker-compose.calendar.yml build backend celery-worker celery-beat crypto-insights-browser`

Expected: successful builds; the backend image does not acquire Chromium/browser-use dependencies.

- [ ] **Step 2: Start the worker once for the initial backfill**

Run: `docker compose -f docker-compose.yml -f docker-compose.datavest.yml -f docker-compose.calendar.yml run --rm crypto-insights-browser python -m crypto_insights_worker.browser_snapshots --backfill`

Expected: one real coverage report per source and one atomic local snapshot per successful source. Failures must be named by source and retain prior snapshots.

- [ ] **Step 3: Import the seven snapshots through the normal Celery task**

Run: `docker exec datavest-celery-worker celery -A app.celery_app call datavest.tasks.enqueue_smart_insights_refresh_for_sources --args='[["alternative-fng","farside-btc-etf","farside-eth-etf","farside-sol-etf","coinshares-weekly","blockchaincenter-altcoin-season","cbbi-public"]]'`

Expected: the command returns a Celery task id; then poll `collector_runs` for the created seven-source run. Do not insert observations directly with SQL.

- [ ] **Step 4: Verify data and health with direct evidence**

Run a Postgres query joining `data_sources`, `observations`, and the most recent `collector_runs` for all seven codes. Confirm `last_observed_at`, positive row counts where the upstream exposed data, and no placeholder records. Then call `http://127.0.0.1:8888/api/health` and the Smart Insights data-health endpoint, if authenticated access is available.

- [ ] **Step 5: Run the complete relevant regression suite**

Run: `pytest backend_api_python/tests/test_smart_insights_browser_snapshots.py backend_api_python/tests/test_crypto_insights_browser_worker.py backend_api_python/tests/test_smart_insights_snapshot_collectors.py backend_api_python/tests/test_smart_insights_public_collectors.py backend_api_python/tests/test_celery_boundaries.py backend_api_python/tests/test_smart_insights_schedule.py -q`

Expected: exit code 0 with no failures.

- [ ] **Step 6: Inspect the diff and report exact source coverage**

Run: `git -c safe.directory=C:/Users/ASUS/Documents/Claude/Projects/Financial\ Platform/Datavest diff --check` followed by a selective status/diff of only this feature's paths. Do not commit, push, or deploy unless explicitly requested.
