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

Task 4 commit: 5733d34.

Final review: one independent fresh-context reviewer examined bc85a35..5733d34. No critical findings; four important findings: NAV missing-date retry, opening request replay, stale/absent data-quality transitions, conditional chart DOM lifecycle. Cancellation replay was labelled minor; re-graded Important because an identical accepted request must keep its original result after later edits. All five are fixed in one pass; no second review was dispatched.

Final: fixed unavailable NAV dates being skipped — test_worker_retries_missing_dates_without_blocking_newer_days RED→GREEN. Follow-up regression tests test_carried_incomplete_date_keeps_retry_in_new_revision and test_worker_defers_idle_book_so_retry_books_are_not_starved also observed RED→GREEN, covering retry inheritance and idle-job fairness. Final backend suite 102/102.

Final: Ruling: each worker batch processes at most one new date plus one due retry per book, maximum 20 books; missing dates retry after five minutes and preserve immutable evidence. Idle books defer until the next retry or Vietnam midnight. Cost if wrong: an outage may require up to twice the former bounded provider work, and long missing histories recover gradually rather than all at once.

Final: fixed opening retry validation order — test_opening_retry_replays_before_mutable_source_validation RED→GREEN; stored canonical command replay is owner-scoped and still rejects changed payloads. Final backend suite 102/102.

Final: fixed stale/missing snapshot alert suppression — test_stale_and_absent_snapshots_alert_once_then_recover RED→GREEN. Allocation still requires fresh complete NAV; valid weekend closes retain their accepted status. Final backend suite 102/102.

Final: fixed ECharts attachment to replaced DOM — charts rebind after Vue replaces their conditional DOM nodes RED→GREEN, covering NAV and benchmark chart instances. Full frontend suite 344/344.

Final: fixed cancellation retry after later restoration/edit — test_cancel_retry_after_restoring_event_replays_original_command RED→GREEN. Canonical cancellation intent is independent of the mutable event contents. Final backend suite 102/102.

Final: minor (deferred): LedgerImport.vue has one vue/no-template-shadow warning for the preview-error loop variable; zero lint errors. This is naming polish and does not change preview validation or commit eligibility.

Final verification completed 2026-10-11: 102 backend tests passed (ledger, routes, NAV, gateway, benchmarks, alerts, stored source reading, monitor hook, PDF extraction, existing valuation/optimizer regressions); 344 frontend tests passed; changed-file lint zero errors/one naming warning; Vite production build passed in 37.40s; git diff --check passed. Graphify AST update completed and graph artifacts remain excluded from feature commits; SQL graph extraction is limited by the missing optional tree_sitter_sql parser.

Final browser evidence: local fixture UI, not production or real-provider evidence. Deposit, two buys, sale with fee/tax and dividend yielded cash 34430, quantity 150, average cost 111, realized P&L 880, dividend income 200. VNINDEX→VN30 and history reload each recreated a visible canvas on the current DOM; console warning/error log was empty. Screenshots: output/portfolio-final-qa.png, output/portfolio-benchmark-qa.png, output/portfolio-alerts-qa.png, output/portfolio-mobile-qa.png. Alert opt-in/save/disable and invalid CSV commit prevention were checked. Desktop/mobile fixture checks do not establish authenticated production delivery.

Release boundary: branch remains local, with four separate feature commits plus the final review-fix commit. No push, merge, deployment, production migrations, external notifications or paid AI calls were performed. PostgreSQL lock behavior/migration execution, real-provider completeness, and authenticated production browser behavior remain unverified; SQLite tests and the UI fixture are explicitly scoped evidence. Three idempotent migration files are already wired into database bootstrap, including the retry table in 20261005_portfolio_nav.sql.
