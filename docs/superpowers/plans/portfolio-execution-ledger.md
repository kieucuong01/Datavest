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

Task 2 commit: 7bf6e47.

Task 3: complete — focused backend 36 passed; frontend lifecycle/history 4 passed, including a late response from a previous benchmark key. Vue local fixture: explicitly selected VNINDEX, rendered 10% price return and null excess across a NAV gap, sources and common dates visible, no console errors. Changed-file lint passed. Screenshot output/portfolio-benchmark-qa.png.

Task 3 commit: ceaa3ec.

Task 4: Ruling: a rule change establishes a new baseline and cancels pending alerts only for rules the user disabled or an allocation threshold they replaced. Timing changes preserve the evidence queue and baseline. Cost if wrong: a current breach at the new threshold is shown in the portfolio rather than pushed retrospectively.

Task 4: Ruling: report alerts preserve the existing shared-report access policy. Held assets outside public scope must also be on the current watchlist to read shared report content. Corporate events use stored source IDs and safe links for holdings/watchlist. Cost if wrong: a held asset without watchlist membership receives no shared report-content alert until added.

Task 4: local verification covers baseline/restart, pending cooldown, recovery/new episode, disabled cancellation, owned notification read/mark-read and two concurrent SQLite workers creating one digest. The existing monitor hook dispatches the NAV batch and alert evaluation. Source-reader test reads stored events in user scope and preserves a future-event cursor.

Task 4: complete — focused backend and report-PDF regression suite 68 passed; full frontend 343 passed; changed-file lint zero errors; Vite production build passed. Vue fixture verified opt-in, threshold change, saved state and disable, plus mobile layout at 390×844. Temporary Vite HMR errors occurred while adding exports, before the fresh reload; a final fresh-tab QA checks for current runtime errors. No production DB migration, external messages, paid analysis, push or deploy.
