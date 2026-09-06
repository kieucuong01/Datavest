# TradingAgents review — 2026-09-06

## Corrected

- LangGraph `stream_mode=values` emits accumulated state, including empty report
  fields. Progress now recognizes non-empty completed reports and finalized
  debates instead of choosing the first field present. A stale heartbeat cannot
  override newer completion evidence. Percent remains a stage estimate, not an
  estimate of token completion or remaining wall-clock time.
- Resume dispatch starts event sequencing after the last persisted event.
  Transient callback retries use the same sequence; persistence deduplicates it.
  Resume during pending cancellation is rejected explicitly.
- Public-source waits and model requests have limits; unavailable social sources
  are described as unavailable, never replaced with fabricated data. Hosted
  configuration and bounded fetch threads retain each run's context.
- Frontend polling is single-flight, recovers from transient network errors and
  rejects stale responses after close/date/asset changes. Report loading has a
  retry state. Closing the modal does not cancel the server task.
- Native team/analyst report hierarchy remains intact when model content starts
  with H1/H2. Nested sections render recursively, fenced text remains text, and
  tables scroll locally. Mobile has one vertical scroll surface.

## Verification and remaining release gates

Focused service, public progress/task/repository and patched-upstream tests;
frontend unit tests, ESLint and production build; local browser fixtures at
1280/390/360px cover progress reconnect, close/reopen, artifact retry, nested
content, accordion interaction and stale-date responses.

This is not a production release or a live-provider latency certification.
Before release, smoke one real run with production-like provider access and
verify final artifact persistence plus callback delivery. Sustained callback
outages or process restarts still require reconciliation/retry: two HTTP retries
are not a durable event outbox. Existing checkpoint identity is still upstream's
owner/ticker/day/graph-signature scope, not an independent checkpoint per DataVest
run; avoid concurrent fresh runs for the same owner and ticker/day. Historical
lookup currently matches owner/asset/day, not language; a stored report carries
its original language label. These are follow-up lifecycle improvements, not
reasons to replace the native analysis engine.

The upstream pin remains the imported base. Local vendor patches are recorded
in `backend/third_party/tradingagents/UPSTREAM.md` and keep the native roles,
tools and prompts. No API key values are stored in this report.
