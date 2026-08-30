from scripts.generate_market_symbols_seed_sql import build_sql


def test_generated_seed_repairs_curated_etf_metadata_after_symbol_insert():
    sql = build_sql(
        [
            ("VNStock", "FPT", "FPT Corporation", "HOSE", "VND"),
            ("USStock", "SPY", "SPDR S&P 500 ETF Trust", "NYSE Arca", "USD"),
        ],
        [],
    )

    insert_end = sql.index("is_active = 1;")
    repair_start = sql.index("SET asset_class = 'etf', is_hot = 1")

    assert repair_start > insert_end
    assert "WHERE market = 'VNStock'" not in sql
    assert "WHERE market = 'USStock'" in sql
    assert "'SPY'" in sql
