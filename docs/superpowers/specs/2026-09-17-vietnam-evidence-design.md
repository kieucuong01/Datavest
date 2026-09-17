# Vietnam Evidence Design

## Goal

Provide one source-backed, point-in-time evidence contract for HOSE equities that is consumed by Fast Analysis and AI Chat. VNDIRECT is the primary free source for the HOSE catalog, financial statements, company profile, events and disclosures. Yahoo Finance remains a price-only fallback.

## Contract

`VietnamEvidence` contains `instrument`, `price`, `technical`, `fundamentals`, `corporateActions`, `disclosures`, `marketContext`, `dataGaps`, and `sources`.

Every fundamental observation carries `metric`, `value`, `unit`, `periodEnd`, `availableAt`, `frequency`, `reportScope`, `source`, `sourceUrl`, and revision metadata. Evidence builders exclude observations with `availableAt` after the requested `asOf` time.

## Components

- `VndirectProvider` normalizes free VNDIRECT financial statement, financial model, company profile, and event responses. Provider failures remain isolated and result in explicit data gaps.
- `VietnamEvidenceService` validates active HOSE instruments, applies point-in-time filtering, derives compatible percentage-point metrics, collects VNINDEX/VN30 context, and emits the shared DTO.
- `MarketDataCollector` attaches the DTO to VNStock results and maps its fundamental/company fields into the legacy shape needed by Fast Analysis.
- AI Chat inserts the same DTO into `research_context`, replaces search-only fundamentals for VNStock, and rejects inferred VN symbols that are not active HOSE targets.
- PostgreSQL stores normalized financial observations and events with source identity, availability time, revision time, and raw metadata. Persistence is best-effort during analysis; provider or database failure never fabricates data.

## Data policy

- Price data: VNDIRECT primary, Yahoo `.VN` fallback.
- Fundamental/event/profile data: VNDIRECT only unless a future verified free adapter is added.
- Foreign room and ownership are emitted as `dataGaps` until a verified free structured source exists.
- Search results may supplement news, but never become structured financial observations.
- Ratio units are explicit. ROE and growth exposed to legacy Fast Analysis use percentage points; debt-to-equity is a ratio.

## Failure behavior

Price remains mandatory for Fast Analysis. Missing optional evidence lowers completeness and is visible in `dataGaps`. Provider timeout, malformed rows, future-dated observations, unsupported report scopes, and unavailable foreign-room/ownership data are fail-soft and auditable through `sources` and gaps.

## Verification

Unit tests cover provider normalization, point-in-time filtering, report-scope preservation, ratio units, explicit data gaps, MarketDataCollector compatibility, AI Chat consumption, inferred-symbol validation, and price-provider provenance. Existing VN price, Fast Analysis scoring, and AI Chat tests remain green.
