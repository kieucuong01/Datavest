from scripts import refresh_public_universe_snapshots as snapshots


class _RowsCursor:
    def __init__(self, rows):
        self.rows = rows
        self.params = None
        self.executions = []

    def execute(self, sql, params=None):
        self.params = params
        self.executions.append((sql, params))

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class _RowsConnection:
    def __init__(self, rows):
        self.cursor_obj = _RowsCursor(rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        pass


def test_etf_snapshot_loader_reads_hot_symbol_master_rows(monkeypatch):
    connection = _RowsConnection([
        {"market": "USStock", "symbol": "spy", "name": "SPDR S&P 500 ETF"},
        {"market": "USStock", "symbol": "qqq", "name": "Invesco QQQ"},
    ])
    monkeypatch.setattr(snapshots, "get_db_connection", lambda: connection)

    rows = snapshots.symbol_master_etfs("USStock")

    assert connection.cursor_obj.params == ("USStock",)
    repair_sql, repair_params = connection.cursor_obj.executions[0]
    assert "SET asset_class = 'etf', is_hot = 1" in repair_sql
    assert repair_params[0] == "USStock"
    assert "SPY" in repair_params[1]
    assert [row["symbol"] for row in rows] == ["SPY", "QQQ"]
    assert rows[0]["rank"] == 1
    assert rows[0]["metadata"] == {"source": "symbol_master", "asset_class": "etf"}
    assert "hk_etf" not in snapshots.LOADERS
    assert "us_etf" in snapshots.LOADERS
