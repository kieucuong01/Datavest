# SDD ledger — plan: docs/superpowers/plans/2026-10-05-portfolio-ledger-nav-alerts.md

User approved all four tasks on 2026-10-06. Execution is sequential, with one feature commit per task. Local release only.

Setup: Ruling: use an isolated feature branch in the existing checkout instead of another worktree. Existing dependencies and unrelated graph/cache changes stay in place; stage only feature files. Cost if wrong: shared filesystem offers less isolation than a second checkout.

Task 1: Ruling: manual historical VN entries use syntactic equity identity, excluding indices, rather than the current AI-eligible active catalog. A historical ledger must still accept formerly held/delisted shares when the current catalog changes. Unsupported historical quotes stay unavailable. Cost if wrong: a mistyped ticker can be recorded and requires an audit revision to correct.

Task 1: RED confirmed missing backend modules and missing Vue workspace; repository tests use SQLite SQL adapter without PostgreSQL FOR UPDATE to exercise transaction rollback, ownership, replay and idempotency. PostgreSQL concurrency is protected by the production row lock but is not proved by SQLite.

Task 1: complete — backend ledger/repository/routes 14 passed; existing valuation/optimizer 38 passed; full frontend 339 passed; changed-file lint zero errors. Browser local Vue fixture: created VND book, deposited 50000, cash and revision changed, invalid CSV showed row error and disabled commit, console errors/warnings empty. Browser screenshot capture was unavailable; retry at final integrated UI QA. No production DB used.
