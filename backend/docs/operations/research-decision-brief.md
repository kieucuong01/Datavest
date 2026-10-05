# Research decision brief

The default research view presents four compact sections: changes from a prior
report, supporting/counter evidence, risks, and thesis invalidation conditions.
Horizon and next observations are included. The full PDF and frozen HOSE evidence
remain available through the full-report view.

## Content contract

- Extract only the final Portfolio Manager section of the same complete report.
  Analyst recommendations must not override the final decision.
- The existing native Portfolio Manager call supplies optional, bounded evidence,
  risk, invalidation, scenario and next-watch lists. No extra AI request is added.
- Reports produced before this change may lack these lists. Show the missing
  sections explicitly; do not manufacture evidence, thresholds or probabilities.
- Evidence is a report claim. Show its original link when supplied, otherwise
  mark that no original link was supplied. Never label it provider-verified.
- Compare only completed, strictly earlier reports for the same asset, report
  kind and language. Missing prior data is not evidence of no change. Differences
  in risk wording are not proof of newly emerged or resolved risks.
- Weekly validity follows the evidence period, not a later publication time.
  Expired reports require reassessment. Validity does not prove that invalidation
  conditions have not occurred.

## Access and PDF consistency

Guest comparison is limited to the existing fixed public asset scope. Shared
watchlist comparison and dated PDFs recheck current membership on the server.
Private comparison reads artifacts through the existing owner-scoped run API.
Responses retain the existing public/shared payload allowlists.

Public/shared PDFs include the effective date of the displayed brief. Private
PDFs use that run's ID. New publication must not silently substitute a different
period when the reader opens the full report. These are read paths; opening the
brief or comparing periods does not create a run or enqueue paid analysis.

## Validation and release

SQLite-backed period tests cover asset, kind, locale, status and cutoff selection;
service tests cover membership removal and safe projection. Frontend tests cover
final-manager extraction, missing fields, unsafe links and artifact selection.
Local browser acceptance uses clearly marked synthetic content. This is not
production market/provider or authenticated end-to-end verification.

No migration is required for the added optional report fields or read queries.
Existing reports are not regenerated automatically. Deploy the API, frontend and
native TradingAgents code together; new runs receive the richer final decision.
