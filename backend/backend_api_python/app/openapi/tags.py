"""OpenAPI tag names (English). Keep stable for published docs."""

HEALTH = "Health"
AUTH = "Auth"
USERS = "Users"
MARKET = "Market"
UNIVERSE = "Universe"
FACTOR = "Factor"
INDICATOR = "Indicator"
BACKTEST = "Backtest"
STRATEGY = "Strategy"
COMMUNITY = "Community"
DASHBOARD = "Dashboard"
PORTFOLIO = "Portfolio"
SETTINGS = "Settings"
FAST_ANALYSIS = "FastAnalysis"
GLOBAL_MARKET = "GlobalMarket"
AI_CHAT = "AIChat"
SMART_INSIGHTS = "SmartInsights"

ALL_TAGS = [
    {"name": HEALTH, "description": "Liveness and API metadata (Public)"},
    {"name": AUTH, "description": "Authentication and OAuth (Public)"},
    {"name": USERS, "description": "User profile and administration (Mixed)"},
    {"name": MARKET, "description": "Market data and watchlists (Public)"},
    {"name": UNIVERSE, "description": "Point-in-time strategy universes (Internal)"},
    {"name": FACTOR, "description": "Versioned factor catalog and research diagnostics (Internal)"},
    {"name": INDICATOR, "description": "Indicator IDE workspace (Public)"},
    {"name": BACKTEST, "description": "Unified V2 backtesting (Public)"},
    {"name": STRATEGY, "description": "Strategy source, research, and backtests (Internal)"},
    {"name": COMMUNITY, "description": "Free source-visible research library (Public)"},
    {"name": DASHBOARD, "description": "Dashboard aggregates (Internal)"},
    {"name": PORTFOLIO, "description": "Manual portfolio tracking (Internal)"},
    {"name": SETTINGS, "description": "System and brand settings (Mixed)"},
    {"name": FAST_ANALYSIS, "description": "Fast AI analysis (Public)"},
    {"name": GLOBAL_MARKET, "description": "Global market overview (Public)"},
    {"name": AI_CHAT, "description": "Legacy AI chat compatibility (Internal)"},
    {"name": SMART_INSIGHTS, "description": "Source-backed market intelligence (Internal)"},
]
