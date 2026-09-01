# Local DataVest Production Data Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the DataVest production database and product snapshot files with the complete state from the new QuantDinger-first local DataVest stack.

**Architecture:** Export the PostgreSQL 18 local database as PostgreSQL 16-compatible plain SQL, checksum it, and stage it on the VPS. Back up the current production database and product-data directories, stop only DataVest writers, restore into the canonical `datavest` database, preserve the production admin role for the matching account, then verify counts, authentication, APIs, and service health.

**Tech Stack:** PostgreSQL 18/16, Docker Desktop, systemd user services, SSH/SCP, gzip/tar.

**Spec:** User request in the current DataVest deployment task.

## Global Constraints

- Use only the new DataVest containers (`datavest-*`); never read or import `quant_insight_radar` application data.
- Never copy browser profiles, cookies, Celery schedule state, secrets, tokens, or Redis ephemeral state.
- Preserve a PostgreSQL custom-format backup and product-data archive before destructive restore.
- Keep the canonical production database name `datavest` so future deployments remain compatible.
- Verify SHA-256 on both transfer artifacts before restore.
- Keep `kieucuong01@gmail.com` active and restore its production admin role after import.

---

### Task 1: Inventory and export local DataVest

**Files:**
- Create: `.local/migrations/20260901-new-datavest-to-production/datavest-new-local.sql.gz`
- Create: `.local/migrations/20260901-new-datavest-to-production/datavest-product-data.tar.gz`

- [ ] Identify the running `datavest-postgres` and `datavest-backend` containers.
- [ ] Record exact key table counts, snapshot ranges, user identities, and data directories.
- [ ] Export all 64 PostgreSQL tables without owners or ACLs.
- [ ] Remove only PostgreSQL 18-only `restrict`, `unrestrict`, and `transaction_timeout` directives.
- [ ] Archive product data while excluding browser profiles and Celery schedule files.
- [ ] Validate gzip streams and SHA-256 hashes.

### Task 2: Back up and restore production

**Files:**
- Create: `/opt/datavest/backups/pre-local-migration-<timestamp>.dump`
- Create: `/opt/datavest/backups/pre-local-migration-data-<timestamp>.tar.gz`

- [ ] Upload artifacts to `/opt/datavest/shared/incoming/20260901-new-local/` and verify hashes.
- [ ] Back up the current production database and data directory.
- [ ] Stop `datavest-api`, `datavest-celery`, `datavest-beat`, and `datavest-scheduler`.
- [ ] Drop and recreate only the `public` schema in the canonical `datavest` database.
- [ ] Restore the local SQL with `ON_ERROR_STOP=1`.
- [ ] Move existing product-data directories into a recoverable backup directory and extract the local archive.
- [ ] Promote the matching DataVest account to `admin` without changing its imported password hash.

### Task 3: Verify and document

**Files:**
- Create: `.local/migrations/20260901-new-datavest-to-production/migration-result.json`

- [ ] Compare user, watchlist, position, collector, observation, snapshot, opinion, evidence, import, and optimizer counts with local.
- [ ] Confirm the observation, snapshot, and collector time ranges.
- [ ] Restart all four DataVest services and require `active` state.
- [ ] Verify local readiness and public HTTPS return 200.
- [ ] Verify production login and authenticated Smart Insights/portfolio APIs.
- [ ] Retain rollback artifacts and record their paths/checksums without secrets.
