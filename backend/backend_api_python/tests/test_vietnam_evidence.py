from datetime import datetime, timezone

from app.data_sources.vn_market_providers import VndirectProvider


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_evidence_repository_bridges_same_period_observations_to_strategy_fundamentals(monkeypatch):
    from app.services.vietnam_evidence import VietnamEvidenceRepository
    from app.utils import db as db_module

    executed = []

    class Cursor:
        def execute(self, query, params=()):
            executed.append((" ".join(query.split()), params))

        def close(self):
            return None

    class Database:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def cursor(self):
            return Cursor()

        def commit(self):
            return None

    monkeypatch.setattr(db_module, "get_db_connection", lambda: Database())
    base = {
        "periodEnd": "2025-12-31",
        "availableAt": "2026-03-30T02:00:00+00:00",
        "frequency": "ANNUAL",
        "reportScope": "CONSOLIDATED",
        "modelType": "CONSOLIDATED",
        "unit": "VND",
        "source": "vndirect",
        "sourceUrl": "https://example.test/statements",
        "revisionAt": None,
    }
    evidence = {
        "checksum": "evidence-checksum",
        "instrument": {"symbol": "FPT", "sharesOutstanding": 999_999},
        "price": {"price": 120_000},
        "fundamentals": {"observations": [
            {**base, "metric": "revenue", "itemCode": "REV", "label": "Revenue", "value": 100.0},
            {**base, "metric": "net_income", "itemCode": "NI", "label": "Income", "value": 10.0},
            {**base, "metric": "shareholder_equity", "itemCode": "EQ", "label": "Equity", "value": 80.0},
            {**base, "metric": "total_debt", "itemCode": "DEBT", "label": "Debt", "value": 40.0},
        ]},
        "corporateActions": [],
        "disclosures": [],
    }

    VietnamEvidenceRepository.persist(evidence)

    bridge = next(item for item in executed if "INSERT INTO qd_fundamental_snapshots" in item[0])
    params = bridge[1]
    assert params[0:6] == ("VNStock", "FPT", "2025-12-31", "2026-03-30", "annual", "VND")
    assert params[6:11] == (100.0, 10.0, None, 80.0, 40.0)
    assert params[12] is None  # shares_outstanding must not use the current company profile
    assert params[13] is None  # market_cap must not use the current price
    assert params[16] == 0.125
    assert params[18] == 0.5


def test_vndirect_normalizes_point_in_time_financial_observations():
    def get(url, **kwargs):
        if url.endswith("/financial_models"):
            return Response({
                "data": [{
                    "itemCode": "ISA1",
                    "modelType": "1",
                    "modelTypeName": "Income Statement",
                    "modelVnDesc": "Doanh thu thuần",
                    "formType": "CONSOLIDATED",
                }],
                "totalPages": 1,
            })
        assert url.endswith("/financial_statements")
        return Response({
            "data": [{
                "code": "FPT",
                "itemCode": "ISA1",
                "reportType": "QUARTER",
                "modelType": "CONSOLIDATED",
                "numericValue": 123_000_000_000,
                "fiscalDate": "2026-06-30",
                "createdDate": "2026-07-29T08:30:00+07:00",
                "modifiedDate": "2026-08-01T09:15:00+07:00",
            }],
            "totalPages": 1,
        })

    rows = VndirectProvider(http_get=get).fetch_financial_statements("FPT")

    assert rows == [{
        "symbol": "FPT",
        "metric": "revenue",
        "itemCode": "ISA1",
        "label": "Doanh thu thuần",
        "value": 123_000_000_000.0,
        "unit": "VND",
        "periodEnd": "2026-06-30",
        "availableAt": "2026-07-29T01:30:00+00:00",
        "revisionAt": "2026-08-01T02:15:00+00:00",
        "frequency": "QUARTERLY",
        "reportScope": "CONSOLIDATED",
        "modelType": "CONSOLIDATED",
        "source": "vndirect",
        "sourceUrl": "https://api-finfo.vndirect.com.vn/v4/financial_statements",
    }]


def test_vndirect_normalizes_profile_events_and_disclosures():
    def get(url, **kwargs):
        if url.endswith("/company_profiles"):
            return Response({"data": [{
                "code": "FPT",
                "companyName": "Công ty Cổ phần FPT",
                "shortName": "FPT",
                "industryName": "Công nghệ",
                "listedDate": "2006-12-13",
                "numOfShares": 1_470_000_000,
                "website": "https://fpt.com",
            }], "totalPages": 1})
        assert url.endswith("/events")
        return Response({"data": [
            {
                "id": 77,
                "code": "FPT",
                "group": "DIVIDEND",
                "type": "CASH_DIVIDEND",
                "typeDesc": "Trả cổ tức bằng tiền",
                "note": "Tỷ lệ 10%",
                "disclosureDate": "2026-08-05T09:00:00+07:00",
                "effectiveDate": "2026-08-20",
                "actualDate": "2026-09-01",
            },
            {
                "id": 78,
                "code": "FPT",
                "group": "DISCLOSURE",
                "type": "FINANCIAL_REPORT",
                "typeDesc": "Công bố BCTC",
                "disclosureDate": "2026-08-10T15:00:00+07:00",
            },
        ], "totalPages": 1})

    provider = VndirectProvider(http_get=get)
    profile = provider.fetch_company_profile("FPT")
    events = provider.fetch_events("FPT")

    assert profile["sharesOutstanding"] == 1_470_000_000.0
    assert profile["sector"] == "Công nghệ"
    assert profile["source"] == "vndirect"
    assert events[0]["category"] == "corporateAction"
    assert events[0]["availableAt"] == "2026-08-05T02:00:00+00:00"
    assert events[1]["category"] == "disclosure"
    assert events[1]["availableAt"] == "2026-08-10T08:00:00+00:00"


def test_vndirect_maps_live_numeric_item_codes_using_item_names():
    statement_params = []

    def get(url, **kwargs):
        if url.endswith("/financial_models"):
            return Response({"data": [
                {
                    "itemCode": 21001.0,
                    "modelType": 12.0,
                    "modelVnDesc": "Báo cáo kết quả kinh doanh",
                    "itemVnName": "Doanh thu thuần",
                    "itemEnName": "Net Sales",
                    "formType": "WEB",
                    "companyForm": "NON_FINANCE",
                },
                {
                    "itemCode": 700087.0,
                    "modelType": 2.0,
                    "modelVnDesc": "Báo cáo kết quả kinh doanh",
                    "itemVnName": "Lãi suy giảm trên cổ phiếu",
                    "itemEnName": "EPS_diluted",
                    "formType": "ALL",
                    "companyForm": "NON_FINANCE",
                },
            ], "totalPages": 1})
        statement_params.append(kwargs["params"])
        return Response({"data": [
            {
                "code": "FPT", "itemCode": 21001.0, "reportType": "QUARTER", "modelType": 1.0,
                "numericValue": 123.0, "fiscalDate": "2026-06-30",
                "createdDate": "2026-07-29 08:30:00", "modifiedDate": "2026-07-29 08:30:00",
            },
            {
                "code": "FPT", "itemCode": 700087.0, "reportType": "YEAR", "modelType": 2.0,
                "numericValue": 5.0, "fiscalDate": "2025-12-31",
                "createdDate": "2026-01-29 08:30:00", "modifiedDate": "2026-01-29 08:30:00",
            },
        ], "totalPages": 1})

    provider = VndirectProvider(http_get=get)
    rows = provider.fetch_financial_statements("FPT")
    cached_rows = provider.fetch_financial_statements("FPT")

    assert rows[0]["itemCode"] == "21001"
    assert rows[0]["label"] == "Doanh thu thuần"
    assert rows[0]["metric"] == "revenue"
    assert rows[0]["reportScope"] == "UNKNOWN"
    assert rows[1]["itemCode"] == "700087"
    assert rows[1]["metric"] == "earnings_per_share"
    assert cached_rows == rows
    assert statement_params == [{
        "size": 1000,
        "page": 1,
        "q": "code:FPT",
        "sort": "fiscalDate:desc,modifiedDate:desc",
    }]


def test_vietnam_evidence_is_point_in_time_and_exposes_explicit_gaps():
    from app.services.vietnam_evidence import VietnamEvidenceService

    class Provider:
        name = "vndirect"

        def fetch_company_profile(self, symbol):
            return {
                "symbol": symbol,
                "name": "Công ty Cổ phần FPT",
                "exchange": "HOSE",
                "assetClass": "equity",
                "sector": "Công nghệ",
                "sharesOutstanding": 10.0,
                "source": "vndirect",
                "sourceUrl": "https://api-finfo.vndirect.com.vn/v4/company_profiles",
            }

        def fetch_financial_statements(self, symbol):
            base = {
                "symbol": symbol,
                "unit": "VND",
                "frequency": "ANNUAL",
                "reportScope": "CONSOLIDATED",
                "modelType": "CONSOLIDATED",
                "source": "vndirect",
                "sourceUrl": "https://api-finfo.vndirect.com.vn/v4/financial_statements",
            }
            return [
                {**base, "metric": "revenue", "itemCode": "REV", "label": "Doanh thu thuần", "value": 80.0,
                 "periodEnd": "2024-12-31", "availableAt": "2025-03-30T02:00:00+00:00", "revisionAt": None},
                {**base, "metric": "revenue", "itemCode": "REV", "label": "Doanh thu thuần", "value": 100.0,
                 "periodEnd": "2025-12-31", "availableAt": "2026-03-30T02:00:00+00:00", "revisionAt": None},
                {**base, "metric": "net_income", "itemCode": "NI", "label": "Lợi nhuận sau thuế", "value": 10.0,
                 "periodEnd": "2025-12-31", "availableAt": "2026-03-30T02:00:00+00:00", "revisionAt": None},
                {**base, "metric": "shareholder_equity", "itemCode": "EQ", "label": "Vốn chủ sở hữu", "value": 80.0,
                 "periodEnd": "2025-12-31", "availableAt": "2026-03-30T02:00:00+00:00", "revisionAt": None},
                {**base, "metric": "total_debt", "itemCode": "DEBT", "label": "Tổng nợ", "value": 40.0,
                 "periodEnd": "2025-12-31", "availableAt": "2026-03-30T02:00:00+00:00", "revisionAt": None},
                {**base, "metric": "revenue", "itemCode": "REV", "label": "Doanh thu thuần", "value": 999.0,
                 "periodEnd": "2026-06-30", "availableAt": "2026-10-01T02:00:00+00:00", "revisionAt": None},
                {**base, "metric": "revenue", "itemCode": "REV", "label": "Doanh thu thuần", "value": 777.0,
                 "periodEnd": "2026-12-31", "availableAt": "2026-08-01T02:00:00+00:00", "revisionAt": None},
            ]

        def fetch_events(self, symbol):
            return [{
                "id": "77", "symbol": symbol, "category": "corporateAction", "group": "DIVIDEND",
                "type": "CASH_DIVIDEND", "title": "Trả cổ tức", "note": "10%",
                "availableAt": "2026-08-05T02:00:00+00:00", "effectiveDate": "2026-08-20",
                "actualDate": "2026-09-01", "source": "vndirect",
                "sourceUrl": "https://api-finfo.vndirect.com.vn/v4/events",
            }]

    persisted = []
    service = VietnamEvidenceService(
        provider=Provider(),
        instrument_loader=lambda symbol: {
            "symbol": symbol, "name": "FPT", "exchange": "HOSE", "asset_class": "equity",
            "sector": "Công nghệ", "trading_status": "ACTIVE", "source": "vndirect",
        },
        market_context_loader=lambda: {"benchmarks": {"VNINDEX": {"price": 1300.0}}},
        persist=lambda evidence: persisted.append(evidence),
    )

    evidence = service.build(
        symbol="FPT",
        price={"price": 20.0, "source": "vndirect"},
        technical={"rsi": 55.0},
        as_of=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )

    observations = evidence["fundamentals"]["observations"]
    metrics = evidence["fundamentals"]["derivedMetrics"]
    assert all(row["value"] not in {777.0, 999.0} for row in observations)
    assert {row["reportScope"] for row in observations} == {"CONSOLIDATED"}
    assert metrics["revenue"] == 100.0
    assert metrics["revenue_growth"] == 25.0
    assert metrics["return_on_equity"] == 12.5
    assert metrics["debt_to_equity"] == 0.5
    assert metrics["pe_ratio"] == 20.0
    assert metrics["pb_ratio"] == 2.5
    assert metrics["ratioUnit"] == "PERCENTAGE_POINTS"
    assert evidence["corporateActions"][0]["id"] == "77"
    assert evidence["marketContext"]["benchmarks"]["VNINDEX"]["price"] == 1300.0
    assert {gap["field"] for gap in evidence["dataGaps"]} >= {"foreignRoom", "ownershipStructure"}
    assert evidence["sources"][0]["provider"] == "vndirect"
    assert evidence["provenance"]["price"]["latencyClass"] == "unknown"
    assert evidence["provenance"]["coverage"]["fundamentals"]["status"] == "available"
    assert evidence["provenance"]["coverage"]["news"]["status"] == "not_requested"
    assert len(evidence["checksum"]) == 64
    assert persisted == [evidence]


def test_vietnam_evidence_reports_unknown_financial_statement_scope_as_a_gap():
    from app.services.vietnam_evidence import VietnamEvidenceService

    class Provider:
        def fetch_company_profile(self, symbol):
            return {"symbol": symbol, "sharesOutstanding": 1, "source": "vndirect", "sourceUrl": "https://example.com/profile"}

        def fetch_financial_statements(self, symbol):
            return [{
                "symbol": symbol, "metric": "revenue", "itemCode": "21001", "label": "Doanh thu thuần",
                "value": 1.0, "unit": "VND", "periodEnd": "2025-12-31",
                "availableAt": "2026-03-30T02:00:00+00:00", "revisionAt": None,
                "frequency": "ANNUAL", "reportScope": "UNKNOWN", "modelType": "1",
                "source": "vndirect", "sourceUrl": "https://example.com/statements",
            }]

        def fetch_events(self, symbol):
            return []

    evidence = VietnamEvidenceService(
        provider=Provider(),
        instrument_loader=lambda symbol: {"symbol": symbol, "trading_status": "ACTIVE"},
        market_context_loader=lambda: {},
        persist=lambda evidence: None,
    ).build(symbol="FPT", price={"price": 1}, technical={}, as_of=datetime(2026, 9, 1, tzinfo=timezone.utc))

    assert {gap["field"] for gap in evidence["dataGaps"]} >= {"reportScope"}


def test_vietnam_evidence_derives_pe_from_annual_eps_without_share_count():
    from app.services.vietnam_evidence import VietnamEvidenceService

    class Provider:
        def fetch_company_profile(self, symbol):
            return {"symbol": symbol, "source": "vndirect", "sourceUrl": "https://example.com/profile"}

        def fetch_financial_statements(self, symbol):
            base = {
                "symbol": symbol, "metric": "earnings_per_share", "itemCode": "700087", "label": "EPS",
                "unit": "VND", "periodEnd": "2025-12-31",
                "availableAt": "2026-01-29T01:30:00+00:00", "revisionAt": None,
                "frequency": "ANNUAL", "reportScope": "UNKNOWN", "modelType": "2",
                "source": "vndirect", "sourceUrl": "https://example.com/statements",
            }
            return [{**base, "value": 0.0}, {**base, "value": 5.0}]

        def fetch_events(self, symbol):
            return []

    evidence = VietnamEvidenceService(
        provider=Provider(),
        instrument_loader=lambda symbol: {"symbol": symbol, "trading_status": "ACTIVE"},
        market_context_loader=lambda: {},
        persist=lambda evidence: None,
    ).build(symbol="FPT", price={"price": 100.0}, technical={}, as_of=datetime(2026, 9, 1, tzinfo=timezone.utc))

    assert evidence["fundamentals"]["derivedMetrics"]["pe_ratio"] == 20.0
    assert {gap["field"] for gap in evidence["dataGaps"]} >= {"pbRatio"}


def test_market_data_collector_attaches_vietnam_evidence_to_legacy_fast_analysis_shape(monkeypatch):
    from app.services.market_data_collector import MarketDataCollector

    evidence = {
        "checksum": "a" * 64,
        "instrument": {"symbol": "FPT", "name": "FPT", "exchange": "HOSE"},
        "fundamentals": {
            "observations": [{"metric": "revenue", "value": 100.0}],
            "derivedMetrics": {
                "pe_ratio": 20.0,
                "return_on_equity": 18.0,
                "revenue_growth": 12.0,
            },
        },
        "corporateActions": [{"id": "77"}],
        "disclosures": [{"id": "78"}],
        "marketContext": {"benchmarks": {"VNINDEX": {"price": 1300.0}}},
        "dataGaps": [{"field": "foreignRoom", "reason": "NO_VERIFIED_FREE_SOURCE"}],
        "sources": [{"provider": "vndirect", "url": "https://api-finfo.vndirect.com.vn/v4/financial_statements"}],
    }
    collector = object.__new__(MarketDataCollector)
    collector._get_price = lambda market, symbol: {"price": 120_000.0, "source": "vndirect"}
    collector._get_kline = lambda market, symbol, timeframe, limit: [
        {"time": index, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1.0}
        for index in range(60)
    ]
    collector._calculate_indicators = lambda bars: {"rsi": 55.0}
    collector._get_vietnam_evidence = lambda symbol, data: evidence
    collector._get_macro_data = lambda market, timeout=10: {}
    collector._get_news = lambda market, symbol, company_name=None, timeout=8: {"news": [], "sentiment": {}}

    result = collector.collect_all("VNStock", "FPT", include_macro=False, include_news=False)

    assert result["vietnam_evidence"] is evidence
    assert result["fundamental"]["pe_ratio"] == 20.0
    assert result["fundamental"]["financial_statements"]["observations"][0]["metric"] == "revenue"
    assert result["company"]["exchange"] == "HOSE"
    assert result["corporate_actions"] == [{"id": "77"}]
    assert result["disclosures"] == [{"id": "78"}]
    assert result["market_context"]["benchmarks"]["VNINDEX"]["price"] == 1300.0
    assert "vietnam_evidence" in result["_meta"]["success_items"]


def test_fast_analysis_provenance_includes_vietnam_evidence_sources_and_gaps():
    from app.services.fast_analysis import FastAnalysisService

    service = object.__new__(FastAnalysisService)
    provenance = service._build_input_provenance(
        {
            "price": {"price": 120_000.0, "source": "vndirect"},
            "kline": [{"time": 123, "close": 120_000.0}],
            "vietnam_evidence": {
                "checksum": "b" * 64,
                "fundamentals": {"observations": [{"metric": "revenue", "value": 1.0}]},
                "corporateActions": [{"id": "77"}],
                "disclosures": [{"id": "78"}],
                "dataGaps": [{"field": "foreignRoom", "reason": "NO_VERIFIED_FREE_SOURCE"}],
                "sources": [{"provider": "vndirect", "url": "https://api-finfo.vndirect.com.vn/v4/events"}],
            },
            "_meta": {"success_items": ["vietnam_evidence"]},
        },
        timeframe="1D",
        captured_at="2026-09-01T00:00:00Z",
    )

    assert provenance["evidence_checksum"] == "b" * 64
    assert provenance["provider_sources"] == ["vndirect"]
    assert set(provenance["components"]) >= {"technical", "fundamentals", "corporate_actions", "disclosures"}
    assert provenance["data_gaps"] == [{"field": "foreignRoom", "reason": "NO_VERIFIED_FREE_SOURCE"}]


def test_ai_chat_consumes_shared_vietnam_evidence_for_inferred_hose_symbol(monkeypatch):
    from app.routes import ai_chat

    evidence = {
        "instrument": {"market": "VNStock", "symbol": "FPT", "exchange": "HOSE"},
        "fundamentals": {"observations": [{"metric": "revenue", "value": 100.0}],
                         "derivedMetrics": {"pe_ratio": 20.0}},
        "corporateActions": [],
        "disclosures": [],
        "marketContext": {"benchmarks": {"VNINDEX": {"price": 1300.0}}},
        "dataGaps": [{"field": "foreignRoom", "reason": "NO_VERIFIED_FREE_SOURCE"}],
        "sources": [{"provider": "vndirect", "url": "https://api-finfo.vndirect.com.vn/v4/financial_statements"}],
        "checksum": "c" * 64,
    }

    class Service:
        def build(self, **kwargs):
            assert kwargs["symbol"] == "FPT"
            assert kwargs["price"]["price"] == 120_000.0
            return evidence

    validated = []
    monkeypatch.setattr(ai_chat, "_local_symbol_candidates", lambda message: [
        {"market": "VNStock", "symbol": "FPT", "name": "FPT", "match": "FPT", "source": "local_symbol_db"}
    ])
    monkeypatch.setattr(ai_chat, "_search_intelligence", lambda *args, **kwargs: {
        "web_results": [], "news_results": [], "search_queries": [], "language": "vi-VN"
    })
    monkeypatch.setattr(ai_chat, "_snapshot_for_candidate", lambda candidate: {
        "market": "VNStock", "symbol": "FPT",
        "price": {"last": 120_000.0, "source": "vndirect"},
        "timeframes": {"1D": {"rsi14": 55.0}},
    })
    monkeypatch.setattr(ai_chat, "_research_skill_plan", lambda *args, **kwargs: [])
    monkeypatch.setattr(ai_chat, "validate_hose_ai_target", lambda market, symbol: validated.append((market, symbol)) or "FPT")
    monkeypatch.setattr(ai_chat, "get_vietnam_evidence_service", lambda: Service(), raising=False)

    context = ai_chat._build_research_context({
        "user_message": "valuation FPT",
        "intent": "market_analysis",
        "language": "vi-VN",
    })

    assert validated == [("VNStock", "FPT")]
    assert context["vietnamEvidence"] is evidence
    assert context["fundamentals"]["derivedMetrics"]["pe_ratio"] == 20.0
    assert {gap["field"] for gap in context["data_gaps"]} == {"foreignRoom"}


def test_ai_chat_rejects_inferred_inactive_vn_symbol_before_evidence_provider(monkeypatch):
    from app.routes import ai_chat

    provider_called = []
    monkeypatch.setattr(ai_chat, "_local_symbol_candidates", lambda message: [
        {"market": "VNStock", "symbol": "BAD", "name": "Bad", "match": "BAD", "source": "local_symbol_db"}
    ])
    monkeypatch.setattr(ai_chat, "_search_intelligence", lambda *args, **kwargs: {
        "web_results": [], "news_results": [], "search_queries": [], "language": "vi-VN"
    })
    monkeypatch.setattr(ai_chat, "_snapshot_for_candidate", lambda candidate: provider_called.append("snapshot"))
    monkeypatch.setattr(ai_chat, "validate_hose_ai_target", lambda market, symbol: (_ for _ in ()).throw(
        ValueError("unsupported_or_inactive_vn_symbol")
    ))

    try:
        ai_chat._build_research_context({
            "user_message": "valuation BAD",
            "intent": "market_analysis",
            "language": "vi-VN",
        })
    except ValueError as exc:
        assert str(exc) == "unsupported_or_inactive_vn_symbol"
    else:
        raise AssertionError("inactive inferred VN symbol must be rejected")
    assert provider_called == []


def test_realtime_price_preserves_actual_ticker_provider(monkeypatch):
    from app.data_sources import DataSourceFactory
    from app.services.kline import KlineService

    class Cache:
        def get(self, key):
            return None

        def set(self, key, value, ttl):
            return None

    monkeypatch.setattr(DataSourceFactory, "get_ticker", lambda *args, **kwargs: {
        "last": 120_000.0,
        "change": 1_000.0,
        "changePercent": 0.84,
        "high": 121_000.0,
        "low": 118_000.0,
        "open": 119_000.0,
        "previousClose": 119_000.0,
        "provider": "vndirect",
    })
    service = object.__new__(KlineService)
    service.cache = Cache()

    quote = service.get_realtime_price("VNStock", "FPT", force_refresh=True)

    assert quote["source"] == "vndirect"
