"""Resolve Vietnamese equities from the active HOSE symbol master."""

from __future__ import annotations

import re
from typing import Callable


_IGNORED_TOKENS = {"HOSE", "HNX", "UPCOM", "AI", "API", "USD", "VND", "ETF"}
_WORDS = re.compile(r"[^\W_]+", re.UNICODE)


def _search_terms(message: str) -> list[tuple[str, int]]:
    words = _WORDS.findall(message or "")
    terms: list[tuple[str, int]] = []
    for word in words:
        if word.isascii() and word.isupper() and 2 <= len(word) <= 6 and word not in _IGNORED_TOKENS:
            terms.append((word, 100))
    for size in range(min(6, len(words)), 1, -1):
        for start in range(len(words) - size + 1):
            phrase = " ".join(words[start:start + size])
            terms.append((phrase, 50 + size))
    return list(dict.fromkeys(terms))[:24]


def rank_hose_candidates(message: str, rows: list[dict], selected_symbol: str = "") -> list[dict]:
    """Rank already matched catalog rows; callers still must validate each target."""
    exact_tokens = {word.upper() for word in _WORDS.findall(message or "") if word.isupper()}
    out = []
    for row in rows:
        symbol = str(row.get("symbol") or "").upper()
        if not symbol or str(row.get("exchange") or "").upper() != "HOSE":
            continue
        score = int(row.get("_match_score") or 0)
        if symbol in exact_tokens:
            score = max(score, 100)
        if symbol == selected_symbol.upper():
            score = max(score, 80)
        out.append({**row, "score": score})
    return sorted(out, key=lambda row: (-row["score"], row["symbol"]))


def resolve_hose_request(
    message: str,
    selected: dict,
    search_fn: Callable,
    validate_fn: Callable,
) -> dict:
    """Return resolved, ambiguous, or none; never return an unvalidated symbol."""
    selected = selected or {}
    selected_symbol = str(selected.get("symbol") or "").strip().upper() if selected.get("market") == "VNStock" else ""
    candidates: dict[str, dict] = {}

    terms = _search_terms(message)
    if selected_symbol:
        terms.append((selected_symbol, 80))
    for term, score in terms:
        try:
            rows = search_fn("VNStock", term, exchange="HOSE") or []
        except Exception:
            continue
        for row in rows:
            symbol = str(row.get("symbol") or "").strip().upper()
            if str(row.get("exchange") or "").upper() != "HOSE" or not symbol:
                continue
            try:
                valid_symbol = validate_fn("VNStock", symbol)
            except ValueError:
                continue
            if valid_symbol != symbol:
                continue
            match_score = score if symbol == term.upper() or score < 100 else 50
            if symbol == selected_symbol and term == selected_symbol:
                match_score = 80
            if match_score > int(candidates.get(symbol, {}).get("_match_score") or 0):
                candidates[symbol] = {**row, "symbol": symbol, "_match_score": match_score}

    ranked = rank_hose_candidates(message, list(candidates.values()), selected_symbol)
    for row in ranked:
        row.pop("_match_score", None)
    if not ranked:
        return {"status": "none", "target": None, "candidates": []}
    if len(ranked) > 1 and ranked[0]["score"] == ranked[1]["score"]:
        return {"status": "ambiguous", "target": None, "candidates": ranked}
    return {"status": "resolved", "target": ranked[0], "candidates": ranked}
