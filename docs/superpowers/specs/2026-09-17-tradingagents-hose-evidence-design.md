# TradingAgents HOSE Evidence Design

## Goal

Make a `VNStock` TradingAgents run consume DataVest's shared point-in-time Vietnam Evidence DTO instead of relying on a `.VN` ticker mapping and generic Yahoo data alone.

## Scope

- Keep the full pinned TradingAgents graph and all analyst/debate/risk roles.
- Build one immutable Vietnam evidence snapshot per run from free VNDIRECT and Yahoo data.
- Send that snapshot through the existing HMAC-signed private boundary.
- Make the snapshot the authoritative source for exact HOSE identity, price, technical, fundamental, corporate-action, disclosure, and market-context claims.
- Keep Crypto and Gold behavior unchanged.
- Do not add SSI, a paid provider, broker execution, or live-trading behavior.

## Snapshot construction

The backend worker constructs evidence before dispatching a HOSE run. It loads up to 260 adjusted daily bars ending at the requested `analysis_date`, derives a price payload and deterministic technical indicators, then calls `VietnamEvidenceService.build(..., as_of=cutoff)`.

The cutoff is the end of `analysis_date` in `Asia/Ho_Chi_Minh`, converted to UTC. Bars, financial observations, corporate actions, and disclosures after that cutoff are excluded. If no valid historical price bar exists, the run fails closed with a safe `evidence_unavailable` code.

## Reproducibility and persistence

`trading_agents_runs` gains nullable `evidence_json`, `evidence_checksum`, and `evidence_as_of` columns. The first worker execution may attach the snapshot; after that, database constraints and repository code make it write-once. Resume, cancellation, and checkpoint operations reuse the stored snapshot instead of rebuilding it from newer provider data.

The public run contract exposes only evidence provenance (`checksum`, `asOf`, `version`, providers and gap count), never the full raw observation payload.

## Private service boundary

The signed service payload includes `vietnam_evidence` only for `VNStock`. The private service validates:

- object shape and maximum serialized size;
- `version=vietnam-evidence-v1`;
- checksum over canonical JSON excluding the checksum field;
- `instrument.market=VNStock`, `instrument.exchange=HOSE`;
- evidence symbol matches the `.VN` ticker;
- evidence `asOf` is not later than the requested analysis-date cutoff.

`VNStock` requests without valid evidence are rejected. Non-Vietnam requests carrying Vietnam evidence are also rejected.

## TradingAgents consumption

The service formats a bounded, deterministic evidence context from the DTO. It includes instrument identity, point-in-time price and technical values, derived fundamental metrics, recent same-date-safe observations, corporate actions, disclosures, Vietnam benchmark context, explicit gaps, sources, checksum, and cutoff.

This context is appended to the existing `instrument_context`, which reaches all analyst and downstream graph roles. The market and fundamental analyst prompts are amended conditionally: when the instrument context declares a DataVest point-in-time snapshot, that snapshot takes precedence over generic Yahoo-derived tools for exact HOSE claims. Generic tools may supplement it only when their data is dated no later than the analysis date; conflicts must be disclosed rather than silently reconciled.

## Observability

Before graph execution, the private service publishes an `evidence_snapshot` event containing only the bounded provenance summary. Tool events continue to record vendor, status, duration, and checksum. The complete report remains the native TradingAgents artifact.

## Failure behavior

- Provider/build/persistence failure before dispatch: mark run failed with `evidence_unavailable` and a safe message.
- Missing or invalid snapshot at the private service: return a signed-request rejection; the backend records `service_rejected`.
- Optional evidence sections may be empty only when represented in `dataGaps`; exact price history is mandatory.
- No code path silently falls back to an unverified current Yahoo snapshot for a HOSE run.

## Verification

- Backend unit tests prove historical cutoff, adjusted price use, deterministic technical data, write-once persistence, resume reuse, and safe failure codes.
- Private-service tests prove checksum/symbol/cutoff validation, bounded formatting, non-Vietnam isolation, context injection, and provenance events.
- Vendored TradingAgents prompt tests prove DataVest evidence precedence is conditional and does not change ordinary stock behavior.
- Existing route, callback, full-graph, Crypto, Gold, and TradingAgents regression suites remain green.
