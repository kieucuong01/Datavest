"""Free Vietnamese market-data providers with a stable internal contract."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import date, datetime, time as day_time, timedelta
import math
import os
import threading
import time
from typing import Any, Callable, Iterable, Protocol
from zoneinfo import ZoneInfo

import requests


VN_ZONE = ZoneInfo("Asia/Ho_Chi_Minh")


@dataclass(frozen=True)
class VietnamMarketDataSettings:
    timeout_seconds: int = 12
    requests_per_minute: int = 50

    @classmethod
    def from_env(cls) -> "VietnamMarketDataSettings":
        return cls(
            timeout_seconds=max(1, int(os.getenv("VN_MARKET_DATA_TIMEOUT_SEC", "12"))),
            requests_per_minute=max(1, int(os.getenv("VNDIRECT_MARKET_DATA_RPM", "50"))),
        )


@dataclass(frozen=True)
class VietnamSecurity:
    symbol: str
    name: str
    exchange: str
    asset_class: str
    sector: str = ""
    listed_date: date | None = None
    delisted_date: date | None = None
    trading_status: str = "ACTIVE"
    source: str = "vndirect"


class VietnamPriceProvider(Protocol):
    name: str

    def fetch_ohlcv(
        self, symbol: str, timeframe: str, start: date, end: date, limit: int
    ) -> list[dict[str, Any]]: ...


class RequestRateGate:
    """Small process-local gate; upstream provider limits remain authoritative."""

    def __init__(
        self,
        max_requests: int,
        period_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.max_requests = max(1, int(max_requests))
        self.period_seconds = max(0.001, float(period_seconds))
        self.clock = clock
        self.sleeper = sleeper
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = self.clock()
            while self._timestamps and now - self._timestamps[0] >= self.period_seconds:
                self._timestamps.popleft()
            if len(self._timestamps) >= self.max_requests:
                now = self.clock()
                wait = max(0.0, self.period_seconds - (now - self._timestamps[0]))
                if wait:
                    self.sleeper(wait)
                now += wait
                while self._timestamps and now - self._timestamps[0] >= self.period_seconds:
                    self._timestamps.popleft()
            self._timestamps.append(now)


_PROVIDER_GATES_LOCK = threading.Lock()
_VNDIRECT_PROVIDER_GATES: dict[int, RequestRateGate] = {}
_YAHOO_PROVIDER_GATE = RequestRateGate(30, 60)


def _shared_vndirect_gate(requests_per_minute: int) -> RequestRateGate:
    budget = max(1, int(requests_per_minute))
    with _PROVIDER_GATES_LOCK:
        gate = _VNDIRECT_PROVIDER_GATES.get(budget)
        if gate is None:
            gate = RequestRateGate(budget, 60)
            _VNDIRECT_PROVIDER_GATES[budget] = gate
        return gate


def _value(item: Any, *names: str, default: Any = "") -> Any:
    if isinstance(item, dict):
        lowered = {str(key).lower(): value for key, value in item.items()}
        for name in names:
            if name in item:
                return item[name]
            if name.lower() in lowered:
                return lowered[name.lower()]
        return default
    for name in names:
        if hasattr(item, name):
            return getattr(item, name)
    return default


def _parse_date(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    raw = raw.split(" ", 1)[0]
    for pattern in ("%Y/%m/%d", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, pattern).date()
        except ValueError:
            continue
    return None


def _iso_utc(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        parsed_date = _parse_date(raw)
        if parsed_date is None:
            return None
        parsed = datetime.combine(parsed_date, day_time.min, tzinfo=VN_ZONE)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=VN_ZONE)
    return parsed.astimezone(ZoneInfo("UTC")).isoformat()


def _report_frequency(value: Any) -> str:
    normalized = str(value or "").strip().upper()
    if any(token in normalized for token in ("YEAR", "ANNUAL", "NĂM")):
        return "ANNUAL"
    return "QUARTERLY"


def _report_scope(*values: Any) -> str:
    normalized = " ".join(str(value or "") for value in values).strip().upper()
    if any(token in normalized for token in ("SEPARATE", "RIÊNG", "PARENT")):
        return "SEPARATE"
    if any(token in normalized for token in ("CONSOLIDATED", "HỢP NHẤT", "HOP NHAT")):
        return "CONSOLIDATED"
    return "UNKNOWN"


def _item_code(value: Any) -> str:
    try:
        number = float(value)
        if math.isfinite(number) and number.is_integer():
            return str(int(number))
    except (TypeError, ValueError, OverflowError):
        pass
    return str(value or "").strip()


def _canonical_financial_metric(label: Any, item_code: Any) -> str:
    code = _item_code(item_code)
    code_metrics = {
        "21001": "revenue",
        "23003": "net_income",
        "14000": "shareholder_equity",
        "13000": "total_debt",
        "32000": "operating_cash_flow",
        "700087": "earnings_per_share",
    }
    if code in code_metrics:
        return code_metrics[code]
    normalized = " ".join(str(label or "").lower().split())
    if any(token in normalized for token in ("tỷ lệ", "ratio", "chưa phân phối", "undistributed")):
        return code or "unknown"
    patterns = (
        (("doanh thu thuần", "net revenue", "net sales", "total revenue"), "revenue"),
        (("lợi nhuận sau thuế", "net income", "profit after tax"), "net_income"),
        (("vốn chủ sở hữu", "owners equity", "shareholder equity", "stockholders equity"), "shareholder_equity"),
        (("tổng nợ", "nợ phải trả", "total debt", "total liabilities"), "total_debt"),
        (("lưu chuyển tiền thuần từ hoạt động kinh doanh", "operating cash flow"), "operating_cash_flow"),
        (("dòng tiền tự do", "free cash flow"), "free_cash_flow"),
    )
    for aliases, metric in patterns:
        if any(alias in normalized for alias in aliases):
            return metric
    return code or "unknown"


def _timestamp(value: Any) -> int:
    raw = str(value or "").strip()
    for pattern in (
        "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S",
        "%Y/%m/%d", "%Y-%m-%d", "%d/%m/%Y",
    ):
        try:
            return int(datetime.strptime(raw, pattern).replace(tzinfo=VN_ZONE).timestamp())
        except ValueError:
            continue
    raise ValueError("invalid trading date")


def _normalize_bars(records: Iterable[Any]) -> list[dict[str, Any]]:
    bars: list[dict[str, Any]] = []
    seen = set()
    for record in records or []:
        try:
            trading_date = _value(record, "trading_date", "TradingDate")
            time_value = str(_value(record, "time", "Time") or "").strip()
            stamp = _timestamp(f"{trading_date} {time_value}".strip())
            open_price = float(_value(record, "open_price", "Open", "open"))
            high = float(_value(record, "high_price", "High", "high"))
            low = float(_value(record, "low_price", "Low", "low"))
            close = float(_value(record, "close_price", "Close", "close"))
            volume = float(_value(record, "volume", "Volume", default=0) or 0)
        except (TypeError, ValueError, OverflowError):
            continue
        if stamp in seen or any(not math.isfinite(value) for value in (open_price, high, low, close, volume)):
            continue
        if min(open_price, high, low, close) <= 0 or volume < 0:
            continue
        if not (low <= open_price <= high and low <= close <= high):
            continue
        seen.add(stamp)
        bar = {
            "time": stamp,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
        adjusted_close = _value(record, "adjusted_close", "AdjustedClose", default=None)
        try:
            adjusted = float(adjusted_close)
            factor = adjusted / close
            if math.isfinite(adjusted) and adjusted > 0 and math.isfinite(factor) and factor > 0:
                bar["adjusted_close"] = adjusted
                bar["adjustment_factor"] = factor
        except (TypeError, ValueError, OverflowError, ZeroDivisionError):
            pass
        bars.append(bar)
    return sorted(bars, key=lambda bar: bar["time"])


class VndirectProvider:
    name = "vndirect"
    universe_url = "https://api-finfo.vndirect.com.vn/v4/stocks"
    industry_url = "https://api-finfo.vndirect.com.vn/v4/industry_classification"
    history_url = "https://dchart-api.vndirect.com.vn/dchart/history"
    financial_statements_url = "https://api-finfo.vndirect.com.vn/v4/financial_statements"
    financial_models_url = "https://api-finfo.vndirect.com.vn/v4/financial_models"
    company_profiles_url = "https://api-finfo.vndirect.com.vn/v4/company_profiles"
    events_url = "https://api-finfo.vndirect.com.vn/v4/events"

    def __init__(
        self,
        *,
        settings: VietnamMarketDataSettings | None = None,
        http_get: Callable[..., Any] = requests.get,
        rate_gate: RequestRateGate | None = None,
    ) -> None:
        self.settings = settings or VietnamMarketDataSettings.from_env()
        self.http_get = http_get
        self.rate_gate = rate_gate or _shared_vndirect_gate(self.settings.requests_per_minute)
        self._evidence_cache: dict[str, tuple[float, Any]] = {}
        self._evidence_cache_lock = threading.Lock()

    def _evidence_cache_get(self, key: str) -> Any | None:
        with self._evidence_cache_lock:
            cached = self._evidence_cache.get(key)
            if cached and cached[0] > time.monotonic():
                return cached[1]
            self._evidence_cache.pop(key, None)
        return None

    def _evidence_cache_set(self, key: str, value: Any, ttl_seconds: int) -> Any:
        with self._evidence_cache_lock:
            self._evidence_cache[key] = (time.monotonic() + max(1, ttl_seconds), value)
        return value

    def fetch_universe(self) -> list[VietnamSecurity]:
        sectors = self._fetch_sector_map()
        securities: list[VietnamSecurity] = []
        for security_type, asset_class in (("STOCK", "equity"), ("ETF", "etf")):
            page = 1
            while True:
                self.rate_gate.acquire()
                response = self.http_get(
                    self.universe_url,
                    params={
                        "q": f"type:{security_type}~floor:HOSE",
                        "size": 1000,
                        "page": page,
                    },
                    headers={"Accept": "application/json", "User-Agent": "DataVest-MarketData/1.0"},
                    timeout=self.settings.timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                for record in payload.get("data") or []:
                    symbol = str(record.get("code") or "").strip().upper()
                    exchange = str(record.get("floor") or "").strip().upper()
                    if not symbol or exchange != "HOSE":
                        continue
                    listed_date = _parse_date(record.get("listedDate"))
                    delisted_date = _parse_date(record.get("delistedDate"))
                    status = str(record.get("status") or "").strip().lower()
                    trading_status = {
                        "listed": "ACTIVE",
                        "active": "ACTIVE",
                        "trading": "ACTIVE",
                        "suspended": "SUSPENDED",
                        "delisted": "DELISTED",
                    }.get(status, status.upper() or "INACTIVE")
                    securities.append(VietnamSecurity(
                        symbol=symbol,
                        name=str(
                            record.get("companyName")
                            or record.get("shortName")
                            or record.get("companyNameEng")
                            or symbol
                        ).strip(),
                        exchange=exchange,
                        asset_class=asset_class,
                        sector=str(
                            record.get("industryName")
                            or record.get("sector")
                            or record.get("industry")
                            or sectors.get(symbol)
                            or ("ETF" if asset_class == "etf" else "")
                        ).strip(),
                        listed_date=listed_date,
                        delisted_date=delisted_date,
                        trading_status=trading_status,
                    ))
                total_pages = max(1, int(payload.get("totalPages") or 1))
                if page >= total_pages:
                    break
                page += 1
        return securities

    def _fetch_sector_map(self) -> dict[str, str]:
        sectors: dict[str, str] = {}
        levels: dict[str, int] = {}
        page = 1
        while True:
            self.rate_gate.acquire()
            response = self.http_get(
                self.industry_url,
                params={"size": 1000, "page": page},
                headers={"Accept": "application/json", "User-Agent": "DataVest-MarketData/1.0"},
                timeout=self.settings.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            for record in payload.get("data") or []:
                try:
                    level = int(record.get("industryLevel") or 0)
                except (TypeError, ValueError):
                    level = 0
                name = str(record.get("vietnameseName") or record.get("englishName") or "").strip()
                if not name:
                    continue
                for raw_symbol in str(record.get("codeList") or "").split(","):
                    symbol = raw_symbol.strip().upper()
                    if symbol and level >= levels.get(symbol, -1):
                        levels[symbol] = level
                        sectors[symbol] = name
            total_pages = max(1, int(payload.get("totalPages") or 1))
            if page >= total_pages:
                return sectors
            page += 1

    def fetch_ohlcv(
        self, symbol: str, timeframe: str, start: date, end: date, limit: int
    ) -> list[dict[str, Any]]:
        resolution, merge = {
            "1m": ("1", 1), "3m": ("3", 1), "5m": ("5", 1),
            "15m": ("15", 1), "30m": ("30", 1), "1H": ("60", 1),
            "4H": ("60", 4), "1D": ("D", 1),
        }.get(timeframe, ("", 1))
        if not resolution:
            return []
        self.rate_gate.acquire()
        response = self.http_get(
            self.history_url,
            params={
                "resolution": resolution,
                "symbol": symbol,
                "from": int(datetime.combine(start, day_time.min, tzinfo=VN_ZONE).timestamp()),
                "to": int(datetime.combine(end + timedelta(days=1), day_time.min, tzinfo=VN_ZONE).timestamp()),
            },
            headers={"Accept": "application/json", "User-Agent": "DataVest-MarketData/1.0"},
            timeout=self.settings.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if str(payload.get("s") or "").lower() != "ok":
            return []
        timestamps = payload.get("t") or []
        scale = 1.0 if symbol in {"VNINDEX", "VN30"} else 1000.0
        records: list[dict[str, Any]] = []
        for index, stamp in enumerate(timestamps):
            try:
                records.append({
                    "TradingDate": datetime.fromtimestamp(int(stamp), tz=VN_ZONE).strftime("%Y-%m-%d %H:%M:%S"),
                    "Open": float(_at(payload.get("o"), index)) * scale,
                    "High": float(_at(payload.get("h"), index)) * scale,
                    "Low": float(_at(payload.get("l"), index)) * scale,
                    "Close": float(_at(payload.get("c"), index)) * scale,
                    "Volume": _at(payload.get("v"), index, 0),
                })
            except (IndexError, TypeError, ValueError, OverflowError):
                continue
        bars = _normalize_bars(records)
        if merge > 1:
            bars = _resample(bars, merge)
        return bars[-limit:]

    def _fetch_paged(
        self, url: str, *, query: str = "", size: int = 1000, sort: str = ""
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1
        while True:
            self.rate_gate.acquire()
            params: dict[str, Any] = {"size": size, "page": page}
            if query:
                params["q"] = query
            if sort:
                params["sort"] = sort
            response = self.http_get(
                url,
                params=params,
                headers={"Accept": "application/json", "User-Agent": "DataVest-MarketData/1.0"},
                timeout=self.settings.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            rows.extend(record for record in (payload.get("data") or []) if isinstance(record, dict))
            total_pages = max(1, int(payload.get("totalPages") or 1))
            if page >= total_pages:
                return rows
            page += 1

    def fetch_financial_statements(self, symbol: str) -> list[dict[str, Any]]:
        canonical = str(symbol or "").strip().upper()
        cache_key = f"financial-statements:{canonical}"
        cached = self._evidence_cache_get(cache_key)
        if cached is not None:
            return cached
        models = self._evidence_cache_get("financial-models")
        if models is None:
            models = self._evidence_cache_set(
                "financial-models", self._fetch_paged(self.financial_models_url), 86_400
            )
        labels: dict[tuple[str, str], dict[str, Any]] = {}
        for model in models:
            item_code = _item_code(model.get("itemCode"))
            model_type = str(model.get("modelType") or "").strip()
            if item_code:
                labels[(item_code, model_type)] = model
                labels.setdefault((item_code, ""), model)

        records = self._fetch_paged(
            self.financial_statements_url,
            query=f"code:{canonical}",
            sort="fiscalDate:desc,modifiedDate:desc",
        )
        result: list[dict[str, Any]] = []
        for record in records:
            item_code = _item_code(record.get("itemCode"))
            period_end = _parse_date(record.get("fiscalDate"))
            available_at = _iso_utc(record.get("createdDate") or record.get("modifiedDate"))
            try:
                value = float(record.get("numericValue"))
            except (TypeError, ValueError, OverflowError):
                continue
            if not item_code or period_end is None or available_at is None or not math.isfinite(value):
                continue
            model_type = str(record.get("modelType") or "").strip()
            model = labels.get((item_code, model_type)) or labels.get((item_code, "")) or {}
            label = str(
                model.get("itemVnName")
                or model.get("itemEnName")
                or model.get("modelVnDesc")
                or model.get("vietnameseName")
                or model.get("englishName")
                or model.get("modelTypeName")
                or item_code
            ).strip()
            result.append({
                "symbol": canonical,
                "metric": _canonical_financial_metric(label, item_code),
                "itemCode": item_code,
                "label": label,
                "value": value,
                "unit": "VND",
                "periodEnd": period_end.isoformat(),
                "availableAt": available_at,
                "revisionAt": _iso_utc(record.get("modifiedDate")),
                "frequency": _report_frequency(record.get("reportType")),
                "reportScope": _report_scope(
                    record.get("reportType"), record.get("modelType"), model.get("formType")
                ),
                "modelType": model_type,
                "source": self.name,
                "sourceUrl": self.financial_statements_url,
            })
        return self._evidence_cache_set(cache_key, result, 900)

    def fetch_company_profile(self, symbol: str) -> dict[str, Any]:
        canonical = str(symbol or "").strip().upper()
        cache_key = f"company-profile:{canonical}"
        cached = self._evidence_cache_get(cache_key)
        if cached is not None:
            return cached
        records = self._fetch_paged(self.company_profiles_url, query=f"code:{canonical}", size=10)
        record = next((item for item in records if str(item.get("code") or "").upper() == canonical), None)
        if not record:
            return self._evidence_cache_set(cache_key, {}, 900)
        try:
            shares = float(record.get("numOfShares"))
            if not math.isfinite(shares) or shares <= 0:
                shares = None
        except (TypeError, ValueError, OverflowError):
            shares = None
        return self._evidence_cache_set(cache_key, {
            "symbol": canonical,
            "name": str(record.get("companyName") or record.get("shortName") or canonical).strip(),
            "shortName": str(record.get("shortName") or "").strip(),
            "exchange": "HOSE",
            "assetClass": str(record.get("type") or "equity").strip().lower(),
            "sector": str(record.get("industryName") or record.get("industry") or "").strip(),
            "listedDate": (_parse_date(record.get("listedDate")) or "").isoformat()
            if _parse_date(record.get("listedDate")) else None,
            "website": str(record.get("website") or "").strip(),
            "sharesOutstanding": shares,
            "source": self.name,
            "sourceUrl": self.company_profiles_url,
        }, 86_400)

    def fetch_events(self, symbol: str) -> list[dict[str, Any]]:
        canonical = str(symbol or "").strip().upper()
        cache_key = f"events:{canonical}"
        cached = self._evidence_cache_get(cache_key)
        if cached is not None:
            return cached
        records = self._fetch_paged(
            self.events_url,
            query=f"code:{canonical}",
            sort="disclosureDate:desc",
        )
        result: list[dict[str, Any]] = []
        corporate_tokens = ("DIVIDEND", "RIGHT", "ISSUE", "SPLIT", "SHARE", "AGM")
        for record in records:
            available_at = _iso_utc(record.get("disclosureDate"))
            if available_at is None:
                continue
            group = str(record.get("group") or "").strip().upper()
            event_type = str(record.get("type") or "").strip().upper()
            category = (
                "corporateAction"
                if any(token in f"{group} {event_type}" for token in corporate_tokens)
                else "disclosure"
            )
            result.append({
                "id": str(record.get("id") or f"{canonical}:{event_type}:{available_at}"),
                "symbol": canonical,
                "category": category,
                "group": group,
                "type": event_type,
                "title": str(record.get("typeDesc") or event_type or group).strip(),
                "note": str(record.get("note") or "").strip(),
                "availableAt": available_at,
                "effectiveDate": (_parse_date(record.get("effectiveDate")) or "").isoformat()
                if _parse_date(record.get("effectiveDate")) else None,
                "actualDate": (_parse_date(record.get("actualDate")) or "").isoformat()
                if _parse_date(record.get("actualDate")) else None,
                "source": self.name,
                "sourceUrl": self.events_url,
            })
        return self._evidence_cache_set(cache_key, result, 300)


class YahooVietnamProvider:
    name = "yahoo-vn"

    def __init__(self, *, timeout_seconds: int = 10, rate_gate: RequestRateGate | None = None) -> None:
        self.timeout_seconds = max(1, int(timeout_seconds))
        self.rate_gate = rate_gate or _YAHOO_PROVIDER_GATE

    def fetch_ohlcv(
        self, symbol: str, timeframe: str, start: date, end: date, limit: int
    ) -> list[dict[str, Any]]:
        interval, merge = {
            "1m": ("1m", 1), "3m": ("1m", 3), "5m": ("5m", 1),
            "15m": ("15m", 1), "30m": ("30m", 1), "1H": ("60m", 1),
            "4H": ("60m", 4), "1D": ("1d", 1),
        }.get(timeframe, ("", 1))
        if not interval:
            return []
        self.rate_gate.acquire()
        max_history_days = {
            "1m": 7, "3m": 7, "5m": 59, "15m": 59, "30m": 59,
            "1H": 729, "4H": 729,
        }.get(timeframe)
        effective_start = max(start, end - timedelta(days=max_history_days)) if max_history_days else start
        start_dt = datetime.combine(effective_start, day_time.min, tzinfo=VN_ZONE)
        end_dt = datetime.combine(end + timedelta(days=1), day_time.min, tzinfo=VN_ZONE)
        yahoo_symbol = f"^{symbol}" if symbol in {"VNINDEX", "VN30"} else f"{symbol}.VN"
        response = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}",
            params={
                "period1": int(start_dt.timestamp()), "period2": int(end_dt.timestamp()),
                "interval": interval, "includePrePost": "false", "events": "history",
            },
            headers={"Accept": "application/json", "User-Agent": "DataVest-MarketData/1.0"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        result = (((response.json().get("chart") or {}).get("result") or [None])[0])
        if not result:
            return []
        quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
        adjusted = ((result.get("indicators") or {}).get("adjclose") or [{}])[0]
        records = []
        for index, stamp in enumerate(result.get("timestamp") or []):
            records.append({
                "TradingDate": datetime.fromtimestamp(int(stamp), tz=VN_ZONE).strftime("%Y-%m-%d %H:%M:%S"),
                "Open": _at(quote.get("open"), index), "High": _at(quote.get("high"), index),
                "Low": _at(quote.get("low"), index), "Close": _at(quote.get("close"), index),
                "Volume": _at(quote.get("volume"), index, 0),
                "AdjustedClose": _at(adjusted.get("adjclose"), index),
            })
        bars = _normalize_bars(records)
        if timeframe == "1D":
            bars = [bar for bar in bars if float(bar.get("volume") or 0.0) > 0]
        if merge > 1:
            bars = _resample(bars, merge)
        return bars[-limit:]


def _at(values: Any, index: int, default: Any = None) -> Any:
    try:
        return values[index]
    except (IndexError, TypeError):
        return default


def _resample(bars: list[dict[str, Any]], size: int) -> list[dict[str, Any]]:
    result = []
    by_day: dict[date, list[dict[str, Any]]] = {}
    for bar in bars:
        trading_day = datetime.fromtimestamp(int(bar["time"]), tz=VN_ZONE).date()
        by_day.setdefault(trading_day, []).append(bar)
    for day_bars in by_day.values():
        for index in range(0, len(day_bars), size):
            chunk = day_bars[index:index + size]
            if len(chunk) < size:
                continue
            result.append({
                "time": chunk[0]["time"], "open": chunk[0]["open"],
                "high": max(bar["high"] for bar in chunk), "low": min(bar["low"] for bar in chunk),
                "close": chunk[-1]["close"], "volume": sum(bar["volume"] for bar in chunk),
            })
    return result


__all__ = [
    "RequestRateGate", "VndirectProvider", "VietnamMarketDataSettings",
    "VietnamPriceProvider", "VietnamSecurity", "YahooVietnamProvider",
]
