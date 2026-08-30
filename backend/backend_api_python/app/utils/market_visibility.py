"""Market visibility resolution (shared across watchlist / agent / radar).

Operators control which markets the UI exposes through environment variables.
This module is the single source of truth so the *watchlist add-symbol modal*
(`/api/market/types`), the *Agent API market catalog*
(`/api/agent/v1/markets`), and the *home AI radar*
(`/api/global-market/opportunities`) all agree — without it the three places
drifted apart and operators had to disable the same market in three places.

The product allowlist is always the four supported markets. ``ENABLED_MARKETS``
may narrow that set, but legacy flags cannot re-enable retired markets.
"""

from __future__ import annotations

import os
from typing import Any, Iterable, List, Set

from app.utils.supported_markets import (
    DEFAULT_VISIBLE_MARKETS,
    SUPPORTED_MARKETS,
    canonicalize_supported_symbol,
    normalize_supported_market,
)


_KNOWN_MARKETS = SUPPORTED_MARKETS


def _flag(name: str, default: str) -> bool:
    return str(os.getenv(name, default)).strip().lower() in ('1', 'true', 'yes', 'on')


def _parse_csv(name: str) -> Set[str]:
    raw = (os.getenv(name) or '').strip()
    if not raw:
        return set()
    return {part.strip() for part in raw.split(',') if part.strip()}


def enabled_markets_whitelist() -> Set[str]:
    """Return the active ENABLED_MARKETS whitelist, or empty set when unset.

    Empty set is the "no whitelist" signal; callers should fall back to the
    legacy ``SHOW_*`` flags via :func:`is_market_visible`.
    """
    return {
        normalize_supported_market(part)
        for part in _parse_csv('ENABLED_MARKETS')
        if _is_supported(part)
    }


def _is_supported(value: str) -> bool:
    try:
        normalize_supported_market(value)
    except ValueError:
        return False
    return True


def is_market_visible(market: str) -> bool:
    """True iff ``market`` should be exposed in user-facing market pickers."""
    raw = (market or '').strip()
    if not raw or not _is_supported(raw):
        return False
    m = normalize_supported_market(raw)

    whitelist = enabled_markets_whitelist()
    if whitelist:
        return m in whitelist

    return m in DEFAULT_VISIBLE_MARKETS


def filter_market_items(items: Iterable[Any], key: str = 'value') -> List[Any]:
    """Filter a list whose items are either market strings or dicts of shape
    ``{key: <market>, ...}``. Items with falsy / unknown market values are
    dropped; the relative order of surviving items is preserved.
    """
    out: List[Any] = []
    for it in items or []:
        if isinstance(it, dict):
            raw_mk = (it.get(key) or '').strip()
            mk = raw_mk
        elif isinstance(it, str):
            raw_mk = it.strip()
            mk = raw_mk
        else:
            continue
        if mk and is_market_visible(mk):
            if isinstance(it, dict):
                try:
                    canonical_market = normalize_supported_market(mk)
                    item = dict(it)
                    item[key] = canonical_market
                    if 'symbol' in item and item.get('symbol'):
                        item['symbol'] = canonicalize_supported_symbol(canonical_market, item['symbol'])
                    out.append(item)
                except ValueError:
                    continue
            else:
                out.append(it)
    return out


def hidden_markets() -> Set[str]:
    """Return the set of known markets currently hidden by env config.

    Useful for *post-filtering* cached payloads (e.g. opportunities radar)
    where the data was computed before the latest env flip.
    """
    return {m for m in _KNOWN_MARKETS if not is_market_visible(m)}
