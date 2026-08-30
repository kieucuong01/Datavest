"""Evidence-gated server-side explanations for Smart Insights."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence

from .evidence import build_live_explanation_context
from app.utils.language import language_instruction, normalize_product_language


Generate = Callable[..., str]


def _default_generate(*, quantitative_summary: Mapping[str, object], evidence: list[dict], locale: str) -> str:
    from app.services.llm import LLMService

    product_language = normalize_product_language(locale)
    language = "Vietnamese" if product_language == "vi-VN" else "English"
    messages = [
        {
            "role": "system",
            "content": (
                f"Explain the quantitative result in concise {language}. "
                "Use only the supplied validated evidence, cite source names, "
                "state uncertainty, and do not give guaranteed returns or direct trade orders. "
                + language_instruction(product_language)
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {"quantitativeSummary": quantitative_summary, "evidence": evidence},
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            ),
        },
    ]
    return str(
        LLMService().call_llm_api(
            messages,
            temperature=0.2,
            use_fallback=True,
            use_json_mode=False,
            try_alternative_providers=False,
        )
    ).strip()


class EvidenceGroundedExplainer:
    def __init__(self, generate: Generate | None = None) -> None:
        self.generate = generate or _default_generate

    def explain(
        self,
        *,
        quantitative_summary: Mapping[str, object],
        evidence: Sequence[Mapping[str, object]],
        locale: str,
    ) -> str:
        if locale not in {"vi", "vi-VN", "en", "en-US"}:
            raise ValueError("invalid_locale")
        context = build_live_explanation_context(evidence)
        return self.generate(
            quantitative_summary=dict(quantitative_summary),
            evidence=context,
            locale=locale,
        )


__all__ = ["EvidenceGroundedExplainer"]
