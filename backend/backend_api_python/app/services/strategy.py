"""Read-only strategy records used by backtests and post-trade research."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.utils.db import get_db_connection


_service: Optional["StrategyService"] = None


def get_strategy_service() -> "StrategyService":
    global _service
    if _service is None:
        _service = StrategyService()
    return _service


class StrategyService:
    """Tenant-scoped reads for legacy strategy records.

    Strategy authoring and CRUD live in the script-source service. This adapter
    remains only so retained backtest and strategy-review flows can resolve
    historical strategy-to-source links without exposing deployment controls.
    """

    def list_strategies(self, user_id: int = 1) -> List[Dict[str, Any]]:
        return self._query("user_id = ?", (int(user_id),))

    def get_strategy(
        self,
        strategy_id: int,
        user_id: int | None = None,
    ) -> Optional[Dict[str, Any]]:
        where = "id = ?"
        values: list[Any] = [int(strategy_id)]
        if user_id is not None:
            where += " AND user_id = ?"
            values.append(int(user_id))
        rows = self._query(where, tuple(values))
        return rows[0] if rows else None

    @staticmethod
    def _query(where: str, values: tuple[Any, ...]) -> List[Dict[str, Any]]:
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                f"SELECT * FROM qd_strategies_trading WHERE {where} ORDER BY id DESC",
                values,
            )
            rows = cur.fetchall() or []
            cur.close()
        output = []
        for row in rows:
            item = dict(row)
            for field in ("exchange_config", "trading_config", "notification_config"):
                item[field] = _json_object(item.get(field))
            output.append(item)
        return output


def _json_object(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return dict(parsed) if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}
