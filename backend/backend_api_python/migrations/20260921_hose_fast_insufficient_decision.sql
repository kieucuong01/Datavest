-- Preserve explicit missing-data decisions in account-owned Fast Analysis history.
ALTER TABLE IF EXISTS qd_analysis_memory
    ALTER COLUMN decision TYPE VARCHAR(24);
