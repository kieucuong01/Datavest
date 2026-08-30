"""Import one authenticated legacy DataVest account into local QuantDinger.

The input is an export of read-only production API responses.  It is accepted
on stdin so it does not need to be copied into the repository or the backend
image.  Authentication is intentionally re-established with a new local
bcrypt hash; Better Auth sessions, tokens and password hashes are rejected and
never imported.

Usage:
    LOCAL_MIGRATION_PASSWORD='...' \
      python -m app.tools.import_production_account --stdin --apply

Without ``--apply`` the command only validates and reports the import plan.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.services.symbol_name import normalize_crypto_symbol
from app.services.user_service import UserService
from app.utils.db import get_db_connection
from app.utils.supported_markets import (
    UnsupportedSupportedMarketError,
    canonicalize_supported_symbol,
)


class AccountImportError(ValueError):
    """Raised when an account export is unsafe or cannot be mapped."""


_SECRET_KEYS = frozenset({
    "token",
    "sessiontoken",
    "accesstoken",
    "refreshtoken",
    "password",
    "passwordhash",
    "secret",
    "cookie",
    "setcookie",
})
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_USERNAME_RE = re.compile(r"[^a-z0-9_.-]+")
_MAX_EXPORT_BYTES = 50 * 1024 * 1024
_MAX_RECORD_BYTES = 5 * 1024 * 1024
_POSITION_GROUP = "DataVest Production"
_POSITION_TAG = "datavest-production-import"


def _mapping(value: object, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AccountImportError(f"invalid_{field}")
    return value


def _key_name(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _assert_no_secret_keys(value: object) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if _key_name(key) in _SECRET_KEYS:
                raise AccountImportError("secret_field")
            _assert_no_secret_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_no_secret_keys(nested)


def _canonical_json(value: object) -> str:
    try:
        # ``ensure_ascii=True`` also makes malformed legacy surrogate pairs
        # representable, while PostgreSQL still receives valid JSON text.
        return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)
    except (TypeError, ValueError) as exc:
        raise AccountImportError("invalid_json_payload") from exc


def _source_id(value: object, *, field: str = "source_record_id") -> str:
    result = str(value or "").strip()
    if not result:
        raise AccountImportError(f"missing_{field}")
    if len(result) > 255:
        digest = hashlib.sha256(result.encode("utf-8")).hexdigest()
        result = f"sha256:{digest}"
    return result


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _source_updated_at(value: Mapping[str, Any]) -> datetime | None:
    for key in ("updatedAt", "generatedAt", "dataAsOf", "createdAt", "asOf", "localDate"):
        parsed = _timestamp(value.get(key))
        if parsed is not None:
            return parsed
    return None


def _positive_number(value: object, *, field: str) -> float:
    try:
        number = float(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AccountImportError(f"invalid_{field}") from exc
    if not math.isfinite(number) or number <= 0:
        raise AccountImportError(f"invalid_{field}")
    return number


def safe_username(email: str, source_user_id: str) -> str:
    """Derive a deterministic local username without using source secrets."""
    local_part = str(email or "").split("@", 1)[0].lower()
    candidate = _USERNAME_RE.sub("_", local_part).strip("_.-")
    if len(candidate) < 3:
        suffix = re.sub(r"[^a-z0-9]", "", str(source_user_id or "").lower())[:12] or "user"
        candidate = f"user_{suffix}"
    return candidate[:50]


def infer_local_market(asset: Mapping[str, Any]) -> str:
    """Map legacy asset classes to explicit local market namespaces.

    VNStock is already supported by the optimizer gateway but is not yet part
    of the generic QuantDinger quote registry.  Keeping it explicit prevents a
    Vietnamese symbol from being silently routed to a Chinese or crypto feed.
    """
    asset_class = str(asset.get("assetClass") or asset.get("category") or "").strip().lower()
    currency = str(asset.get("currency") or "").strip().upper()
    symbol = str(asset.get("symbol") or asset.get("ticker") or "").strip().upper()
    if asset_class in {"crypto", "digital_asset", "digital asset"} or currency in {"USDT", "USDC"}:
        return "Crypto"
    if symbol in {"XAU", "XAUUSD", "GOLD"}:
        return "Forex"
    if asset_class in {"commodity", "commodities", "metal", "futures"} or symbol in {"XAU", "XAUUSD", "GOLD"}:
        raise UnsupportedSupportedMarketError(f"Unsupported imported asset market for '{symbol}'")
    if asset_class in {"forex", "fx", "currency"}:
        if symbol in {"XAU", "XAUUSD", "GOLD"}:
            return "Forex"
        raise UnsupportedSupportedMarketError(f"Unsupported imported FX symbol '{symbol}'")
    if currency == "VND":
        return "VNStock"
    if currency == "CNY":
        raise UnsupportedSupportedMarketError(f"Unsupported imported market for '{symbol}'")
    if currency == "HKD" or symbol.endswith(".HK"):
        raise UnsupportedSupportedMarketError(f"Unsupported imported market for '{symbol}'")
    return "USStock"


def normalize_source_symbol(symbol: object, market: str) -> str:
    value = str(symbol or "").strip().upper()
    if not value:
        raise AccountImportError("missing_asset_symbol")
    if market == "Crypto":
        return normalize_crypto_symbol(value)
    if market == "Forex":
        return canonicalize_supported_symbol(market, value)
    return value


@dataclass(frozen=True)
class RawImportRecord:
    data_type: str
    source_record_id: str
    payload: Mapping[str, Any] | list[Any] | Any
    source_updated_at: datetime | None
    payload_json: str
    payload_checksum: str


@dataclass(frozen=True)
class AccountImportPlan:
    source_user_id: str
    email: str
    username: str
    nickname: str
    avatar: str | None
    email_verified: bool
    position_rows: tuple[dict[str, Any], ...]
    watchlist_rows: tuple[dict[str, Any], ...]
    preference: Mapping[str, Any] | None
    records: tuple[RawImportRecord, ...]
    record_counts: Mapping[str, int]
    serialized_payload: str
    warnings: tuple[str, ...]


def _record(data_type: str, source_record_id: object, payload: Any) -> RawImportRecord:
    if isinstance(payload, Mapping):
        source_updated_at = _source_updated_at(payload)
    else:
        source_updated_at = None
    payload_json = _canonical_json(payload)
    if len(payload_json.encode("utf-8")) > _MAX_RECORD_BYTES:
        raise AccountImportError("record_too_large")
    return RawImportRecord(
        data_type=data_type[:64],
        source_record_id=_source_id(source_record_id),
        payload=payload,
        source_updated_at=source_updated_at,
        payload_json=payload_json,
        payload_checksum=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
    )


def _list_records(data_type: str, values: object) -> list[RawImportRecord]:
    if not isinstance(values, list):
        return []
    records: list[RawImportRecord] = []
    for index, value in enumerate(values):
        if isinstance(value, Mapping):
            identifier = value.get("id") or value.get("assetId") or value.get("sourceId") or index
        else:
            identifier = index
        records.append(_record(data_type, identifier, value))
    return records


def _build_records(payload: Mapping[str, Any]) -> tuple[RawImportRecord, ...]:
    records: list[RawImportRecord] = []
    user = _mapping(payload["user"], field="user")
    portfolio = _mapping(payload["portfolio"], field="portfolio")
    records.append(_record("user", user["id"], user))
    records.append(_record("portfolio", portfolio.get("portfolioId") or "primary", portfolio))
    for value in portfolio.get("holdings") or []:
        if isinstance(value, Mapping):
            records.append(_record("portfolio_holding", value.get("assetId") or value.get("ticker"), value))
    for value in portfolio.get("transactions") or []:
        if isinstance(value, Mapping):
            records.append(_record("portfolio_transaction", value.get("id"), value))
    for index, value in enumerate(portfolio.get("performance") or []):
        identifier = value.get("label") if isinstance(value, Mapping) else index
        records.append(_record("portfolio_performance", f"{index}:{identifier}", value))

    list_keys = (
        ("watchlist", "watchlist"),
        ("assets", "asset"),
        ("researchRuns", "research_run"),
        ("quantRuns", "quant_run"),
        ("customStrategies", "custom_strategy"),
    )
    for key, data_type in list_keys:
        records.extend(_list_records(data_type, payload.get(key)))

    wrapper_keys = (
        ("briefing", "briefing"),
        ("briefingDates", "briefing_dates"),
        ("preferences", "preferences"),
        ("regimes", "regimes"),
        ("calendar", "calendar"),
        ("cryptoPulse", "crypto_pulse"),
        ("dataHealth", "data_health"),
        ("notifications", "notifications"),
    )
    for key, data_type in wrapper_keys:
        if payload.get(key) is not None:
            records.append(_record(data_type, data_type, payload[key]))
    return tuple(records)


def _position_rows(payload: Mapping[str, Any], assets: Mapping[str, Mapping[str, Any]]) -> tuple[tuple[dict[str, Any], ...], tuple[str, ...]]:
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[tuple[str, str]] = set()
    portfolio = _mapping(payload["portfolio"], field="portfolio")
    for holding in portfolio.get("holdings") or []:
        if not isinstance(holding, Mapping):
            warnings.append("skipped_non_object_holding")
            continue
        asset = assets.get(str(holding.get("assetId") or ""), holding)
        try:
            market = infer_local_market(asset)
            symbol = normalize_source_symbol(holding.get("ticker") or asset.get("symbol"), market)
            quantity = _positive_number(holding.get("qty"), field="holding_quantity")
            entry_price = _positive_number(holding.get("cost"), field="holding_cost")
        except (AccountImportError, UnsupportedSupportedMarketError) as exc:
            warnings.append(f"skipped_holding:{exc}")
            continue
        identity = (market, symbol)
        if identity in seen:
            warnings.append(f"deduped_holding:{market}:{symbol}")
            continue
        seen.add(identity)
        rows.append({
            "market": market,
            "symbol": symbol,
            "name": str(holding.get("name") or asset.get("name") or symbol).strip()[:100],
            "quantity": quantity,
            "entry_price": entry_price,
            "source_asset_id": str(holding.get("assetId") or asset.get("id") or ""),
            "source_currency": str(holding.get("currency") or asset.get("currency") or "").strip().upper(),
        })
    return tuple(rows), tuple(warnings)


def _watchlist_rows(payload: Mapping[str, Any], assets: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in payload.get("watchlist") or []:
        if not isinstance(item, Mapping):
            continue
        asset = assets.get(str(item.get("assetId") or ""), item)
        try:
            market = infer_local_market(asset)
            symbol = normalize_source_symbol(item.get("symbol") or item.get("ticker") or asset.get("symbol"), market)
        except (AccountImportError, UnsupportedSupportedMarketError):
            continue
        if (market, symbol) in seen:
            continue
        seen.add((market, symbol))
        rows.append({
            "market": market,
            "symbol": symbol,
            "name": str(item.get("name") or asset.get("name") or symbol).strip()[:100],
            "exchange_id": str(item.get("exchangeId") or asset.get("provider") or "").strip()[:50],
            "market_type": str(item.get("marketType") or "spot").strip()[:20],
            "instrument_id": str(item.get("instrumentId") or asset.get("providerSymbol") or "").strip()[:120],
            "settle_currency": str(item.get("settleCurrency") or asset.get("currency") or "").strip()[:20],
        })
    return tuple(rows)


def build_import_plan(payload: object) -> AccountImportPlan:
    body = _mapping(payload, field="export")
    serialized_payload = _canonical_json(body)
    if len(serialized_payload.encode("utf-8")) > _MAX_EXPORT_BYTES:
        raise AccountImportError("export_too_large")
    _assert_no_secret_keys(body)
    if body.get("schemaVersion") != 1:
        raise AccountImportError("unsupported_export_version")
    user = _mapping(body.get("user"), field="user")
    source_user_id = _source_id(user.get("id"), field="source_user_id")
    email = str(user.get("email") or "").strip().lower()
    if not _EMAIL_RE.match(email):
        raise AccountImportError("missing_user_email")
    _mapping(body.get("portfolio"), field="portfolio")
    assets = {
        str(item.get("id")): item
        for item in (body.get("assets") or [])
        if isinstance(item, Mapping) and item.get("id")
    }
    positions, warnings = _position_rows(body, assets)
    records = _build_records(body)
    counts = Counter(record.data_type for record in records)
    preference_wrapper = body.get("preferences")
    preference: Mapping[str, Any] | None = None
    if isinstance(preference_wrapper, Mapping):
        candidate = preference_wrapper.get("preference", preference_wrapper)
        if isinstance(candidate, Mapping):
            preference = candidate
    return AccountImportPlan(
        source_user_id=source_user_id,
        email=email,
        username=safe_username(email, source_user_id),
        nickname=str(user.get("name") or user.get("nickname") or email.split("@", 1)[0]).strip()[:100],
        avatar=str(user.get("image") or "").strip()[:500] or None,
        email_verified=bool(user.get("emailVerified")),
        position_rows=positions,
        watchlist_rows=_watchlist_rows(body, assets),
        preference=preference,
        records=records,
        record_counts=dict(counts),
        serialized_payload=serialized_payload,
        warnings=warnings,
    )


def _unique_username(cur, candidate: str, source_user_id: str) -> str:
    cur.execute("SELECT id FROM qd_users WHERE username = ?", (candidate,))
    if not cur.fetchone():
        return candidate
    suffix = re.sub(r"[^a-z0-9]", "", source_user_id.lower())[:8] or "import"
    return f"{candidate[:41]}_{suffix}"


def _upsert_user(cur, plan: AccountImportPlan, password: str) -> int:
    password_hash = UserService().hash_password(password)
    cur.execute(
        "SELECT id, username, role FROM qd_users WHERE LOWER(email) = LOWER(?) FOR UPDATE",
        (plan.email,),
    )
    existing = cur.fetchone()
    if existing:
        user_id = int(existing["id"])
        cur.execute(
            """
            UPDATE qd_users
            SET password_hash = ?, nickname = ?, avatar = COALESCE(?, avatar),
                status = 'active', email_verified = ?, password_changed_at = NOW(), updated_at = NOW()
            WHERE id = ?
            """,
            (password_hash, plan.nickname, plan.avatar, plan.email_verified, user_id),
        )
        return user_id

    username = _unique_username(cur, plan.username, plan.source_user_id)
    cur.execute(
        """
        INSERT INTO qd_users
            (username, password_hash, email, nickname, avatar, status, role,
             email_verified, password_changed_at, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 'active', 'user', ?, NOW(), NOW(), NOW())
        RETURNING id
        """,
        (username, password_hash, plan.email, plan.nickname, plan.avatar, plan.email_verified),
    )
    created = cur.fetchone()
    if not created or created.get("id") is None:
        raise AccountImportError("local_user_create_failed")
    return int(created["id"])


def _persist_records(cur, user_id: int, plan: AccountImportPlan) -> int:
    for record in plan.records:
        cur.execute(
            """
            INSERT INTO qd_production_account_imports
                (user_id, source_user_id, data_type, source_record_id, payload,
                 source_updated_at, payload_checksum, imported_at)
            VALUES (?, ?, ?, ?, ?::jsonb, ?, ?, NOW())
            ON CONFLICT (user_id, data_type, source_record_id)
            DO UPDATE SET payload = EXCLUDED.payload,
                          source_updated_at = EXCLUDED.source_updated_at,
                          payload_checksum = EXCLUDED.payload_checksum,
                          imported_at = NOW()
            """,
            (
                user_id,
                plan.source_user_id,
                record.data_type,
                record.source_record_id,
                record.payload_json,
                record.source_updated_at,
                record.payload_checksum,
            ),
        )
    return len(plan.records)


def _persist_positions(cur, user_id: int, plan: AccountImportPlan) -> int:
    marker_tags = json.dumps([_POSITION_TAG, f"source-user:{plan.source_user_id}"], separators=(",", ":"))
    cur.execute(
        "DELETE FROM qd_manual_positions WHERE user_id = ? AND group_name = ? AND tags = ?",
        (user_id, _POSITION_GROUP, marker_tags),
    )
    for row in plan.position_rows:
        notes = json.dumps({
            "source": "datavest.vn",
            "sourceAssetId": row["source_asset_id"],
            "sourceCurrency": row["source_currency"],
            "migration": "production-account-v1",
        }, ensure_ascii=False, separators=(",", ":"))
        cur.execute(
            """
            INSERT INTO qd_manual_positions
                (user_id, market, symbol, name, side, quantity, entry_price,
                 entry_time, notes, tags, group_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'long', ?, ?, NULL, ?, ?, ?, NOW(), NOW())
            """,
            (
                user_id,
                row["market"],
                row["symbol"],
                row["name"],
                row["quantity"],
                row["entry_price"],
                notes,
                marker_tags,
                _POSITION_GROUP,
            ),
        )
    return len(plan.position_rows)


def _persist_watchlist(cur, user_id: int, plan: AccountImportPlan) -> int:
    for row in plan.watchlist_rows:
        cur.execute(
            """
            INSERT INTO qd_watchlist
                (user_id, market, symbol, name, exchange_id, market_type,
                 instrument_id, settle_currency, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NOW(), NOW())
            ON CONFLICT (user_id, market, symbol)
            DO UPDATE SET name = EXCLUDED.name, exchange_id = EXCLUDED.exchange_id,
                          market_type = EXCLUDED.market_type,
                          instrument_id = EXCLUDED.instrument_id,
                          settle_currency = EXCLUDED.settle_currency,
                          updated_at = NOW()
            """,
            (
                user_id,
                row["market"],
                row["symbol"],
                row["name"],
                row["exchange_id"],
                row["market_type"],
                row["instrument_id"],
                row["settle_currency"],
            ),
        )
    return len(plan.watchlist_rows)


def _persist_preference(cur, user_id: int, preference: Mapping[str, Any] | None) -> bool:
    if preference is None:
        return False
    markets = preference.get("markets") or []
    symbols = preference.get("assets") or preference.get("symbols") or []
    locale = str(preference.get("locale") or "vi").strip().lower()
    locale = locale if locale in {"vi", "en"} else "vi"
    base_currency = str(preference.get("baseCurrency") or "USD").strip().upper()[:8]
    horizon = str(preference.get("investmentHorizon") or "medium").strip()[:40]
    risk = str(preference.get("riskTolerance") or "balanced").strip()[:40]
    alerts = preference.get("alertPreferences") or {}
    cur.execute(
        """
        INSERT INTO user_insight_preferences
            (user_id, markets_json, symbols_json, locale, base_currency,
             investment_horizon, risk_tolerance, alert_preferences_json, created_at, updated_at)
        VALUES (?, ?::jsonb, ?::jsonb, ?, ?, ?, ?, ?::jsonb, NOW(), NOW())
        ON CONFLICT (user_id)
        DO UPDATE SET markets_json = EXCLUDED.markets_json,
                      symbols_json = EXCLUDED.symbols_json,
                      locale = EXCLUDED.locale,
                      base_currency = EXCLUDED.base_currency,
                      investment_horizon = EXCLUDED.investment_horizon,
                      risk_tolerance = EXCLUDED.risk_tolerance,
                      alert_preferences_json = EXCLUDED.alert_preferences_json,
                      updated_at = NOW()
        """,
        (
            user_id,
            _canonical_json(markets),
            _canonical_json(symbols),
            locale,
            base_currency,
            horizon,
            risk,
            _canonical_json(alerts),
        ),
    )
    return True


def apply_import(plan: AccountImportPlan, password: str) -> dict[str, Any]:
    if not password or len(password) < 6:
        raise AccountImportError("migration_password_required")
    migration_sql_path = Path(__file__).resolve().parents[2] / "migrations" / "20260826_production_account_import.sql"
    migration_sql = migration_sql_path.read_text(encoding="utf-8")
    with get_db_connection() as db:
        cur = db.cursor()
        cur.execute(migration_sql)
        user_id = _upsert_user(cur, plan, password)
        record_count = _persist_records(cur, user_id, plan)
        position_count = _persist_positions(cur, user_id, plan)
        watchlist_count = _persist_watchlist(cur, user_id, plan)
        preference_written = _persist_preference(cur, user_id, plan.preference)
        db.commit()
        cur.close()
    return {
        "userId": user_id,
        "recordsUpserted": record_count,
        "positionsUpserted": position_count,
        "watchlistUpserted": watchlist_count,
        "preferenceUpserted": preference_written,
    }


def build_report(plan: AccountImportPlan, *, apply: bool, result: Mapping[str, Any] | None = None) -> dict[str, Any]:
    report: dict[str, Any] = {
        "status": "OK",
        "mode": "APPLY" if apply else "DRY_RUN",
        "sourceUserIdPresent": bool(plan.source_user_id),
        "emailPresent": bool(plan.email),
        "plannedPositionCount": len(plan.position_rows),
        "plannedWatchlistCount": len(plan.watchlist_rows),
        "recordCounts": dict(plan.record_counts),
        "warnings": list(plan.warnings),
    }
    if result:
        report.update(result)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stdin", action="store_true", help="Read the export JSON from stdin")
    parser.add_argument("--apply", action="store_true", help="Write the migration to local PostgreSQL")
    parser.add_argument("--password-env", default="LOCAL_MIGRATION_PASSWORD", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not args.stdin:
        raise SystemExit("--stdin is required")
    try:
        payload = json.load(sys.stdin)
        plan = build_import_plan(payload)
        result = None
        if args.apply:
            result = apply_import(plan, os.environ.get(args.password_env, ""))
        print(json.dumps(build_report(plan, apply=args.apply, result=result), ensure_ascii=False, default=str))
        return 0
    except (json.JSONDecodeError, AccountImportError) as exc:
        print(json.dumps({"status": "REJECTED", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
