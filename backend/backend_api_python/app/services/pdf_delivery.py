"""Small, shared HTTP delivery helpers for generated report PDFs."""

from __future__ import annotations

import re

from flask import Response


def trading_agents_pdf_filename(
    *, symbol: str, analysis_date: str, summary: bool, fallback_date: str = ""
) -> str:
    safe_symbol = re.sub(r"[^A-Za-z0-9._-]+", "_", str(symbol or "report")).strip("_")
    date_text = re.sub(r"[^0-9]", "", str(analysis_date or ""))[:8]
    if not date_text:
        date_text = re.sub(r"[^0-9]", "", str(fallback_date or ""))[:8] or "latest"
    prefix = "DataVest_TradingAgents_Summary" if summary else "DataVest_TradingAgents"
    return f"{prefix}_{safe_symbol or 'report'}_{date_text}.pdf"


def trading_agents_pdf_response(
    pdf_bytes: bytes,
    *,
    symbol: str,
    analysis_date: str,
    summary: bool,
    fallback_date: str = "",
) -> Response:
    """Return an inline, no-store PDF response with a safe report filename."""
    filename = trading_agents_pdf_filename(
        symbol=symbol,
        analysis_date=analysis_date,
        summary=summary,
        fallback_date=fallback_date,
    )
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
            "Cache-Control": "no-store, max-age=0",
        },
    )


__all__ = ["trading_agents_pdf_filename", "trading_agents_pdf_response"]
