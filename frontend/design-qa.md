# Smart Insights economic calendar design QA

## Source visual truth

- Reference screenshot: `C:\Users\ASUS\AppData\Local\Temp\codex-clipboard-1302be69-63d5-445c-a4b5-87fec33f1c09.png`
- Intended viewport: 887 × 807 px
- Intended state: light theme, Vietnamese labels, grouped economic events with actual / forecast / previous values

## Implementation target

- Route: `http://127.0.0.1:8010/#/smart-insights`
- Browser evidence: `output/playwright/smart-insights-auth-gate.png`
- Browser viewport: 887 × 807 px

## Fidelity surfaces

- Dense seven-column table: time, currency/flag, event, importance, actual, forecast, previous
- Date-group rows with compact borders and centered date labels
- Three-star importance indicator with high / medium / low filtering
- Source-backed value tones for positive and negative surprises
- Responsive horizontal scroll for the dense table on narrow screens
- Vietnamese and English locale strings for table labels and states

## Comparison history

1. Source screenshot inspected at 887 × 807 px.
2. Source-backed calendar loading, normalization, sorting, grouping and filter behavior implemented.
3. Production build and unit contracts passed.
4. Host-local browser reached the route, but the clean browser context was redirected to `/user/login?redirect=%2Fsmart-insights`; no authenticated session was supplied, so the rendered target table could not be captured for the required source-vs-implementation visual comparison.

## Result

final result: blocked

Blocker: authenticated Smart Insights browser state is required to capture the actual table and complete pixel-level visual comparison. No authentication bypass or demo data was introduced.
