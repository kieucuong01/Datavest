# HOSE Copilot parity design

## Goal

Make AI Copilot and Fast Analysis use the same market-neutral research pipeline for
USStock and VNStock. The market adapter supplies the evidence; resolution,
coverage gating, scoring, report serialization and UI rendering remain shared.

The product remains research-only. It does not add broker execution, paid data,
or claim that free Vietnamese data is real time when it is EOD or delayed.

## Current problem

The HOSE path has an authoritative symbol-master resolver and a Vietnam Evidence
DTO, but it diverges into a reduced report. It can expose a fundamental score
despite missing evidence and client-side aliases still special-case FPT and VCB.
This produces reports that look more certain than the available data permits and
are materially weaker than USStock reports.

## Chosen architecture

```text
Copilot request / Fast Analysis target
  -> canonical instrument resolution
  -> market evidence adapter
  -> shared coverage policy and scoring
  -> shared report contract
  -> shared Fast Analysis / Copilot renderer
```

### 1. Canonical instrument resolution

All Vietnamese free-text resolution occurs server-side against the active HOSE
symbol master and its generated aliases. The result is one of `resolved`,
`ambiguous`, or `none`; inactive, delisted and non-HOSE symbols are rejected.

The client may search/display matching symbols, but must not select a market from
a handwritten Vietnamese alias map. Existing US/crypto convenience aliases may
remain as UI hints only; the server remains authoritative.

### 2. Market evidence adapters

Introduce a narrow adapter boundary consumed by both Fast Analysis and Copilot:

```text
resolve(target, asOf) -> CanonicalInstrument
collect(instrument, asOf) -> ResearchEvidence
```

`ResearchEvidence` is market-neutral and contains instrument, price, technical,
fundamentals, corporate actions, disclosures, news, market context, per-field
coverage and provenance. Existing USStock collection is wrapped without changing
its external report payload. VNStock maps the existing Vietnam Evidence DTO into
the same shape, with VNDIRECT as the free fundamental/event provider and Yahoo as
the bounded OHLCV fallback.

Every Vietnam observation keeps `period_end`, `available_at`, source and latency
class. An unavailable provider or missing field is evidence of absence, not a
default value.

### 3. Coverage-aware scoring

Each score dimension declares its required evidence fields. A dimension is:

- `available` only when all required evidence is present and fresh enough;
- `partial` when it has useful but incomplete evidence; or
- `unavailable` when no defensible score can be produced.

`partial` and `unavailable` dimensions have a null score; they cannot be converted
to 50 or 100. The overall decision and entry/stop/take-profit levels are emitted
only when their own prerequisites are satisfied. The report always carries the
coverage decision and explicit reasons.

### 4. Shared report/UI contract

Fast Analysis and Copilot consume the existing report shape plus a normalized
`coverage` block. The renderer uses one presentation path for USStock and
VNStock, with market-specific labels only for currency, exchange, session and
provenance. It shows each missing section as unavailable rather than hiding it or
presenting a neutral score.

The Copilot prompt receives the same normalized evidence and coverage decision.
For HOSE, it must not assume USD, SEC filings, US session conventions, or fabricate
BCTC/news/ownership data.

## Error handling

- Ambiguous Vietnamese company names return candidates and request selection.
- A stale or EOD quote remains usable only with its latency label; it cannot be
  presented as real time.
- A VNDIRECT/Yahoo failure preserves last known persisted evidence, records the
  provider gap and never switches to invented values.
- News, foreign room, ownership and filing scope remain explicitly unavailable
  until a verified free source has been ingested.

## Acceptance criteria

1. Any active HOSE symbol is resolved by code, company name, accentless name or
   stored alias without a handwritten FPT/VCB special case.
2. A VNStock report uses the shared report/coverage contract and labels VND,
   HOSE, source, observation time and latency.
3. Missing BCTC/news/ownership yields `partial` or `unavailable`, never a 50/100
   dimension score or an unsupported action level.
4. USStock/Crypto report contract and scores remain regression-compatible.
5. Tests cover resolver behavior, coverage/scoring gates, prompt projection and
   rendered HOSE gaps with deterministic provider fixtures.

## Verification

- Focused Python tests for resolver, evidence adapter, Fast Analysis scoring and
  Copilot routes.
- Focused frontend unit tests for symbol resolution and coverage rendering.
- Production build and a read-only production smoke of symbol search, health and
  an existing HOSE report; do not generate an LLM report merely for smoke testing.
