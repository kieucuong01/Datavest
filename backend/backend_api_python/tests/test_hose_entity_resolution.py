"""HOSE entity resolution must be catalog-backed and ambiguity-aware."""

from app.services.hose_entity_resolution import resolve_hose_request


ROWS = {
    "ABC": [{"market": "VNStock", "symbol": "ABC", "name": "ABC Holdings", "exchange": "HOSE"}],
    "Hòa Phát": [{"market": "VNStock", "symbol": "HPG", "name": "Tập đoàn Hòa Phát", "exchange": "HOSE"}],
    "Ngân hàng": [
        {"market": "VNStock", "symbol": "ACB", "name": "Ngân hàng Á Châu", "exchange": "HOSE"},
        {"market": "VNStock", "symbol": "MBB", "name": "Ngân hàng Quân đội", "exchange": "HOSE"},
    ],
}


def _search(market, keyword, *, exchange):
    assert market == "VNStock" and exchange == "HOSE"
    return ROWS.get(keyword, [])


def _validate(market, symbol):
    if symbol == "BAD":
        raise ValueError("unsupported_or_inactive_vn_symbol")
    return symbol


def test_resolves_unlisted_hardcoded_ticker_from_master():
    result = resolve_hose_request("Phân tích ABC", {}, _search, _validate)
    assert result["status"] == "resolved"
    assert result["target"]["symbol"] == "ABC"


def test_resolves_vietnamese_name_and_selected_context():
    assert resolve_hose_request("Phân tích Hòa Phát", {}, _search, _validate)["target"]["symbol"] == "HPG"
    assert resolve_hose_request(
        "Phân tích thêm", {"market": "VNStock", "symbol": "ABC"}, _search, _validate
    )["target"]["symbol"] == "ABC"


def test_ambiguous_company_words_do_not_select_an_instrument():
    result = resolve_hose_request("Ngân hàng", {}, _search, _validate)
    assert result["status"] == "ambiguous"
    assert result["target"] is None
    assert {row["symbol"] for row in result["candidates"]} == {"ACB", "MBB"}


def test_inactive_result_is_not_resolved():
    def search(market, keyword, *, exchange):
        return [{"market": market, "symbol": "BAD", "name": "Bad", "exchange": exchange}] if keyword == "BAD" else []

    result = resolve_hose_request("HOSE: BAD", {}, search, _validate)
    assert result["status"] == "none"
    assert result["target"] is None
