-- At most three generation claims per asset/week. No active run is reclaimed.
ALTER TABLE public_research_reports ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 1;
ALTER TABLE shared_watchlist_research_reports ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 1;
