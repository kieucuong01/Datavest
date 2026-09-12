"""Translate AkShare economic-event labels once during the scheduled crawl.

AkShare's WallstreetCN adapter returns Chinese labels.  The browser must not
call DeepSeek directly, so the calendar worker enriches each snapshot with
``name_vi`` and ``name_en`` and keeps the result in a small local cache.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List

from app.services.llm import LLMProvider, LLMService
from app.utils.logger import get_logger

logger = get_logger(__name__)

CJK_PATTERN = re.compile(r"[\u3400-\u9fff]")
DEFAULT_CACHE_PATH = "data/economic-calendar/event-name-translations.json"
DEFAULT_BATCH_SIZE = 50

# Keep the common labels deterministic even when a deployment has no LLM key.
# DeepSeek fills the long tail and future provider-label changes.
STATIC_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "美国cpi年率": {"vi": "CPI Hoa Kỳ (theo năm)", "en": "US CPI (YoY)"},
    "美国cpi月率": {"vi": "CPI Hoa Kỳ (theo tháng)", "en": "US CPI (MoM)"},
    "美国非农就业数据": {"vi": "Việc làm phi nông nghiệp Hoa Kỳ", "en": "US Non-Farm Payrolls"},
    "美国初请失业金人数": {"vi": "Số đơn xin trợ cấp thất nghiệp lần đầu của Hoa Kỳ", "en": "US Initial Jobless Claims"},
    "美联储利率决议": {"vi": "Quyết định lãi suất Fed", "en": "Fed Interest Rate Decision"},
    "美联储联邦基金利率": {"vi": "Lãi suất quỹ liên bang của Fed", "en": "Federal Funds Rate"},
    "芝加哥联储全国活动指数": {"vi": "Chỉ số hoạt động quốc gia của Fed chi nhánh Chicago", "en": "Chicago Fed National Activity Index"},
    "3个月国债拍卖": {"vi": "Đấu giá Hối phiếu 3 tháng", "en": "3-Month Bill Auction"},
    "6个月国债拍卖": {"vi": "Đấu giá Hối phiếu 6 tháng", "en": "6-Month Bill Auction"},
    "adp就业变化": {"vi": "Thay đổi việc làm của ADP", "en": "ADP Employment Change"},
    "红皮书年率": {"vi": "Chỉ số Redbook (theo năm)", "en": "Redbook (YoY)"},
    "建筑许可": {"vi": "Giấy phép xây dựng", "en": "Building Permits"},
    "房价指数": {"vi": "Chỉ số giá nhà", "en": "House Price Index"},
    "新屋销售": {"vi": "Doanh số bán nhà mới", "en": "New Home Sales"},
    "消费者信心": {"vi": "Niềm tin tiêu dùng", "en": "Consumer Confidence"},
    "零售销售": {"vi": "Doanh số bán lẻ", "en": "Retail Sales"},
    "工业产出": {"vi": "Sản lượng công nghiệp", "en": "Industrial Production"},
    "贸易帐": {"vi": "Cán cân thương mại", "en": "Trade Balance"},
    "失业率": {"vi": "Tỷ lệ thất nghiệp", "en": "Unemployment Rate"},
    "国内生产总值": {"vi": "Tổng sản phẩm quốc nội (GDP)", "en": "Gross Domestic Product (GDP)"},
    "采购经理人指数": {"vi": "Chỉ số nhà quản trị mua hàng (PMI)", "en": "Purchasing Managers' Index (PMI)"},
    "讲话": {"vi": "Phát biểu", "en": "Speech"},
    "发言": {"vi": "Phát biểu", "en": "Remarks"},
}


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _cache_key(value: Any) -> str:
    return _text(value).lower()


def _safe_label(value: Any) -> str | None:
    text = _text(value)
    if not text or len(text) > 160 or "\n" in text or CJK_PATTERN.search(text):
        return None
    return text


def _translation_cache_path() -> Path:
    configured = _text(os.getenv("ECONOMIC_CALENDAR_TRANSLATION_CACHE_PATH"))
    if configured:
        return Path(configured).expanduser()
    snapshot = Path(
        _text(os.getenv("INVESTING_CALENDAR_SNAPSHOT_PATH"))
        or "data/economic-calendar/investing-browser.json"
    ).expanduser()
    return snapshot.with_name(Path(DEFAULT_CACHE_PATH).name)


def _load_cache(path: Path) -> Dict[str, Dict[str, str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    raw = payload.get("translations") if isinstance(payload, dict) else None
    if not isinstance(raw, dict):
        return {}
    cache: Dict[str, Dict[str, str]] = {}
    for source, value in raw.items():
        if not isinstance(value, dict):
            continue
        vi = _safe_label(value.get("vi"))
        en = _safe_label(value.get("en"))
        if vi or en:
            cache[_cache_key(source)] = {key: val for key, val in (("vi", vi), ("en", en)) if val}
    return cache


def _write_cache(path: Path, cache: Dict[str, Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"version": 1, "translations": cache}, handle, ensure_ascii=False, separators=(",", ":"))
        Path(temporary_name).replace(path)
    finally:
        temporary = Path(temporary_name)
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def _batch_size() -> int:
    try:
        return min(100, max(10, int(os.getenv("ECONOMIC_CALENDAR_TRANSLATION_BATCH_SIZE", DEFAULT_BATCH_SIZE))))
    except (TypeError, ValueError):
        return DEFAULT_BATCH_SIZE


def _translation_enabled() -> bool:
    return str(os.getenv("ECONOMIC_CALENDAR_TRANSLATION_ENABLED", "true")).strip().lower() not in {
        "0", "false", "no", "off"
    }


def _source_name(event: Dict[str, Any]) -> str:
    return _text(event.get("name") or event.get("event") or event.get("name_en") or event.get("event_en"))


def _merge_translation(source: str, event: Dict[str, Any], cache: Dict[str, Dict[str, str]]) -> Dict[str, str]:
    key = _cache_key(source)
    merged: Dict[str, str] = {}
    for candidate in (STATIC_TRANSLATIONS.get(key, {}), cache.get(key, {}), event):
        vi = _safe_label(candidate.get("vi") if candidate is not event else candidate.get("name_vi"))
        en = _safe_label(candidate.get("en") if candidate is not event else candidate.get("name_en"))
        if vi and "vi" not in merged:
            merged["vi"] = vi
        if en and "en" not in merged:
            merged["en"] = en
    return merged


def _parse_deepseek_response(raw: str, sources: Iterable[str]) -> Dict[str, Dict[str, str]]:
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3].strip()
    try:
        payload = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        logger.warning("Economic calendar translation returned invalid JSON")
        return {}

    rows = payload.get("translations") if isinstance(payload, dict) else payload
    if isinstance(rows, dict):
        rows = [{"source": source, **value} for source, value in rows.items() if isinstance(value, dict)]
    if not isinstance(rows, list):
        return {}

    allowed = {_cache_key(source): source for source in sources}
    translated: Dict[str, Dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        source = _text(row.get("source"))
        source_key = _cache_key(source)
        if source_key not in allowed:
            continue
        vi = _safe_label(row.get("vi") or row.get("vietnamese"))
        en = _safe_label(row.get("en") or row.get("english"))
        if vi or en:
            translated[allowed[source_key]] = {key: val for key, val in (("vi", vi), ("en", en)) if val}
    return translated


def _call_deepseek_batch(sources: List[str]) -> Dict[str, Dict[str, str]]:
    llm = LLMService(provider="deepseek")
    if not llm.is_configured(LLMProvider.DEEPSEEK):
        logger.info("DeepSeek is not configured; using cached/static calendar translations")
        return {}

    system_prompt = (
        "You translate economic calendar event labels. Return JSON only in the form "
        '{"translations":[{"source":"...","vi":"...","en":"..."}]}. '
        "Translate every supplied source exactly once. Vietnamese must be natural financial Vietnamese; "
        "English must be concise. Preserve acronyms, numbers, YoY/MoM and institution names. "
        "Do not add explanations, values, dates, recommendations, or any Chinese characters in vi/en."
    )
    user_prompt = json.dumps({"sources": sources}, ensure_ascii=False, separators=(",", ":"))
    try:
        raw = llm.call_llm_api(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            use_fallback=False,
            provider=LLMProvider.DEEPSEEK,
            use_json_mode=True,
            try_alternative_providers=False,
        )
    except Exception as exc:
        logger.warning("Economic calendar DeepSeek translation failed: %s", type(exc).__name__)
        return {}
    return _parse_deepseek_response(raw, sources)


def translate_calendar_event_names(events: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enrich event rows with validated Vietnamese and English labels.

    Translation runs in the scheduled worker, never during a dashboard
    request. Existing snapshot labels and static/cache values are reused; only
    missing labels are sent to the explicitly selected DeepSeek provider.
    """
    translated_events = [dict(event) for event in events if isinstance(event, dict)]
    cache_path = _translation_cache_path()
    cache = _load_cache(cache_path)
    pending: List[str] = []
    seen = set()

    for event in translated_events:
        source = _source_name(event)
        if not source:
            continue
        if not _safe_label(event.get("name_vi")):
            event.pop("name_vi", None)
        if not _safe_label(event.get("name_en")):
            event.pop("name_en", None)
        labels = _merge_translation(source, event, cache)
        if labels:
            event.update({"name_vi": labels["vi"]} if labels.get("vi") else {})
            event.update({"name_en": labels["en"]} if labels.get("en") else {})
        if ("vi" not in labels or "en" not in labels) and _cache_key(source) not in seen:
            pending.append(source)
            seen.add(_cache_key(source))

    if _translation_enabled() and pending:
        for start in range(0, len(pending), _batch_size()):
            batch = pending[start:start + _batch_size()]
            for source, labels in _call_deepseek_batch(batch).items():
                key = _cache_key(source)
                cache[key] = {**cache.get(key, {}), **labels}
        for event in translated_events:
            source = _source_name(event)
            labels = _merge_translation(source, event, cache)
            if labels.get("vi"):
                event["name_vi"] = labels["vi"]
            if labels.get("en"):
                event["name_en"] = labels["en"]

    if cache:
        _write_cache(cache_path, cache)
    return translated_events
