"""Research-only dashboard summary."""

from __future__ import annotations

from flask import g, jsonify

from app.openapi.blueprint import HumanBlueprint as Blueprint
from app.utils.auth import login_required
from app.utils.db import get_db_connection
from app.utils.logger import get_logger

logger = get_logger(__name__)
dashboard_blp = Blueprint("dashboard", __name__)


def _count(cur, table: str, user_id: int) -> int:
    cur.execute(f"SELECT COUNT(1) AS cnt FROM {table} WHERE user_id = ?", (user_id,))
    return int((cur.fetchone() or {}).get("cnt") or 0)


@dashboard_blp.route("/summary", methods=["GET"])
@login_required
def summary():
    """Return research, authoring, backtest, and manual-paper counts."""
    try:
        user_id = int(g.user_id)
        with get_db_connection() as db:
            cur = db.cursor()
            try:
                data = {
                    "strategy_source_count": _count(cur, "qd_script_sources", user_id),
                    "indicator_count": _count(cur, "qd_indicator_codes", user_id),
                    "backtest_count": _count(cur, "qd_backtest_runs", user_id),
                    "factor_research_count": _count(cur, "qd_factor_research_runs", user_id),
                    "manual_position_count": _count(cur, "qd_manual_positions", user_id),
                }
            finally:
                cur.close()
        return jsonify({"code": 1, "msg": "success", "data": data})
    except Exception as exc:
        logger.error("dashboard summary failed: %s", exc, exc_info=True)
        return jsonify({"code": 0, "msg": str(exc), "data": None}), 500


# openapi-compat: legacy import name
dashboard_bp = dashboard_blp
