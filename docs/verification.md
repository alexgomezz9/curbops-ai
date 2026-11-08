# Release verification — 6 November 2026

This record separates automated checks, live integrations and operator actions for CurbOps AI.

## Automated and runtime checks

| Check | Observed result |
|---|---|
| Backend `python -m pytest -q` | **103 passed**, including LangGraph tests; no skipped graph module |
| Frontend TypeScript / production Next.js build | Passed locally and in the rebuilt Docker image |
| `npm audit` | **0 vulnerabilities** after remediation, including development dependencies |
| Docker Compose | API/web built and started; API health check passed |
| Read-only `scripts/smoke.sh` | Passed against the running Compose API |
| No-key demo | Separate container with no Google/Groq keys returned `deterministic_demo`, no proposal and three read tools; temporary container was stopped |
| Markdown render checks | Headings, first/subsequent bullets, escaped emphasis, inline code and HTML escaping passed |
| Approval-trace render checks | All three proposal tools display decisions; a matching approved-plan fixture displays approval; read-only fixtures do not inherit a decision |

Backend tests use fake outbound providers. The live checks below are separate observations.

## Live browser and provider evidence

Desktop Chromium, light theme, 1920 × 1080 viewport. Full-page screenshots retain content and map attribution rather than clipping the page to a fixed height.

| Flow | Observed result |
|---|---|
| Municipal source refresh | All four configured sources connected: 60 incidents, 350 loading reserves, 357 cameras, 3,591 valid traffic readings; 1,800 geolocated sensor points mapped |
| Incident investigation | Incident `2026/883` returned nearby observations; geographic join remained read-only |
| Camera still | A linked 1280 × 720 image loaded through the backend proxy and closed without changing the plan |
| Gemini proposal | `llm_tool_agent`; actual preparation, audit, comparison and map tools executed; nine route-progress events observed |
| Read-only fleet review | Actual three-node LangGraph completion events; plan ID/generation unchanged |
| Vehicle/scenario targeting | V-02/B selected after explicit request; B footer and B evidence matched; composer cleared |
| Preventative whole-fleet request | Current request retained ALL scope despite previous vehicle/incident focus; all three vehicle outcomes returned |
| B/C visibility | Provider-backed reference/candidate comparison and map fit exercised without requesting another optimization |
| Human approval boundary | Pending proposal/button inspected; subsequent read-only requests returned no proposal and showed no approval button. After explicit operator authorization, Swagger UI submitted that exact synthetic plan and returned HTTP 200; a separate mission read confirmed its approved status |

### Synthetic planning results

| Scenario | Road km | Base minutes | Stops |
|---|---:|---:|---:|
| A | 50.65 | 113.5 | 15 |
| B | 29.01 | 67.6 | 15 |
| Initial C | 29.01 | 67.6 | 15 |
| Preventative C | 30.37 | 70.0 | 15 |

Initial B/C were identical. A later explicit hypothetical-avoidance request verified **one partial bypass for V-01**, avoiding the buffer around notice `2026/1832` while leaving `2026/1833` unresolved. It added 1.36 km and 2.4 base minutes. V-02 and V-03 had no accepted bypass. Five selected notice buffers remained unresolved across the fleet.

The provider returned the accepted street geometry; the application checked required stops, buffers and budgets. This is not proof of a real closure or observed business savings. Provider checks include cached responses; they are not a count of unique external HTTP requests.

The recorded summary's congested-point counts were checked against the structured C traffic endpoint: V-01 = 13, V-02 = 5, V-03 = 4. These are counts, separate from weighted advisory scores.

One avoidance run completed its tools but returned no readable model summary; the UI reported that explicitly. A subsequent read-only request summarized the existing result without changing the plan. Model prose should be checked against structured outputs: the sensor advisory score is a weighted sum of service levels, not a sensor count.

The observability captures use a read-only investigation of the existing C result. It emitted actual model/tool and LangGraph events, preserved the plan ID/generation, returned no proposal, and displayed no approval button.

The operator subsequently authorized approval of synthetic plan `precaution-d13500a8a`. The request was submitted through the real FastAPI Swagger interface, and `GET /api/mission` confirmed the same ID in `approved_plan` with status `approved` and `simulation: true`. No dispatch was performed. This verifies the live approval endpoint through Swagger; the original frontend approval button was inspected, not clicked in this release check.

## Corrected defects

- Replaced vulnerable MapLibre/PostCSS versions; configured MapLibre 6's ESM worker URL for Next.js. The worker-loading error was reproduced before correction; the corrected map rendered with no JavaScript console errors during the checked flow.
- The map footer now recognizes a loaded road baseline before any proposal exists.
- Markdown emphasis and the first item of a list render without stray markers.
- The execution view recognizes dispatch, preventative-avoidance and rehearsal proposals rather than only dispatch preparation.
- The workflow catalogue now includes all 22 backend tools, including preventative avoidance, incident rehearsal and scenario metrics. The frontend production Docker build and type checks passed after this update. In Chromium, all 22 nodes fit in the expanded light-theme graph; 3 tools were actually used across 4 calls, while 19 remain explicitly uncalled.

## Application screenshots

The README gallery contains eleven real desktop captures: overview, operations map, incident investigation, route comparison, full tool catalogue, fullscreen copilot, City Signals, camera explorer, camera selection on the operations map, incident details on the map and the AI Agent workspace. The execution timeline's four tool outputs are expanded in the workspace capture. The additional read-only investigation preserved plan `precaution-d13500a8a` and generation `3`.

Camera screenshots display successfully loaded municipal stills (1280 × 720 in the explorer and 960 × 576 from the operations map), with source labels and map attribution visible. No camera availability beyond these checked images is implied. Video files are excluded from the published tree.

## Security and rights

The final frontend tree uses MapLibre **6.16.0**, PostCSS **8.5.32** via an explicit override and Next.js **15.5.29**. The override patches the transitive dependency without introducing a Next.js major migration. `npm audit` reports no known advisories at the time checked; this is not a guarantee against future advisories or application-level flaws.

The private `.env` is excluded and preserved. Historical/current source scans check configured credential values and common key patterns without printing them. Generated browser state, raw traces, caches and private working documents are excluded from deliverables.

The source code is published with all rights reserved. Third-party components and data retain their own licences. See [third-party notices](third-party-notices.md).

## Remaining limits

- The successful live approval used Swagger UI rather than the frontend approval button. Matching/stale approval contracts are covered by backend tests, and the UI rendering states are covered by fixture checks.
- ORS, Groq, Safari/Firefox, a public deployment, concurrent users and sustained failure/load scenarios were not exercised live.
- No authentication, durable audit or multi-user isolation. The supplied Compose ports are host-published; use a trusted local development machine.
- Public feeds and routing may change or fail. No universal successful bypass, complete sensor coverage or model-answer accuracy is promised.

## Re-run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
(cd frontend && npm ci)
./scripts/verify.sh
./scripts/smoke.sh
```

See the [operator guide](demo.md) and [latest CI](https://github.com/alexgomezz9/curbops-ai/actions/workflows/ci.yml). Actual desktop screenshots are in [`media/screenshots/`](../media/screenshots/).
