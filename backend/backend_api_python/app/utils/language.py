"""
Language helpers (local-only).

We want AI analysis output language to follow the frontend UI language.
Frontend sends `X-App-Lang` (and also `Accept-Language`) on each request.
"""

from __future__ import annotations

from typing import Optional


PRODUCT_LANGS = {"en-US", "vi-VN"}
SUPPORTED_LANGS = PRODUCT_LANGS


def _normalize_lang(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    s = str(raw).strip().replace("_", "-")
    if not s:
        return None

    # Accept-Language can be like: "en-US,en;q=0.9"
    if "," in s:
        s = s.split(",", 1)[0].strip()
    if ";" in s:
        s = s.split(";", 1)[0].strip()

    # Normalize short tags
    lower = s.lower()
    if lower in ("en", "en-us"):
        return "en-US"
    if lower in ("vi", "vi-vn"):
        return "vi-VN"
    if lower in ("zh", "zh-cn", "zh-hans"):
        return "zh-CN"
    if lower in ("zh-tw", "zh-hant"):
        return "zh-TW"

    # Keep canonical casing if already supported
    for lang in SUPPORTED_LANGS:
        if lang.lower() == lower:
            return lang
    return None


def normalize_product_language(raw: Optional[str], default: str = "en-US") -> str:
    """Return one of the two languages exposed by the DataVest product."""
    normalized = _normalize_lang(raw)
    if normalized in PRODUCT_LANGS:
        return normalized
    return default if default in PRODUCT_LANGS else "en-US"


def language_instruction(language: Optional[str], *, structured: bool = False) -> str:
    """Build the mandatory language contract shared by every AI workflow."""
    normalized = normalize_product_language(language)
    field_note = (
        " Quy tắc này áp dụng cho toàn bộ nội dung người dùng nhìn thấy và mọi trường văn bản trong JSON, gồm tiêu đề, "
        "tóm tắt, lý do, rủi ro, cảnh báo, nhãn và hành động."
        if structured
        else " Quy tắc này áp dụng cho toàn bộ nội dung người dùng nhìn thấy."
    )
    if normalized == "vi-VN":
        return (
            "Bắt buộc trả lời hoàn toàn bằng tiếng Việt tự nhiên, đầy đủ dấu. "
            "Không viết văn xuôi bằng tiếng Anh hoặc tiếng Trung. Chỉ giữ nguyên mã cổ phiếu, "
            "tên riêng của nhà cung cấp/sản phẩm, thuật ngữ viết tắt chuẩn, mã nguồn và khóa JSON; "
            "nếu phải trích dẫn nguồn tiếng Anh hoặc tiếng Trung thì dịch ý ngay sang tiếng Việt."
            + field_note
        )
    return (
        "Reply entirely in clear English. Do not output Chinese or Vietnamese prose. "
        "Preserve ticker symbols, provider/product proper names, standard abbreviations, code, and JSON keys."
        + (" Apply this rule to every user-visible text field in JSON." if structured else " Apply this rule to all user-visible content.")
    )


def detect_request_language(flask_request, body: Optional[dict] = None, default: str = "en-US") -> str:
    """
    Detect language for the current request.

    Priority:
    1) Header X-App-Lang (frontend UI language)
    2) body["language"] or query ?language=
    3) Header Accept-Language
    """
    # 1) Custom header
    lang = _normalize_lang(flask_request.headers.get("X-App-Lang"))
    if lang:
        return normalize_product_language(lang, default)

    # 2) Explicit parameter
    if body and isinstance(body, dict):
        lang = _normalize_lang(body.get("language"))
        if lang:
            return normalize_product_language(lang, default)
    lang = _normalize_lang(flask_request.args.get("language"))
    if lang:
        return normalize_product_language(lang, default)

    # 3) Browser default
    lang = _normalize_lang(flask_request.headers.get("Accept-Language"))
    if lang:
        return normalize_product_language(lang, default)

    return normalize_product_language(default)


