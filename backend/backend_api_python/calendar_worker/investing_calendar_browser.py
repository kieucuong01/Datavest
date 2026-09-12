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
RANGE_LABEL_ALIASES = {
    "Hôm qua": ("Hôm qua", "Yesterday"),
    "Hôm nay": ("Hôm nay", "Today"),
    "Tuần này": ("Tuần này", "This Week"),
    "Tuần tới": ("Tuần tới", "Next Week"),
}
DEFAULT_SOURCE_URLS = (DEFAULT_SOURCE_URL, "https://www.investing.com/economic-calendar/")


def _env_bool(name: str, default: bool = False) -> bool:
    return str(os.getenv(name, str(default))).strip().lower() in {"1", "true", "yes", "on"}


def _decode_browser_value(value: Any) -> Any:
    """Browser Use v0.13 returns primitive/object evaluation results as text."""
    if not isinstance(value, str):
        return value
    if value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
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
        "enable_default_extensions": False,
        "allowed_domains": ["vn.investing.com", "www.investing.com", "investing.com"],
        "user_data_dir": str(Path(os.getenv("INVESTING_BROWSER_USER_DATA_DIR", "data/browser-profiles/investing")).expanduser().resolve()),
        "profile_directory": os.getenv("INVESTING_BROWSER_PROFILE_DIRECTORY", "Default"),
    }
    if executable_path:
        options["executable_path"] = executable_path
    return BrowserSession(**options)


async def select_calendar_range(page: Any, label: str) -> bool:
    """Click one exact, user-visible range button in the rendered calendar.

    Investing can render the public calendar in Vietnamese or English based on
    host, locale and browser preferences. The internal range names remain
    Vietnamese so the API contract stays stable.
    """
    quoted_labels = json.dumps(RANGE_LABEL_ALIASES.get(label, (label,)), ensure_ascii=False)
    result = await page.evaluate(f"""
      () => {{
        const labels = {quoted_labels};
        const normalize = (value) => (value || '').trim().replace(/\\s+/gu, ' ').toLocaleLowerCase();
        const normalizedLabels = labels.map(normalize);
        const button = Array.from(document.querySelectorAll('button'))
          .find((item) => normalizedLabels.includes(normalize(item.innerText)) && item.offsetParent !== null);
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
            const text = (heading.innerText || '').trim();
            const match = text.match(/(\\d{{1,2}})\\s+tháng\\s+(\\d{{1,2}}),\\s*(\\d{{4}})/iu);
            if (match) {{
              date = `${{match[3]}}-${{match[2].padStart(2, '0')}}-${{match[1].padStart(2, '0')}}`;
            }} else {{
              const english = text.match(/(January|February|March|April|May|June|July|August|September|October|November|December)\\s+(\\d{{1,2}}),\\s*(\\d{{4}})/iu);
              if (english) {{
                const months = {{ january: 1, february: 2, march: 3, april: 4, may: 5, june: 6,
                  july: 7, august: 8, september: 9, october: 10, november: 11, december: 12 }};
                const month = months[english[1].toLowerCase()];
                date = `${{english[3]}}-${{String(month).padStart(2, '0')}}-${{english[2].padStart(2, '0')}}`;
              }}
            }}
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
    seen = {}
    for row in rows:
        key = tuple(str(row.get(field, "")).strip().lower() for field in ("date", "time", "country", "name"))
        if key in seen:
            seen[key].update({field: value for field, value in row.items()
                              if value is not None and str(value).strip() not in {"", "-", "—", "–"}})
            continue
        seen[key] = dict(row)
        unique.append(seen[key])
    return unique


async def refresh_investing_calendar() -> Dict[str, Any]:
    configured_url = os.getenv("INVESTING_CALENDAR_URL", "").strip()
    configured_urls = os.getenv("INVESTING_CALENDAR_URLS", "").strip()
    if configured_urls:
        source_urls = [item.strip() for item in configured_urls.split(",") if item.strip()]
    else:
        source_urls = [configured_url or DEFAULT_SOURCE_URL]
        if not configured_url or configured_url == DEFAULT_SOURCE_URL:
            source_urls.extend(DEFAULT_SOURCE_URLS[1:])
    source_urls = list(dict.fromkeys(source_urls))
    wait_seconds = max(1, float(os.getenv("INVESTING_BROWSER_PAGE_WAIT_SECONDS", "4")))
    session = create_browser_session()
    try:
        await session.start()
        page = await session.get_current_page()
        errors = []
        for source_url in source_urls:
            try:
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
            except Exception as exc:
                errors.append(f"{source_url}: {exc}")
        raise RuntimeError("; ".join(errors))
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
