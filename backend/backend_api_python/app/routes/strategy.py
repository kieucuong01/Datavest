"""Canonical strategy deployment and lifecycle routes."""

from __future__ import annotations

import re
from typing import Any

from flask import g, jsonify, request

from app.routes.strategy_blueprint import strategy_blp
from app.services.ai_generation_contracts import (
    SCRIPT_STRATEGY_REPAIR_REQUIREMENTS,
    SCRIPT_STRATEGY_SYSTEM_PROMPT,
)
from app.services.strategy_v2 import compile_strategy_v2
from app.utils.auth import login_required
from app.utils.logger import get_logger


logger = get_logger(__name__)

# Split route modules share this blueprint.
from app.routes import script_source_routes  # noqa: E402,F401
from app.routes import strategy_notifications  # noqa: E402,F401
from app.routes import strategy_review_routes  # noqa: E402,F401


def _ok(data: Any = None, message: str = "common.success"):
    return jsonify({"code": 1, "msg": message, "data": data})


def _error(message: str, status: int = 400, data: Any = None):
    return jsonify({"code": 0, "msg": message, "data": data}), status


@strategy_blp.route("/strategies/verify", methods=["POST"])
@login_required
def verify_strategy():
    code = str((request.get_json() or {}).get("code") or "").strip()
    if not code:
        return _error("strategyV2.codeRequired")
    try:
        program = compile_strategy_v2(code)
        return _ok({"valid": True, "manifest": program.manifest.metadata()})
    except Exception as exc:
        return _error("strategyV2.contractInvalid", data={"valid": False, "error": str(exc)})


@strategy_blp.route("/strategies/generate", methods=["POST"])
@login_required
def generate_strategy():
    payload = dict(request.get_json() or {})
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        return _error("strategyV2.promptRequired")
    try:
        from app.services.llm import LLMService

        llm = LLMService()
        if not llm.is_configured():
            return _error("strategyV2.llmNotConfigured")
        content = llm.call_llm_api(
            messages=[
                {"role": "system", "content": SCRIPT_STRATEGY_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            model=llm.get_code_generation_model(),
            temperature=0.4,
            use_json_mode=False,
        )
        code = _strip_code_fence(str(content or ""))
        code, program = _compile_or_repair_generated_strategy(llm, prompt, code)
        return _ok({"code": code, "manifest": program.manifest.metadata()})
    except Exception as exc:
        logger.warning("strategy generation failed: %s", exc)
        return _error("strategyV2.generationInvalid", data={"error": str(exc)})


def _strip_code_fence(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^```(?:python)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _compile_or_repair_generated_strategy(llm, prompt: str, code: str):
    try:
        return code, compile_strategy_v2(code)
    except Exception as first_error:
        logger.info("repairing invalid generated strategy: %s", first_error)
        repair_prompt = "\n\n".join(
            [
                SCRIPT_STRATEGY_REPAIR_REQUIREMENTS,
                f"Original user request:\n{prompt}",
                f"Validation error:\n{first_error}",
                f"Invalid generated source:\n{code}",
                "Repair the source and return the complete Python source only.",
            ]
        )
        repaired_content = llm.call_llm_api(
            messages=[
                {"role": "system", "content": SCRIPT_STRATEGY_SYSTEM_PROMPT},
                {"role": "user", "content": repair_prompt},
            ],
            model=llm.get_code_generation_model(),
            temperature=0.15,
            use_json_mode=False,
        )
        repaired_code = _strip_code_fence(str(repaired_content or ""))
        return repaired_code, compile_strategy_v2(repaired_code)
