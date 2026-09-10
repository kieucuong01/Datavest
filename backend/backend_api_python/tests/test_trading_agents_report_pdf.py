from io import BytesIO

from pypdf import PdfReader

from app.services.ai_report_pdf import (
    build_trading_agents_report_pdf,
    extract_portfolio_manager_decision,
)


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


def test_portfolio_manager_summary_extracts_only_section_v() -> None:
    decision = extract_portfolio_manager_decision(
        "# Báo cáo phân tích BTC/USDT\n\n"
        "## I. Báo cáo nhóm phân tích\n\n"
        "**Luận điểm ngoài phạm vi**: Không được đưa vào trang tóm tắt.\n\n"
        "## V. Portfolio Manager Decision\n\n"
        "### Portfolio Manager\n"
        "**Rating**: Overweight\n\n"
        "**Executive Summary**: Build position gradually after confirmation.\n\n"
        "**Risk Control**: Exit if daily support fails.\n\n"
        "## Appendix\n\n"
        "**Ngoài quyết định**: Không được đưa vào trang tóm tắt."
    )

    assert decision["title"] == "V. Portfolio Manager Decision"
    assert decision["cards"] == [
        ("Rating", "Overweight"),
        ("Executive Summary", "Build position gradually after confirmation."),
        ("Risk Control", "Exit if daily support fails."),
    ]


def test_trading_agents_pdf_uses_portfolio_manager_decision_as_its_first_page_summary() -> None:
    pdf = build_trading_agents_report_pdf(
        content=(
            "# Báo cáo phân tích BTC/USDT\n\n"
            "## I. Báo cáo nhóm phân tích\n\n"
            "**Luận điểm ngoài phạm vi**: Không được đưa vào tóm tắt.\n\n"
            "## V. Quyết định quản lý danh mục\n\n"
            "### Quản lý danh mục\n"
            "**Khuyến nghị**: HOLD\n\n"
            "**Tóm tắt điều hành**: Giữ tỷ trọng hiện tại và chờ xác nhận tại vùng kháng cự.\n\n"
            "**Hành động chiến lược**: Không tăng vị thế khi chưa có thanh khoản xác nhận."
        ),
        market="Crypto",
        symbol="BTC/USDT",
        analysis_date="2026-09-09",
        language="vi-VN",
        run_id="summary-preview",
    )

    first_page = PdfReader(BytesIO(pdf)).pages[0].extract_text() or ""
    normalized_first_page = " ".join(first_page.split())

    assert "Quyết định quản lý danh mục" in first_page
    assert "tóm tắt điều hành" in first_page.casefold()
    assert "Giữ tỷ trọng hiện tại và chờ xác nhận tại vùng kháng cự." in normalized_first_page
    assert "Luận điểm ngoài phạm vi" not in normalized_first_page
