"""PostgreSQL persistence for immutable optimizer runs and paper rebalances."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from app.utils.db import get_db_connection

from .market_data import PriceSeries


def _json(value, fallback):
    if value is None:
        return fallback
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return fallback
    return value


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


class PortfolioOptimizerRepository:
    def create_run(
        self,
        *,
        user_id: int,
        request: dict[str, Any],
        input_snapshot: dict[str, Any],
        input_checksum: str,
        series: tuple[PriceSeries, ...],
        result: dict[str, Any],
    ) -> str:
        run_id = str(uuid4())
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                INSERT INTO optimizer_runs
                    (id, user_id, status, method, base_currency, request_json,
                     input_snapshot_json, input_checksum, result_json)
                VALUES (?, ?, 'SUCCEEDED', ?, ?, ?::jsonb, ?::jsonb, ?, ?::jsonb)
                """,
                (
                    run_id,
                    user_id,
                    request["method"],
                    request["baseCurrency"],
                    _dump(request),
                    _dump(input_snapshot),
                    input_checksum,
                    _dump(result),
                ),
            )
            for item in series:
                cur.execute(
                    """
                    INSERT INTO optimizer_input_series
                        (optimizer_run_id, market, symbol, currency, provider,
                         fallback_chain_json, coverage, checksum, data_class,
                         timestamps_json, closes_json)
                    VALUES (?, ?, ?, ?, ?, ?::jsonb, ?, ?, ?, ?::jsonb, ?::jsonb)
                    """,
                    (
                        run_id,
                        item.market,
                        item.symbol,
                        item.currency,
                        item.provider,
                        _dump(item.fallback_chain),
                        item.coverage,
                        item.checksum,
                        item.data_class,
                        _dump(item.timestamps),
                        _dump(item.closes),
                    ),
                )
            for allocation in result["allocations"]:
                cur.execute(
                    """
                    INSERT INTO optimizer_allocations
                        (optimizer_run_id, symbol, target_weight_bps)
                    VALUES (?, ?, ?)
                    """,
                    (run_id, allocation["symbol"], allocation["weightBps"]),
                )
            db.commit()
            cur.close()
        return run_id

    def get_run(self, *, run_id: str, user_id: int) -> dict[str, Any] | None:
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                SELECT id, user_id, status, request_json, input_snapshot_json,
                       input_checksum, result_json, created_at
                FROM optimizer_runs WHERE id = ? AND user_id = ?
                """,
                (run_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                cur.close()
                return None
            cur.execute(
                """
                SELECT market, symbol, currency, provider, fallback_chain_json,
                       coverage, checksum, data_class, timestamps_json, closes_json
                FROM optimizer_input_series
                WHERE optimizer_run_id = ? ORDER BY id
                """,
                (run_id,),
            )
            series_rows = cur.fetchall() or []
            cur.close()
        return {
            "id": str(row["id"]),
            "userId": int(row["user_id"]),
            "status": row["status"],
            "request": _json(row["request_json"], {}),
            "input_snapshot": _json(row["input_snapshot_json"], {}),
            "input_checksum": row["input_checksum"],
            "inputChecksum": row["input_checksum"],
            "result": _json(row["result_json"], {}),
            "series": [
                {
                    "market": item["market"],
                    "symbol": item["symbol"],
                    "currency": item["currency"],
                    "provider": item["provider"],
                    "fallbackChain": _json(item["fallback_chain_json"], []),
                    "coverage": float(item["coverage"]),
                    "checksum": item["checksum"],
                    "dataClass": item["data_class"],
                    "timestamps": _json(item["timestamps_json"], []),
                    "closes": _json(item["closes_json"], []),
                }
                for item in series_rows
            ],
            "createdAt": row["created_at"],
        }

    def list_managed_positions(self, *, user_id: int) -> list[dict[str, Any]]:
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                SELECT market, symbol, quantity
                FROM qd_manual_positions
                WHERE user_id = ? AND side = 'long' AND group_name = 'DataVest Optimizer'
                """,
                (user_id,),
            )
            rows = cur.fetchall() or []
            cur.close()
        return [
            {"market": row["market"], "symbol": row["symbol"], "quantity": float(row["quantity"])}
            for row in rows
        ]

    def create_plan(
        self,
        *,
        run_id: str,
        user_id: int,
        portfolio_value: float,
        input_checksum: str,
        orders: list[dict[str, Any]],
    ) -> dict[str, Any]:
        plan_id = str(uuid4())
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                INSERT INTO paper_rebalance_plans
                    (id, optimizer_run_id, user_id, status, portfolio_value,
                     input_checksum, proposal_json)
                VALUES (?, ?, ?, 'PREVIEW', ?, ?, ?::jsonb)
                """,
                (plan_id, run_id, user_id, portfolio_value, input_checksum, _dump({"orders": orders})),
            )
            db.commit()
            cur.close()
        return {"id": plan_id, "status": "PREVIEW"}

    def apply_plan(
        self,
        *,
        plan_id: str,
        run_id: str,
        user_id: int,
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                SELECT id, optimizer_run_id, status, proposal_json,
                       apply_idempotency_key, applied_result_json
                FROM paper_rebalance_plans
                WHERE id = ? AND optimizer_run_id = ? AND user_id = ?
                FOR UPDATE
                """,
                (plan_id, run_id, user_id),
            )
            plan = cur.fetchone()
            if not plan:
                cur.close()
                return None
            if plan["status"] == "APPLIED":
                if plan["apply_idempotency_key"] != idempotency_key:
                    raise ValueError("rebalance_plan_already_applied")
                result = _json(plan["applied_result_json"], {})
                db.commit()
                cur.close()
                return result
            cur.execute(
                """
                SELECT id, applied_result_json FROM paper_rebalance_plans
                WHERE user_id = ? AND apply_idempotency_key = ?
                """,
                (user_id, idempotency_key),
            )
            conflict = cur.fetchone()
            if conflict:
                raise ValueError("idempotency_key_conflict")
            orders = _json(plan["proposal_json"], {}).get("orders") or []
            if any(item.get("executionMode") != "SIMULATED" for item in orders):
                raise RuntimeError("paper_execution_boundary_violated")
            cur.execute(
                """
                DELETE FROM qd_manual_positions
                WHERE user_id = ? AND side = 'long' AND group_name = 'DataVest Optimizer'
                """,
                (user_id,),
            )
            transaction_ids = []
            for order in orders:
                target_quantity = float(order.get("targetQuantity") or order.get("quantity") or 0)
                if target_quantity > 0:
                    cur.execute(
                        """
                        INSERT INTO qd_manual_positions
                            (user_id, market, symbol, name, side, quantity, entry_price,
                             entry_time, notes, tags, group_name, created_at, updated_at)
                        VALUES (?, ?, ?, ?, 'long', ?, ?, EXTRACT(EPOCH FROM NOW())::BIGINT,
                                'Optimizer paper rebalance', '[]', 'DataVest Optimizer', NOW(), NOW())
                        """,
                        (
                            user_id,
                            order["market"],
                            order["symbol"],
                            order["symbol"],
                            target_quantity,
                            float(order["markPrice"]),
                        ),
                    )
                quantity = float(order.get("quantity") or 0)
                if quantity <= 0:
                    continue
                transaction_id = str(uuid4())
                transaction_ids.append(transaction_id)
                cur.execute(
                    """
                    INSERT INTO paper_portfolio_transactions
                        (id, user_id, paper_rebalance_plan_id, market, symbol, side,
                         quantity, price, notional, currency, execution_mode, idempotency_key)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SIMULATED', ?)
                    """,
                    (
                        transaction_id,
                        user_id,
                        plan_id,
                        order["market"],
                        order["symbol"],
                        order["side"],
                        quantity,
                        float(order["markPrice"]),
                        float(order["notional"]),
                        order["currency"],
                        idempotency_key,
                    ),
                )
            result = {
                "planId": plan_id,
                "status": "APPLIED",
                "executionMode": "SIMULATED",
                "transactionIds": transaction_ids,
            }
            cur.execute(
                """
                UPDATE paper_rebalance_plans
                SET status = 'APPLIED', apply_idempotency_key = ?,
                    applied_result_json = ?::jsonb, applied_at = NOW()
                WHERE id = ?
                """,
                (idempotency_key, _dump(result), plan_id),
            )
            db.commit()
            cur.close()
        return result


__all__ = ["PortfolioOptimizerRepository"]
