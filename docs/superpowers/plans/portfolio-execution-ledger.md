# SDD ledger — plan: docs/superpowers/plans/2026-10-05-portfolio-ledger-nav-alerts.md

User approved all four tasks on 2026-10-06. Execution is sequential, with one feature commit per task. Local release only.

Setup: Ruling: use an isolated feature branch in the existing checkout instead of another worktree. Existing dependencies and unrelated graph/cache changes stay in place; stage only feature files. Cost if wrong: shared filesystem offers less isolation than a second checkout.

Task 1: Ruling: manual historical VN entries use syntactic equity identity, excluding indices, rather than the current AI-eligible active catalog. A historical ledger must still accept formerly held/delisted shares when the current catalog changes. Unsupported historical quotes stay unavailable. Cost if wrong: a mistyped ticker can be recorded and requires an audit revision to correct.

Task 1: RED confirmed missing backend modules and missing Vue workspace; repository tests use SQLite SQL adapter without PostgreSQL FOR UPDATE to exercise transaction rollback, ownership, replay and idempotency. PostgreSQL concurrency is protected by the production row lock but is not proved by SQLite.

Task 1: complete — backend ledger/repository/routes 14 passed; existing valuation/optimizer 38 passed; full frontend 339 passed; changed-file lint zero errors. Browser local Vue fixture: created VND book, deposited 50000, cash and revision changed, invalid CSV showed row error and disabled commit, console errors/warnings empty. Browser screenshot capture was unavailable; retry at final integrated UI QA. No production DB used.

Task 1 commit: 90af2f3.

Task 2: Ruling: carry proven unaffected dates into the new ledger revision, with derivedFromRevision, while excluding all dates on/after the edit. Cost if wrong: changes to snapshot schema must also maintain the carry-forward adapter.

Task 2: Ruling: immutable NAV evidence records every attempted checksum. The current-day/revision pointer may replace an unavailable snapshot when pricing recovers, but never replaces a complete valuation. Recovery test failed before this implementation and passed after. Cost if wrong: complete provider corrections require a deliberate ledger/history revision workflow instead of silent repricing.

Task 2: Ruling: cash-only flow valuations can be established exactly from the ledger and permit guarded Dietz estimates; flows with an existing risky holding require separately evidenced flow-time valuations and stay null. Cost if wrong: some periods show no return until finer valuation evidence is added.

Task 2: Ruling: use conservative weekday closure for HOSE/gold because the existing gateway has no verified exchange holiday calendar. Weekends retain valid previous closes; unverified weekday holidays may show stale/missing NAV. Cost if wrong: holiday gaps reduce displayed coverage until a verified calendar is integrated.

Task 2: complete — NAV/history/ledger/routes/VN gateway tests 33 passed; frontend lifecycle/history 2 passed; changed lint zero errors. Vue fixture showed null return across a missing day and 1W control changed selection, with no console errors. Screenshot output/portfolio-nav-qa.png. Background work is a bounded batch dispatched from the existing monitor tick; no second scheduler.
