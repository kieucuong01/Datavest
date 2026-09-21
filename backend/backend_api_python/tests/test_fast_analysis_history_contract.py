from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_fast_analysis_history_is_user_scoped_and_uses_safe_smart_insights_projection():
    route = (ROOT / "app" / "routes" / "fast_analysis.py").read_text(encoding="utf-8")
    memory = (ROOT / "app" / "services" / "analysis_memory.py").read_text(encoding="utf-8")

    assert "user_id = getattr(g, 'user_id', None)" in route
    assert "user_id=user_id" in route
    assert "AiAssistantInsightsService._public_report" in route
    assert "AND user_id = %s" in memory


def test_insufficient_data_decision_fits_memory_schema():
    migration = (ROOT / "migrations" / "20260921_hose_fast_insufficient_decision.sql").read_text(encoding="utf-8")
    memory = (ROOT / "app" / "services" / "analysis_memory.py").read_text(encoding="utf-8")
    assert "ALTER COLUMN decision TYPE VARCHAR(24)" in migration
    assert "decision VARCHAR(24)" in memory
