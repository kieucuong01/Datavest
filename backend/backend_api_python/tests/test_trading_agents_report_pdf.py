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


def test_trading_agents_pdf_adds_a_short_summary_before_the_report_body() -> None:
    pdf = build_trading_agents_report_pdf(
        content=(
            "# Báo cáo phân tích BTC/USDT\n\n"
            "Generated: 2026-09-09 07:00:00\n\n"
            "## I. Báo cáo nhóm phân tích\n\n"
            "### Chuyên gia thị trường\n"
            "Xu hướng trung hạn tích cực nhưng thanh khoản cần được theo dõi.\n\n"
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

    extracted = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)

    assert "Tóm tắt toàn bộ báo cáo" in extracted
    assert "Giữ tỷ trọng hiện tại và chờ xác nhận tại vùng kháng cự." in extracted
    assert extracted.index("Tóm tắt toàn bộ báo cáo") < extracted.index("Báo cáo phân tích BTC/USDT")
    assert "01\nI. Báo cáo nhóm phân tích" not in extracted


def test_trading_agents_pdf_summary_includes_an_excerpt_from_each_main_section() -> None:
    pdf = build_trading_agents_report_pdf(
        content=(
            "# Báo cáo phân tích BTC/USDT\n\n"
            "## I. Báo cáo nhóm phân tích\n\n"
            "### Chuyên gia thị trường\n"
            "Động lượng giá đang cải thiện, nhưng khối lượng giao dịch chưa xác nhận bứt phá.\n\n"
            "## II. Quyết định nhóm nghiên cứu\n\n"
            "### Nhà nghiên cứu tăng giá\n"
            "Kịch bản tăng cần giữ vững vùng hỗ trợ và dòng tiền vào thị trường.\n\n"
            "## V. Quyết định quản lý danh mục\n\n"
            "### Quản lý danh mục\n"
            "**Khuyến nghị**: HOLD\n\n"
            "**Tóm tắt điều hành**: Chờ thêm xác nhận trước khi thay đổi tỷ trọng."
        ),
        market="Crypto",
        symbol="BTC/USDT",
        analysis_date="2026-09-09",
        language="vi-VN",
        run_id="detailed-summary",
    )

    extracted = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)

    assert "Tổng quan theo các phần" in extracted
    assert "Động lượng giá đang cải thiện, nhưng khối lượng giao dịch chưa xác nhận bứt phá." in extracted
    assert "Kịch bản tăng cần giữ vững vùng hỗ trợ và dòng tiền vào thị trường." in extracted
    assert extracted.index("Động lượng giá đang cải thiện") < extracted.index("Báo cáo phân tích BTC/USDT")


def test_trading_agents_pdf_summary_overview_gives_each_section_an_ordinal_label() -> None:
    pdf = build_trading_agents_report_pdf(
        content=(
            "# Báo cáo phân tích BTC/USDT\n\n"
            "## Luận điểm thị trường\n\n"
            "Xu hướng trung hạn đang tích cực.\n\n"
            "## Quản trị rủi ro\n\n"
            "Rủi ro thanh khoản vẫn cần được theo dõi."
        ),
        market="Crypto",
        symbol="BTC/USDT",
        analysis_date="2026-09-09",
        language="vi-VN",
        run_id="section-cards",
    )

    extracted = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)

    assert "01" in extracted
    assert "02" in extracted
