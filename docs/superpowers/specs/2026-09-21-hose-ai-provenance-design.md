# HOSE AI discovery and data-provenance design

Date: 2026-09-21
Status: Design for user review

## Purpose and scope

An investor should be able to find any active HOSE equity/ETF by ticker, company name, or Vietnamese alias; ask DataVest Copilot about it; and understand exactly which observations supported the answer. Fast Analysis and TradingAgents reports must display the same market identity and data-coverage truth. The product remains research/paper-investing-only and uses the existing free VNDIRECT/Yahoo path. No broker execution or paid feed is added.

This work covers the Copilot asset picker and watchlist search, Copilot research context and prompts, Fast Analysis result and UI, and the HOSE TradingAgents report/view. It does not add HNX/UPCoM, change US/Crypto/Forex analysis policy, or promise real-time VN prices. Historical reports are not rewritten; they may show provenance as unknown when it was not captured.

## Decision

Keep `market=VNStock` as the application market key and use `exchange=HOSE` as an explicit filter and display value. Use the authoritative active HOSE rows in `qd_market_symbols` plus `qd_market_symbol_aliases`; do not introduce a second `HOSE` market key or a hand-maintained list of eligible tickers. This preserves existing analysis and watchlist interfaces while making exchange identity explicit.

Rejected alternatives: a separate `HOSE` market key would force broad interface and history migrations; a UI-only HOSE label would leave Copilot resolution and evidence scoring inaccurate.

## Symbol discovery and validation

1. The HOSE catalog remains authoritative for AI eligibility. Search returns only active HOSE equity/ETF rows satisfying the same provider freshness/validation rules as `get_active_hose_symbol`; an inactive, delisted, or absent ticker cannot be analyzed even if a legacy alias mentions it. Search failure is an empty/unavailable state, not a guessed ticker.
2. Extend the current `/api/market/symbols/search` request with optional `exchange=HOSE`. `VNStock` results include `exchange`, `asset_class`, `name`, and `symbol`; existing clients may omit `exchange`. The Copilot HOSE filter sends `market=VNStock&exchange=HOSE`. Preserve current `VNStock` storage values for selections and history.
3. Normalize Unicode Vietnamese text for matching: case-fold, trim/collapse whitespace, and remove accents for a secondary search key. The catalog sync creates a normalized alias from each provider company name; curated aliases remain supplemental and cannot create an eligible instrument. Search ranking is exact ticker, ticker prefix, exact name/alias, then partial name/alias. Limit results and return an unambiguous stable symbol identity.
4. Copilot entity resolution queries the symbol master with candidate ticker tokens and Vietnamese phrase windows rather than expanding five hard-coded VN aliases. It validates the chosen HOSE target before fetching evidence. An explicit UI selection or `HOSE:FPT` wins over ambiguous prose; if two plausible active targets remain, ask which company the user means instead of silently using the first one. US company aliases stay in their existing path.

## Evidence and provenance contract

The existing Vietnam Evidence DTO remains the factual payload: `instrument`, `price`, `technical`, `fundamentals`, `corporateActions`, `disclosures`, `marketContext`, `dataGaps`, and `sources`. Add a small, shared presentation-ready provenance object to the HOSE result/response envelope, derived from observations rather than authored by the LLM:

| Field | Meaning |
| --- | --- |
| `exchange`, `currency` | `HOSE`, `VND` for validated HOSE instruments. |
| `source` | Actual provider used for that price/observation, e.g. VNDIRECT or Yahoo; never an assumed primary provider. |
| `observedAt` | Market observation/bar timestamp when supplied and valid. |
| `fetchedAt` | Server retrieval time, separately labelled; it is not market time. |
| `latencyClass` | `real_time`, `delayed`, `eod`, or `unknown`. |
| `delayMinutes` | Only when the provider supplies a verified delay value. |
| `available`, `dataGaps` | Which report inputs exist and coded reasons for absence. |

Daily historical bars are `eod`. A live quote is `real_time` or `delayed` only when provider metadata/contract explicitly supports that claim; otherwise it is `unknown`, regardless of how recently it was fetched. Missing timestamps remain null. Time is stored in UTC and rendered in the user's locale/time zone with the underlying zone visible on hover/detail. `asOf` and point-in-time `availableAt` rules already in Vietnam Evidence remain authoritative for fundamentals/events; no later filing may leak into a historical report.

Each response/report lists sources per data family (price, statements, news/disclosures) and separates `missing`, `unavailable`, and `not requested`. If a source fails, no source or freshness label is fabricated. The data-coverage section is constructed deterministically from the evidence and appended to stored TradingAgents output/PDF so it remains visible even if the model omits it.

## Copilot and scoring behavior

The Copilot system prompt gets a market-specific HOSE policy when the validated target is `VNStock`/`HOSE`: prices are VND, Vietnam session/filing context applies, US-specific assumptions must not be imported, and every claim about financial statements or news needs a matching supplied observation/source. When statements or news are absent, answer with the exact gap and a conditional analysis from the available evidence; do not fill financial metrics, headlines, or corporate events from general model knowledge. If even price/technical evidence is absent, return an insufficient-data result instead of a directional verdict.

For HOSE Fast Analysis, an unavailable technical, fundamental, sentiment, or macro component is represented as unavailable/null with a reason, never a neutral `50`. The overall objective score uses only eligible observed components with renormalized existing weights; if none are eligible, the overall score and decision are unavailable. A score computed from a subset carries a visible coverage indicator and the omitted components. Model confidence is distinct from objective score and must not be defaulted to 50 solely because parsing or evidence failed. Preserve numeric legacy behavior for non-HOSE markets unless needed for rendering null safely.

## UI and report behavior

- Add a visible `HOSE` filter to Copilot symbol search/watchlist selection, without changing the stored `VNStock` market key. Symbol options and selected context show ticker, company name, and `HOSE`.
- For HOSE quote, plan levels, and report prices, render `VND`, never `$`. Show actual source, market observation time, retrieval time, and one of `Real-time`, `Delayed`, `EOD`, or `Chưa xác định`; never infer real-time from a recent fetch.
- Fast Analysis score cards render `Không đủ dữ liệu` for null components and do not draw a numeric progress ring for a missing overall score. The report lists inputs used and gaps. A partial overall score is visibly labelled partial.
- Copilot answer cards and TradingAgents report/view expose the same HOSE data-coverage/provenance fields. The TradingAgents PDF includes a deterministic data-coverage appendix; unsupported items such as foreign room/ownership stay explicitly missing.
- Existing US/Crypto/Forex labels and price formatting remain unchanged.

## Failure handling and verification

Provider/catalog failure fails closed for new HOSE analysis; a known catalog row with a failed quote yields a named data gap rather than a synthetic price. UI search errors do not create a manually typed HOSE target. Missing news is reported as a news gap, not as proof that no news exists. Empty statements are not interpreted as zero revenue/earnings. Old saved reports lacking provenance show `Không rõ nguồn/thời điểm`, not `Real-time`.

Implementation tests will cover: every active HOSE catalog ticker eligible without a handwritten list; diacritic and accentless company-name search; curated alias search; inactive/delisted rejection; ambiguous entity handling; US alias regression; provider metadata to latency-class mapping including unknown; no fabricated BCTC/news in Copilot prompts and fallback paths; null scores and partial coverage; VND/exchange/source/time rendering in Copilot and Fast Analysis; TradingAgents HTML/PDF coverage; and existing non-HOSE behavior. Verification uses fixtures/mocks for free providers and a separately labelled live-provider smoke test when connectivity is available. No production deployment is implied by passing local tests.
