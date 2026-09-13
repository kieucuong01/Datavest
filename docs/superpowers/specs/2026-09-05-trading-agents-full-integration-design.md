# TradingAgents Full Integration Design

## Goal

Integrate the complete upstream TradingAgents research framework into DataVest
without replacing its agent graph, prompts, tool selection, debates, risk
discussion, memory/reflection, checkpoints, report tree, or provider support.
DataVest owns authentication, product navigation, persisted user-visible
results, market identity mapping, and the existing paper-only boundary.

## Upstream boundary and provenance

- Upstream repository: `https://github.com/TauricResearch/TradingAgents`
- Pinned source commit: `9dee508c44662702281a8dbaad1f7b42179b5ba7`
- License: Apache-2.0. Preserve its complete `LICENSE`, copyright headers, and
  an attribution entry in `LICENSES.md` and `backend/NOTICE`.
- Vendored source location: `backend/third_party/tradingagents/`.
- The vendored tree is a full git subtree import at the pinned commit. Do not
  edit agent, graph, prompt, dataflow, CLI, test, or package files in that
  tree. DataVest-specific behavior belongs in `backend/trading_agents_service/`.
- A later upstream upgrade is a deliberate subtree update with the full
  upstream test suite, not an unreviewed dependency upgrade.

## Product boundary

DataVest remains research and paper-investing only. The full TradingAgents
workflow produces its native final decision and trader proposal. The pinned
upstream source contains no simulated-exchange or broker-order implementation,
so this integration does not invent one or alter DataVest Mock Portfolio.

No TradingAgents feature is silently removed. Where an upstream data vendor is
not configured or does not cover a DataVest market, its native unavailable or
vendor error remains visible in the report. DataVest must not fabricate an
equivalent value.

## Chosen architecture

Run TradingAgents as `datavest-trading-agents`, a private Docker service in the
same DataVest monorepo, Compose release, network, and deployment manifest.
It has an independent Python 3.12 environment and dependency lock so LangGraph
and upstream dependencies cannot destabilize the Flask backend.

The Flask backend is the only public gateway. It authenticates the user,
validates asset identity and run configuration, creates a durable run record,
and sends an internal signed job request to the service. The service has no
public port and cannot access the DataVest database with a general-purpose
credential. It stores upstream-native checkpoint, report, cache, and memory
files in a per-user directory under a named volume; it returns structured event
and artifact metadata to the backend through an authenticated internal callback.

```text
Vue AI Assistant / Smart Insights
  -> Flask API (JWT, ownership, validation, durable run id)
  -> PostgreSQL + Celery/Redis (status and audit)
  -> private datavest-trading-agents container
       -> exact TradingAgentsGraph at pinned commit
       -> exact upstream LLM and data-vendor interfaces
       -> per-user upstream checkpoint/memory/report volume
  -> internal callback -> PostgreSQL -> SSE/polling -> Vue report
```

## Full upstream capability mapping

| Upstream capability | DataVest integration behavior |
| --- | --- |
| Market, sentiment/social, news, and fundamentals analysts | All four are selected by default and selectable individually in the advanced run form. |
| Bull and Bear researchers, Research Manager, Trader | Preserve graph nodes, outputs, tool calls, and report sections exactly. |
| Aggressive, Neutral, Conservative risk roles and Portfolio Manager | Preserve all three risk discussion roles and final structured decision. |
| Five-tier rating and trader proposal | Preserve original values and label them research output; do not add an execution path absent from upstream. |
| Crypto pipeline and stock pipeline | Use upstream asset type unchanged after DataVest symbol mapping. |
| yfinance, Alpha Vantage, FRED, Polymarket, Reddit, StockTwits, native vendor routing | Install and configure the original vendor chain inside the service. Surface vendor provenance, configured/unavailable state, and errors. |
| LLM providers and `TRADINGAGENTS_*` configuration | Preserve provider selection, deep/quick models, output language, reasoning settings, retries, token cap, debate/risk rounds, and temperature. Secrets remain service-side. |
| LangGraph stream and CLI progress model | Convert graph chunks and tool calls into durable run events; the original CLI remains available only through an admin container command. |
| Checkpoint/resume | Preserve native per-run SQLite checkpoints in the volume; provide resume and clear-checkpoint actions through the API. |
| Decision log, realised outcome, reflection | Preserve upstream memory/reflection files per DataVest user; additionally index run metadata and final output in PostgreSQL for the UI. |
| Raw report tree and structured outputs | Preserve raw upstream Markdown/JSON artifacts; render them in DataVest without summarising away sections. |

## Data and market identity

The service receives an immutable `TradingAgentsRunRequest` created by Flask:
`runId`, `userId`, `market`, `datavestSymbol`, `upstreamTicker`, `assetType`,
`analysisDate`, selected analysts, full TradingAgents runtime configuration,
and optional DataVest evidence reference.

- Crypto: normalize the DataVest symbol to the upstream Yahoo-style pair such
  as `BTC-USD`; preserve Crypto asset type.
- Vietnamese stocks: map the DataVest instrument catalog to its exchange-
  qualified upstream ticker; the service rejects an unmapped symbol rather
  than guessing.
- Gold: map XAU to the upstream-supported `XAUUSD`/`GC=F` normalization path.
- Optional DataVest evidence is additive context displayed separately from
  upstream tool data. It never replaces an upstream tool or pretends to be an
  upstream vendor result.

## Durable DataVest contract

New additive tables:

- `trading_agents_runs`: immutable request/config/source pin/user/status/times.
- `trading_agents_events`: ordered, redacted node/tool/progress/error events.
- `trading_agents_artifacts`: raw report sections and artifact checksums.
- `trading_agents_proposals`: extracted native final decision and trader
  proposal for report filtering and history queries; it is not an order record.

The primary key and all child reads are constrained by `user_id`. A run has
exactly one source pin and config checksum. Re-running with changed analysts,
models, rounds, date, or ticker creates a new run. Resume retains the original
configuration and native checkpoint only.

## API and UI

Public Flask routes under `/api/trading-agents`:

- `POST /runs` creates a full upstream run.
- `GET /runs/{id}` returns owner-scoped status, event cursor and artifact list.
- `GET /runs/{id}/events` provides SSE; polling remains available through
  `GET /runs/{id}`.
- `POST /runs/{id}/resume`, `/cancel`, and `/clear-checkpoint` operate only on
  the owner’s unfinished/native checkpointed run.
- `GET /runs/{id}/artifacts/{name}` retrieves one owner-scoped full report
  section.

AI Assistant adds **Phân tích chuyên sâu mã** beside current fast analysis and
the existing diagnostic tools. It starts or opens a TradingAgents run for the
selected asset. Smart Insights Asset Opinions adds **Phân tích chuyên sâu**;
it only opens a run that matches the row’s market, symbol and selected
`as_of`, or starts a new run explicitly for that date. It never substitutes a
newer run silently.

The detailed report view exposes all upstream sections: analyst reports,
tool/vendor events, bull/bear research, research-manager plan, trader proposal,
all risk discussions, final portfolio-manager decision, memory/reflection,
raw artifact download, and limitations. It must work on 360px and desktop.

## Security, operations and resilience

- Service listens only on the internal Compose network; no host port.
- Non-root, read-only root filesystem; only a scoped named state volume and
  temporary directory are writable.
- Flask signs short-lived internal requests; callbacks authenticate with a
  separate service secret. Neither side logs either secret.
- Provider egress is allowed only because full upstream tools require it. Every
  vendor call has timeout, configured/not-configured status and provenance in
  the event stream.
- Limits: per-user concurrent run count, global worker count, request body,
  runtime deadline, output/event size, retry policy, and cancellation.
- Preserve upstream checkpoints after a failed run; delete only after explicit
  clear or a completed retention policy. Never use a global clear action from a
  normal user route.
- The 07:00 Vietnam monitor remains Fast Analysis unless a user explicitly
  enables a separate scheduled deep analysis later; no automatic cost increase.

## Acceptance requirements

1. Service runs the pinned upstream graph with all four analysts, two
   researchers, trader, three risk agents and portfolio manager in one run.
2. Every upstream data-tool group is callable and reports either the native
   result or an explicit configured/vendor error.
3. Checkpoint crash/resume, memory reflection, report artifacts and CLI command
   work in the service’s per-user state volume.
4. JWT ownership prevents cross-user read/resume/cancel/artifact access.
5. AI Assistant and Smart Insights show complete reports, live progress,
   failure/retry state and mobile-safe UI.
6. No public TradingAgents port, broker credential, live-order route or
   unrelated execution feature is introduced.
7. Upstream tests, DataVest integration tests, security tests and browser E2E
   pass before the feature flag is enabled.
