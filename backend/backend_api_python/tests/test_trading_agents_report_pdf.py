from io import BytesIO

from pypdf import PdfReader

from app.services.ai_report_pdf import (
    build_trading_agents_report_pdf,
    extract_portfolio_manager_decision,
    extract_portfolio_manager_decision_sections,
    structure_trading_agents_report,
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


def test_portfolio_decision_sections_recognize_plain_text_bull_bear_markers() -> None:
    decision = extract_portfolio_manager_decision_sections(
        "V. Portfolio Manager Decision\n"
        "Rating: Hold\n"
        "Executive Summary: Giữ vị thế lõi, không mua đuổi.\n"
        "PHE BÒ (Aggressive) đưa ra luận điểm giá còn trên SMA50.\n"
        "PHE GẤU (Conservative) cảnh báo giá dưới VWMA.\n"
        "PHE TRUNG LẬP (Neutral) nhấn mạnh rủi ro stop quá gần.\n"
        "DANH SÁCH THEO DÕI để nâng/hạ rating: FOMC và CPI.\n"
        "Time Horizon: 2-6 tuần"
    )

    assert decision["fields"]["rating"] == "Hold"
    assert decision["fields"]["bull"] == "đưa ra luận điểm giá còn trên SMA50."
    assert decision["fields"]["bear"] == "cảnh báo giá dưới VWMA."
    assert decision["fields"]["neutral"] == "nhấn mạnh rủi ro stop quá gần."
    assert decision["fields"]["watchlist"] == "FOMC và CPI."


def test_portfolio_decision_sections_normalize_prefixed_manager_rating() -> None:
    decision = extract_portfolio_manager_decision_sections(
        "V. Portfolio Manager Decision\n"
        "### Portfolio Manager\n"
        "Portfolio Manager Rating: Reduce\n"
        "Executive Summary: Giảm tỷ trọng cho tới khi có xác nhận."
    )

    assert decision["fields"]["rating"] == "Reduce"


def test_portfolio_decision_sections_split_inline_upgrade_and_downgrade_scenarios() -> None:
    decision = extract_portfolio_manager_decision_sections(
        "V. Portfolio Manager Decision\n"
        "DANH SÁCH THEO DÕI: FOMC | CPI | Dòng tiền ETF. "
        "Nâng lên Overweight nếu: đóng cửa trên 78.910 kèm volume lớn. "
        "Hạ xuống Underweight nếu: thủng 76.248 kèm khối lượng lớn."
    )

    assert decision["fields"]["watchlist"] == "FOMC | CPI | Dòng tiền ETF."
    assert decision["fields"]["upgrade"] == "đóng cửa trên 78.910 kèm volume lớn."
    assert decision["fields"]["downgrade"] == "thủng 76.248 kèm khối lượng lớn."


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

    assert "TÓM TẮT BÁO CÁO QUYẾT ĐỊNH DANH MỤC ĐẦU TƯ" in first_page
    assert "TÓM TẮT HÀNH ĐỘNG" in first_page
    assert "Giữ tỷ trọng hiện tại và chờ xác nhận tại vùng kháng cự." in normalized_first_page
    assert "Luận điểm ngoài phạm vi" not in normalized_first_page


def test_trading_agents_pdf_structures_portfolio_decision_into_action_thesis_and_scenarios() -> None:
    pdf = build_trading_agents_report_pdf(
        content=(
            "# Báo cáo phân tích BTC/USDT\n\n"
            "## V. Portfolio Manager Decision\n\n"
            "Portfolio Manager\n"
            "Rating: Hold\n"
            "Executive Summary: Giữ vị thế lõi, không mua đuổi ở 78.386. Giảm sizing 25-30% và không dùng đòn bẩy. "
            "Stop cứng dưới 76.248. Chỉ thêm vị thế khi đóng cửa trên 78.910 kèm khối lượng lớn.\n\n"
            "Investment Thesis: Cấu trúc trung hạn còn tăng nhưng ngắn hạn bất định.\n"
            "PHE BÒ: Giá trên SMA50 và SMA200; dòng ETF vẫn dương.\n"
            "PHE GẤU: Giá dưới VWMA; khối lượng giảm 60% và MACD mở rộng âm.\n"
            "PHE TRUNG LẬP: Stop quá gần dễ bị quét nhiễu, nhưng dời về 70.000 làm rủi ro tăng cao.\n"
            "CÂN LẠI: HOLD với tỷ trọng đã thu gọn là chiến lược phù hợp.\n\n"
            "DANH SÁCH THEO DÕI: FOMC 16/09 | CPI | Dòng tiền ETF | Thanh lý OI Altcoin.\n"
            "Nâng lên Overweight nếu đóng cửa trên 78.910 kèm volume lớn.\n"
            "Hạ xuống Underweight nếu thủng 76.248 kèm khối lượng lớn.\n"
            "Time Horizon: 2-6 tuần"
        ),
        market="Crypto",
        symbol="BTC-USD",
        analysis_date="2026-09-10",
        language="vi-VN",
        run_id="structured-decision",
    )

    first_page = " ".join((PdfReader(BytesIO(pdf)).pages[0].extract_text() or "").split())

    assert "TÓM TẮT BÁO CÁO QUYẾT ĐỊNH DANH MỤC ĐẦU TƯ" in first_page
    assert "TÓM TẮT HÀNH ĐỘNG" in first_page
    assert "LUẬN ĐIỂM ĐẦU TƯ" in first_page
    assert "PHE BÒ" in first_page
    assert "PHE GẤU" in first_page
    assert "PHE TRUNG LẬP" in first_page
    assert "DANH SÁCH THEO DÕI & KỊCH BẢN" in first_page
    assert "2-6 tuần" in first_page


def test_trading_agents_report_preserves_team_role_and_nested_analysis_levels() -> None:
    blocks = structure_trading_agents_report(
        "# Trading Analysis Report: BTC-USD\n"
        "## I. Analyst Team Reports\n"
        "### Market Analyst\n"
        "# Market review\n"
        "1. Xác nhận dữ liệu và ghi chú sai lệch\n"
        "Giá đóng cửa tăng nhẹ.\n"
        "FINAL TRANSACTION PROPOSAL: **HOLD**\n"
        "## II. Research Team Decision\n"
        "### Research Manager\n"
        "Recommendation: Hold\n"
        "## V. Portfolio Manager Decision\n"
        "Portfolio Manager\n"
        "Portfolio Manager Rating: Hold\n"
    )

    headings = [(block["level"], block["text"]) for block in blocks if block["type"] == "heading"]
    assert headings == [
        (1, "Trading Analysis Report: BTC-USD"),
        (2, "I. Analyst Team Reports"),
        (3, "Market Analyst"),
        (4, "Market review"),
        (4, "1. Xác nhận dữ liệu và ghi chú sai lệch"),
        (2, "II. Research Team Decision"),
        (3, "Research Manager"),
        (2, "V. Portfolio Manager Decision"),
        (3, "Portfolio Manager"),
    ]
    assert [
        (block["label"], block["value"], block["tone"])
        for block in blocks
        if block["type"] == "callout"
    ] == [
        ("FINAL TRANSACTION PROPOSAL", "HOLD", "hold"),
        ("Recommendation", "Hold", "hold"),
        ("Portfolio Manager Rating", "Hold", "hold"),
    ]
