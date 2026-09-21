"""Shared point-in-time evidence for active HOSE equities."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from typing import Any, Callable

from app.data.market_symbols_seed import get_active_hose_symbol
from app.data_sources.vn_market_providers import VndirectProvider
from app.services.vietnam_provenance import build_hose_provenance
from app.utils.logger import get_logger


logger = get_logger(__name__)

_FUNDAMENTAL_SNAPSHOT_FIELDS = (
    "revenue", "net_income", "book_value", "shareholder_equity", "total_debt",
    "free_cash_flow", "shares_outstanding", "market_cap", "pe_ratio", "pb_ratio",
    "return_on_equity", "revenue_growth", "debt_to_equity",
)


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _parse_instant(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def enrich_vietnam_provenance(
    snapshot: dict[str, Any], data: dict[str, Any], components: list[str]
) -> dict[str, Any]:
    evidence = data.get("vietnam_evidence") if isinstance(data.get("vietnam_evidence"), dict) else {}
    if not evidence:
        return snapshot
    if (evidence.get("fundamentals") or {}).get("observations"):
        components.append("fundamentals")
    if evidence.get("corporateActions"):
        components.append("corporate_actions")
    if evidence.get("disclosures"):
        components.append("disclosures")
    if evidence.get("marketContext"):
        components.append("vietnam_market_context")
    snapshot.update({
        "evidence_checksum": str(evidence.get("checksum") or ""),
        "provider_sources": list(dict.fromkeys(
            str(item.get("provider") or "")
            for item in (evidence.get("sources") or [])
            if isinstance(item, dict) and item.get("provider")
        )),
        "data_gaps": evidence.get("dataGaps") or [],
    })
    return snapshot


def _latest(
    rows: list[dict[str, Any]], metric: str, *, prefer_annual: bool = False
) -> dict[str, Any] | None:
    matching = [row for row in rows if row.get("metric") == metric]
    if not matching:
        return None
    annual = [row for row in matching if row.get("frequency") == "ANNUAL"]
    if prefer_annual and annual:
        matching = annual
    return max(
        matching,
        key=lambda row: (
            str(row.get("periodEnd") or ""),
            1 if row.get("reportScope") == "CONSOLIDATED" else 0,
            str(row.get("availableAt") or ""),
            abs(_finite(row.get("value")) or 0.0),
        ),
    )


class VietnamEvidenceRepository:
    """Best-effort PostgreSQL persistence for normalized provider evidence."""

    @staticmethod
    def persist(evidence: dict[str, Any]) -> None:
        from app.utils.db import get_db_connection

        instrument = evidence.get("instrument") or {}
        symbol = str(instrument.get("symbol") or "").upper()
        if not symbol:
            return
        with get_db_connection() as db:
            cur = db.cursor()
            for row in (evidence.get("fundamentals") or {}).get("observations") or []:
                cur.execute(
                    """
                    INSERT INTO qd_vietnam_financial_observations
                      (symbol, metric, item_code, label, numeric_value, unit, period_end,
                       available_at, revision_at, frequency, report_scope, model_type,
                       source, source_url, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?::jsonb)
                    ON CONFLICT (symbol, item_code, period_end, available_at, report_scope, source)
                    DO UPDATE SET
                      metric = EXCLUDED.metric, label = EXCLUDED.label,
                      numeric_value = EXCLUDED.numeric_value, unit = EXCLUDED.unit,
                      revision_at = EXCLUDED.revision_at, frequency = EXCLUDED.frequency,
                      model_type = EXCLUDED.model_type, source_url = EXCLUDED.source_url,
                      metadata_json = EXCLUDED.metadata_json, ingested_at = NOW()
                    """,
                    (
                        symbol, row.get("metric"), row.get("itemCode"), row.get("label"),
                        row.get("value"), row.get("unit"), row.get("periodEnd"), row.get("availableAt"),
                        row.get("revisionAt"), row.get("frequency"), row.get("reportScope"),
                        row.get("modelType"), row.get("source"), row.get("sourceUrl"),
                        _canonical_json({"checksum": evidence.get("checksum")}),
                    ),
                )
            for snapshot in VietnamEvidenceRepository._fundamental_snapshots(evidence):
                cur.execute(
                    f"""
                    INSERT INTO qd_fundamental_snapshots
                      (market, symbol, period_end, available_at, frequency, currency,
                       {', '.join(_FUNDAMENTAL_SNAPSHOT_FIELDS)}, source,
                       source_version, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, {', '.join(['?'] * len(_FUNDAMENTAL_SNAPSHOT_FIELDS))},
                            ?, ?, ?::jsonb)
                    ON CONFLICT (market, symbol, period_end, available_at, source)
                    DO UPDATE SET
                      {', '.join(f'{field} = EXCLUDED.{field}' for field in _FUNDAMENTAL_SNAPSHOT_FIELDS)},
                      frequency = EXCLUDED.frequency, currency = EXCLUDED.currency,
                      source_version = EXCLUDED.source_version,
                      metadata_json = EXCLUDED.metadata_json, ingested_at = NOW()
                    """,
                    (
                        "VNStock", symbol, snapshot["period_end"], snapshot["available_at"],
                        snapshot["frequency"], snapshot["currency"],
                        *(snapshot.get(field) for field in _FUNDAMENTAL_SNAPSHOT_FIELDS),
                        snapshot["source"], snapshot["source_version"],
                        _canonical_json(snapshot["metadata"]),
                    ),
                )
            for row in [*(evidence.get("corporateActions") or []), *(evidence.get("disclosures") or [])]:
                cur.execute(
                    """
                    INSERT INTO qd_vietnam_events
                      (source, event_id, symbol, category, event_type, title, available_at,
                       effective_date, actual_date, source_url, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?::jsonb)
                    ON CONFLICT (source, event_id) DO UPDATE SET
                      category = EXCLUDED.category, event_type = EXCLUDED.event_type,
                      title = EXCLUDED.title, available_at = EXCLUDED.available_at,
                      effective_date = EXCLUDED.effective_date, actual_date = EXCLUDED.actual_date,
                      source_url = EXCLUDED.source_url, payload_json = EXCLUDED.payload_json,
                      ingested_at = NOW()
                    """,
                    (
                        row.get("source"), row.get("id"), symbol, row.get("category"), row.get("type"),
                        row.get("title"), row.get("availableAt"), row.get("effectiveDate"),
                        row.get("actualDate"), row.get("sourceUrl"), _canonical_json(row),
                    ),
                )
            db.commit()
            cur.close()

    @staticmethod
    def _fundamental_snapshots(evidence: dict[str, Any]) -> list[dict[str, Any]]:
        rows = (evidence.get("fundamentals") or {}).get("observations") or []
        groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
        for row in rows:
            period_end = str(row.get("periodEnd") or "")[:10]
            available_at = str(row.get("availableAt") or "")[:10]
            source = str(row.get("source") or "vndirect")
            frequency = str(row.get("frequency") or "quarterly").lower()
            if period_end and available_at:
                groups.setdefault((period_end, available_at, source, frequency), []).append(row)

        snapshots: list[dict[str, Any]] = []
        for (period_end, available_at, source, frequency), group in sorted(groups.items()):
            metrics: dict[str, float] = {}
            for row in group:
                metric = str(row.get("metric") or "")
                value = _finite(row.get("value"))
                if metric in _FUNDAMENTAL_SNAPSHOT_FIELDS and value is not None:
                    current = metrics.get(metric)
                    if current is None or abs(value) > abs(current):
                        metrics[metric] = value
            income = metrics.get("net_income")
            equity = metrics.get("shareholder_equity")
            debt = metrics.get("total_debt")
            if income is not None and equity not in (None, 0.0):
                multiplier = 1.0 if frequency == "annual" else 4.0
                metrics["return_on_equity"] = income * multiplier / equity
            if debt is not None and equity not in (None, 0.0):
                metrics["debt_to_equity"] = debt / equity
            if not metrics:
                continue
            snapshots.append({
                "period_end": period_end,
                "available_at": available_at,
                "frequency": frequency,
                "currency": str(group[0].get("unit") or "VND"),
                "source": f"vietnam_evidence:{source}",
                "source_version": str(evidence.get("checksum") or "")[:64],
                "metadata": {
                    "pointInTime": True,
                    "reportScope": str(group[0].get("reportScope") or "UNKNOWN"),
                    "observationCount": len(group),
                },
                **metrics,
            })
        return snapshots


class VietnamEvidenceService:
    def __init__(
        self,
        *,
        provider: Any | None = None,
        instrument_loader: Callable[[str], dict[str, Any] | None] = get_active_hose_symbol,
        market_context_loader: Callable[[], dict[str, Any]] | None = None,
        persist: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.provider = provider or VndirectProvider()
        self.instrument_loader = instrument_loader
        self.market_context_loader = market_context_loader or self._load_market_context
        self.persist = persist or VietnamEvidenceRepository.persist

    def build(
        self,
        *,
        symbol: str,
        price: dict[str, Any] | None = None,
        technical: dict[str, Any] | None = None,
        as_of: datetime | None = None,
    ) -> dict[str, Any]:
        canonical = str(symbol or "").strip().upper().removesuffix(".VN")
        catalog = self.instrument_loader(canonical)
        if not catalog:
            raise ValueError("unsupported_or_inactive_vn_symbol")
        cutoff = _aware_utc(as_of)
        gaps: list[dict[str, str]] = [
            {"field": "foreignRoom", "reason": "NO_VERIFIED_FREE_SOURCE"},
            {"field": "ownershipStructure", "reason": "NO_VERIFIED_FREE_SOURCE"},
        ]

        profile = self._load_optional("companyProfile", gaps, self.provider.fetch_company_profile, canonical, default={})
        raw_observations = self._load_optional(
            "fundamentalStatements", gaps, self.provider.fetch_financial_statements, canonical, default=[]
        )
        raw_events = self._load_optional("corporateActions", gaps, self.provider.fetch_events, canonical, default=[])
        observations = [
            dict(row)
            for row in raw_observations
            if isinstance(row, dict)
            and (instant := _parse_instant(row.get("availableAt"))) is not None
            and instant <= cutoff
            and (period_end := _parse_date(row.get("periodEnd"))) is not None
            and period_end <= cutoff.date()
        ]
        events = [
            dict(row)
            for row in raw_events
            if isinstance(row, dict)
            and (instant := _parse_instant(row.get("availableAt"))) is not None
            and instant <= cutoff
        ]
        if not observations and not any(gap["field"] == "fundamentalStatements" for gap in gaps):
            gaps.append({"field": "fundamentalStatements", "reason": "NO_POINT_IN_TIME_OBSERVATIONS"})
        if any(row.get("reportScope") == "UNKNOWN" for row in observations):
            gaps.append({"field": "reportScope", "reason": "PROVIDER_DOES_NOT_DISTINGUISH_SCOPE"})

        instrument = {
            "market": "VNStock",
            "symbol": canonical,
            "exchange": "HOSE",
            "name": profile.get("name") or catalog.get("name") or canonical,
            "shortName": profile.get("shortName") or "",
            "assetClass": profile.get("assetClass") or catalog.get("asset_class") or "equity",
            "sector": profile.get("sector") or catalog.get("sector") or "",
            "listedDate": profile.get("listedDate") or catalog.get("listed_date"),
            "tradingStatus": catalog.get("trading_status") or "ACTIVE",
            "website": profile.get("website") or "",
            "sharesOutstanding": _finite(profile.get("sharesOutstanding")),
        }
        price_payload = dict(price or {})
        technical_payload = dict(technical or {})
        derived = self._derive_metrics(observations, instrument, price_payload)
        if "pe_ratio" not in derived:
            gaps.append({"field": "peRatio", "reason": "INSUFFICIENT_FREE_SOURCE_DATA"})
        if "pb_ratio" not in derived:
            gaps.append({"field": "pbRatio", "reason": "INSUFFICIENT_FREE_SOURCE_DATA"})
        try:
            market_context = self.market_context_loader() or {}
        except Exception as exc:
            logger.warning("VN market context unavailable: %s", exc)
            market_context = {}
            gaps.append({"field": "marketContext", "reason": "PROVIDER_UNAVAILABLE"})

        evidence = {
            "version": "vietnam-evidence-v1",
            "asOf": cutoff.isoformat(),
            "instrument": instrument,
            "price": price_payload,
            "technical": technical_payload,
            "fundamentals": {
                "observations": sorted(
                    observations,
                    key=lambda row: (str(row.get("periodEnd") or ""), str(row.get("metric") or "")),
                ),
                "derivedMetrics": derived,
            },
            "corporateActions": [row for row in events if row.get("category") == "corporateAction"],
            "disclosures": [row for row in events if row.get("category") != "corporateAction"],
            "marketContext": market_context,
            "dataGaps": gaps,
            "sources": self._sources(profile, observations, events, price_payload),
        }
        evidence["provenance"] = build_hose_provenance(evidence, fetched_at=datetime.now(timezone.utc))
        evidence["checksum"] = hashlib.sha256(_canonical_json(evidence).encode("utf-8")).hexdigest()
        try:
            self.persist(evidence)
        except Exception as exc:
            logger.warning("VN evidence persistence failed for %s: %s", canonical, exc)
        return evidence

    @staticmethod
    def _load_optional(field: str, gaps: list[dict[str, str]], function: Callable, *args, default: Any) -> Any:
        try:
            return function(*args) or default
        except Exception as exc:
            logger.warning("VN evidence provider failed for %s: %s", field, exc)
            gaps.append({"field": field, "reason": "PROVIDER_UNAVAILABLE"})
            return default

    @staticmethod
    def _derive_metrics(
        observations: list[dict[str, Any]], instrument: dict[str, Any], price: dict[str, Any]
    ) -> dict[str, Any]:
        values: dict[str, float] = {}
        flow_metrics = {
            "revenue", "net_income", "free_cash_flow", "operating_cash_flow", "earnings_per_share"
        }
        for metric in (
            "revenue", "net_income", "shareholder_equity", "total_debt",
            "free_cash_flow", "operating_cash_flow", "earnings_per_share",
        ):
            row = _latest(observations, metric, prefer_annual=metric in flow_metrics)
            value = _finite(row.get("value")) if row else None
            if value is not None:
                values[metric] = value

        annual_revenue = [
            row for row in observations
            if row.get("metric") == "revenue" and row.get("frequency") == "ANNUAL"
        ]
        revenue_rows = sorted(
            annual_revenue or [row for row in observations if row.get("metric") == "revenue"],
            key=lambda row: str(row.get("periodEnd") or ""),
        )
        revenue_by_period: dict[str, dict[str, Any]] = {}
        for row in revenue_rows:
            period = str(row.get("periodEnd") or "")
            current = revenue_by_period.get(period)
            if current is None or abs(_finite(row.get("value")) or 0.0) > abs(_finite(current.get("value")) or 0.0):
                revenue_by_period[period] = row
        revenue_rows = [revenue_by_period[key] for key in sorted(revenue_by_period)]
        if len(revenue_rows) >= 2:
            previous = _finite(revenue_rows[-2].get("value"))
            latest = _finite(revenue_rows[-1].get("value"))
            if latest is not None and previous not in (None, 0.0):
                values["revenue_growth"] = (latest / previous - 1.0) * 100.0

        income = values.get("net_income")
        equity = values.get("shareholder_equity")
        debt = values.get("total_debt")
        if income is not None and equity not in (None, 0.0):
            values["return_on_equity"] = income / equity * 100.0
        if debt is not None and equity not in (None, 0.0):
            values["debt_to_equity"] = debt / equity

        shares = _finite(instrument.get("sharesOutstanding"))
        last_price = _finite(price.get("price"))
        if shares is not None and last_price is not None:
            values["market_cap"] = shares * last_price
            if income not in (None, 0.0):
                values["pe_ratio"] = values["market_cap"] / income
            if equity not in (None, 0.0):
                values["pb_ratio"] = values["market_cap"] / equity
        eps = values.get("earnings_per_share")
        if "pe_ratio" not in values and last_price is not None and eps not in (None, 0.0):
            values["pe_ratio"] = last_price / eps
        values["ratioUnit"] = "PERCENTAGE_POINTS"
        return values

    @staticmethod
    def _sources(
        profile: dict[str, Any], observations: list[dict[str, Any]], events: list[dict[str, Any]], price: dict[str, Any]
    ) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        candidates = [profile, *observations, *events]
        if price.get("source"):
            candidates.append({"source": price.get("source"), "sourceUrl": ""})
        for item in candidates:
            provider = str(item.get("source") or "").strip()
            source_url = str(item.get("sourceUrl") or "").strip()
            key = (provider, source_url)
            if provider and key not in seen:
                seen.add(key)
                result.append({"provider": provider, "url": source_url})
        return result

    @staticmethod
    def _load_market_context() -> dict[str, Any]:
        from app.services.kline import KlineService

        service = KlineService()
        benchmarks: dict[str, Any] = {}
        for symbol in ("VNINDEX", "VN30"):
            quote = service.get_realtime_price("VNStock", symbol, force_refresh=True)
            if _finite(quote.get("price")) not in (None, 0.0):
                benchmarks[symbol] = quote
        return {"benchmarks": benchmarks}


_service: VietnamEvidenceService | None = None


def get_vietnam_evidence_service() -> VietnamEvidenceService:
    global _service
    if _service is None:
        _service = VietnamEvidenceService()
    return _service


__all__ = [
    "VietnamEvidenceRepository", "VietnamEvidenceService", "enrich_vietnam_provenance",
    "get_vietnam_evidence_service",
]
