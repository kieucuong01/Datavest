from io import BytesIO

from pypdf import PdfReader

from app.services.ai_report_pdf import build_trading_agents_report_pdf


def test_vietnamese_trading_agents_pdf_uses_an_extractable_unicode_font() -> None:
    pdf = build_trading_agents_report_pdf(
        content="# Báo cáo BTC\n\n## Tín hiệu\n- Dữ liệu đã xác thực",
        market="Crypto",
        symbol="BTC/USDT",
        analysis_date="2026-09-09",
        language="vi-VN",
        run_id="test-run",
    )

    extracted = "".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)

    assert pdf.startswith(b"%PDF-")
    assert "Tín hiệu" in extracted
    assert "\x00" not in extracted


def test_trading_agents_pdf_renders_markdown_tables_as_readable_cells() -> None:
    pdf = build_trading_agents_report_pdf(
        content=(
            "# Báo cáo BTC\n\n"
            "## Luận điểm chính\n"
            "- Xu hướng trung hạn đang tích cực.\n\n"
            "| Tiêu chí | Kết quả |\n"
            "| --- | --- |\n"
            "| RSI 14 | 58.4 |\n"
            "| Kháng cự | 115,000 USD |"
        ),
        market="Crypto",
        symbol="BTC/USDT",
        analysis_date="2026-09-09",
        language="vi-VN",
        run_id="run-table",
    )

    extracted = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)

    assert "Tiêu chí" in extracted
    assert "Kết quả" in extracted
    assert "Kháng cự" in extracted
    assert "115,000 USD" in extracted
    assert "Tiêu chí · Kết quả" not in extracted
    assert "RSI 14 · 58.4" not in extracted
