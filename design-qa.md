# Smart Insights visual QA

- Source visual truth: `C:\Users\ASUS\AppData\Local\Temp\codex-clipboard-76381522-89e0-4be3-8b93-e149c5597b99.png` and `C:\Users\ASUS\AppData\Local\Temp\codex-clipboard-87337eb2-9233-4a5f-b2ff-4cf58da02208.png`
- Intended implementation: `http://localhost:8888` → Smart Insights → Tổng quan/Tâm lý.
- State: Vietnamese locale, source-backed historical Alternative.me data.
- Flow Terminal visual truth: `C:\Users\ASUS\AppData\Local\Temp\codex-clipboard-844c3773-acf0-4268-861b-547dddc9601f.png` and `C:\Users\ASUS\AppData\Local\Temp\codex-clipboard-f13b6b29-4b99-47bf-9d9f-2f78bbeb6132.png`.
- Flow Terminal implementation: `http://localhost:8888` → Smart Insights → Dòng tiền.
- Cycle Terminal visual truth: `C:\Users\ASUS\AppData\Local\Temp\codex-clipboard-b216c768-3c4e-4704-b4d2-223774836707.png`.
- Cycle Terminal implementation: `http://localhost:8888` → Smart Insights → Chu kỳ.
- Cycle data scope: BlockchainCenter Altcoin Season history from 2017-02-01 and CBBI history from 2011-06-27, including Confidence plus nine imported component series.

## Findings

- [Blocked] Browser-rendered implementation capture is not available in this Codex Desktop session, so a same-viewport visual comparison cannot be made.
  - Evidence: frontend production build, local HTTP smoke, and component contract tests passed; no browser screenshot or console capture tool is available in this session.
  - Required follow-up: capture the authenticated Smart Insights view at desktop width and compare it with all supplied references before claiming visual-fidelity completion.

## Implementation checklist

1. Render a library-backed semi-circular gauge with the 0–100 sentiment palette.
2. Render Now, Yesterday, Last week, and Last month source-backed values.
3. Render an interactive 7D/1M/3M/1Y/Max ECharts history line with hover tooltip.
4. Keep the full validated Alternative.me history available to those controls.
5. Render a Flow Terminal with a selectable asset rail, source-backed net-flow KPIs, positive/negative flow bars, cumulative mode, range controls, a horizontal detail table, and a summary panel.
6. Do not show AUM, issuer attribution, or performance figures until those fields are supplied by the source API.
7. Render an interactive Altcoin Season history with the provider's Bitcoin/Altcoin threshold zones, provider-backed season statistics, and 90D/1Y/All controls.
8. Render CBBI Confidence and each imported CBBI component as selectable, interactive historical series.

## Verification performed

- Frontend static component tests pass.
- Backend contracts pass.
- Flow API snapshots contain 13 CryptoETF assets and the runtime read-model exposes all 13.
- Local frontend and backend HTTP endpoints return 200.
- Browser Use snapshot import completed: 10,066 Altseason and 55,059 CBBI records were parsed; the local import run succeeded with 65,125 records fetched and 10,069 new observations persisted.
- Runtime cycle payload exposes 3,419 Altseason index points from 2017 and 55,118 CBBI points across 10 metrics from 2011.

final result: blocked
