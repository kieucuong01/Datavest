"""Refresh Investing's rendered economic calendar through Browser Use.

This worker uses visible browser DOM and button clicks only. It deliberately
does not call Investing JSON/XHR endpoints. A successful refresh must include
Yesterday, Today, This Week, and Next Week before it replaces the snapshot.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

DEFAULT_SOURCE_URL = "https://vn.investing.com/economic-calendar/"
REQUIRED_CALENDAR_RANGES = ("Hôm qua", "Hôm nay", "Tuần này", "Tuần tới")


def _env_bool(name: str, default: bool = False) -> bool:
    return str(os.getenv(name, str(default))).strip().lower() in {"1", "true", "yes", "on"}


def _decode_browser_value(value: Any) -> Any:
    """Browser Use v0.13 returns primitive/object evaluation results as text."""
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def write_snapshot(payload: Dict[str, Any]) -> Path:
    """Publish JSON atomically without importing the Flask application package."""
    target = Path(os.getenv("INVESTING_CALENDAR_SNAPSHOT_PATH", "data/economic-calendar/investing-browser.json")).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        Path(temporary_name).replace(target)
    finally:
        temporary = Path(temporary_name)
        if temporary.exists():
            temporary.unlink(missing_ok=True)
    return target


def _local_browser_use_site_packages() -> None:
    configured = os.getenv("INVESTING_BROWSER_USE_SITE_PACKAGES", "").strip()
    local_app_data = os.getenv("LOCALAPPDATA", "").strip()
    candidates = [configured] if configured else []
    if local_app_data:
        candidates.extend([
            str(Path(local_app_data) / "DataVest" / "browser-use-0.13.8"),
            str(Path(local_app_data) / "QuantDinger" / "browser-use-0.13.8"),
        ])
    for candidate in candidates:
        if candidate and Path(candidate).is_dir() and candidate not in sys.path:
            sys.path.insert(0, candidate)


def create_browser_session():
    _local_browser_use_site_packages()
    from browser_use import BrowserSession

    executable_path = os.getenv("INVESTING_BROWSER_EXECUTABLE_PATH", "").strip()
    options = {
        "headless": _env_bool("INVESTING_BROWSER_HEADLESS"),
        "keep_alive": False,
        "allowed_domains": ["vn.investing.com", "www.investing.com", "investing.com"],
        "user_data_dir": str(Path(os.getenv("INVESTING_BROWSER_USER_DATA_DIR", "data/browser-profiles/investing")).expanduser().resolve()),
        "profile_directory": os.getenv("INVESTING_BROWSER_PROFILE_DIRECTORY", "Default"),
    }
    if executable_path:
        options["executable_path"] = executable_path
    return BrowserSession(**options)


async def select_calendar_range(page: Any, label: str) -> bool:
    """Click one exact, user-visible range button in the rendered calendar."""
    quoted_label = json.dumps(label, ensure_ascii=False)
    result = await page.evaluate(f"""
      () => {{
        const label = {quoted_label};
        const normalize = (value) => (value || '').trim().replace(/\\s+/gu, ' ').toLocaleLowerCase();
        const button = Array.from(document.querySelectorAll('button'))
          .find((item) => normalize(item.innerText) === normalize(label) && item.offsetParent !== null);
        if (!button) return false;
        button.click();
        return true;
      }}
    """)
    return bool(_decode_browser_value(result))


async def extract_visible_calendar_rows(page: Any, source_url: str) -> List[Dict[str, Any]]:
    """Read currently rendered table rows; never inspect network responses."""
    result = await page.evaluate(f"""
      () => {{
        const sourceUrl = {json.dumps(source_url, ensure_ascii=False)};
        const rows = [];
        let date = '';
        for (const row of Array.from(document.querySelectorAll('tr'))) {{
          const heading = row.querySelector(':scope > td[colspan]');
          if (heading) {{
            const match = (heading.innerText || '').match(/(\\d{{1,2}})\\s+tháng\\s+(\\d{{1,2}}),\\s*(\\d{{4}})/iu);
            if (match) date = `${{match[3]}}-${{match[2].padStart(2, '0')}}-${{match[1].padStart(2, '0')}}`;
            continue;
          }}
          const cells = Array.from(row.querySelectorAll(':scope > td'))
            .filter((cell) => getComputedStyle(cell).display !== 'none');
          const countryNode = row.querySelector('span[data-test^="flag-"]');
          if (!date || cells.length < 7 || !countryNode) continue;
          const name = (cells[2].innerText || '').trim();
          if (!name) continue;
          const stars = cells[3].querySelectorAll('svg[class*="opacity-60"]').length;
          rows.push({{
            date,
            time: (cells[0].innerText || '').trim(),
            country: (cells[1].innerText || countryNode.getAttribute('title') || '').trim(),
            name,
            importance: stars >= 3 ? 'high' : (stars <= 1 ? 'low' : 'medium'),
            actual: (cells[4].innerText || '').trim(),
            forecast: (cells[5].innerText || '').trim(),
            previous: (cells[6].innerText || '').trim(),
            source_url: sourceUrl,
          }});
        }}
        return rows;
      }}
    """)
    decoded = _decode_browser_value(result)
    return decoded if isinstance(decoded, list) else []


def deduplicate_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    unique: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        key = tuple(str(row.get(field, "")).strip().lower() for field in ("date", "time", "country", "name"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


async def refresh_investing_calendar() -> Dict[str, Any]:
    source_url = os.getenv("INVESTING_CALENDAR_URL", DEFAULT_SOURCE_URL).strip() or DEFAULT_SOURCE_URL
    wait_seconds = max(1, float(os.getenv("INVESTING_BROWSER_PAGE_WAIT_SECONDS", "4")))
    session = create_browser_session()
    try:
        await session.start()
        page = await session.get_current_page()
        await page.goto(source_url)
        await asyncio.sleep(wait_seconds)
        rows: List[Dict[str, Any]] = []
        for label in REQUIRED_CALENDAR_RANGES:
            if not await select_calendar_range(page, label):
                raise RuntimeError(f"Investing calendar range button is unavailable: {label}")
            await asyncio.sleep(wait_seconds)
            rows.extend(await extract_visible_calendar_rows(page, source_url))
        rows = deduplicate_rows(rows)
        if not rows:
            raise RuntimeError("Investing calendar returned no visible event rows for the required ranges.")
        payload = {
            "source": "investing_browser",
            "source_url": source_url,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "ranges": list(REQUIRED_CALENDAR_RANGES),
            "events": rows,
        }
        target = write_snapshot(payload)
        print(f"Investing calendar snapshot written: {target} ({len(rows)} events)")
        return payload
    finally:
        await session.kill()


async def _run_forever(interval_seconds: int) -> None:
    while True:
        try:
            await refresh_investing_calendar()
        except Exception as exc:  # leave the prior good snapshot intact
            print(f"Investing calendar refresh failed: {exc}", file=sys.stderr)
        await asyncio.sleep(interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh Investing economic calendar snapshot via Browser Use")
    parser.add_argument("--once", action="store_true", help="Refresh once then exit")
    parser.add_argument("--interval-seconds", type=int, default=int(os.getenv("INVESTING_CALENDAR_INTERVAL_SECONDS", "3600")))
    args = parser.parse_args()
    if args.once:
        asyncio.run(refresh_investing_calendar())
        return
    asyncio.run(_run_forever(max(900, args.interval_seconds)))


if __name__ == "__main__":
    main()
