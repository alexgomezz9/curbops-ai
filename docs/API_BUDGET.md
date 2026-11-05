# External services and request budgets

CurbOps runs without LLM credentials or a GPU. Map tiles and optional street routing require network access. Provider credentials are backend-only and are supplied through an untracked `.env` file.

| Service | Purpose | Request trigger | Limitation |
|---|---|---|---|
| Madrid Open Data | Incident, sensor, camera and loading-zone catalogues | Explicit source refresh; optional five-minute auto-refresh | Backend cooldown; source-specific failures and timestamps |
| OpenFreeMap | Browser vector tiles and map styles | Map load, pan and zoom | External availability; no application SLA |
| OSRM demo | Street geometries and road-cost matrices | Explicit routing/planning action | Noncommercial demonstration; process-local request pacing |
| OpenRouteService | Optional alternative road provider | Explicit routing/planning action | Account key and account-specific quotas |
| Google Gemini | Optional tool-calling agent | Operator investigation | Account/model-specific quotas and billing |
| Groq | Optional alternative tool-calling agent | Operator investigation | Account/model-specific quotas and billing |

## Request accounting

A municipal refresh can make one request per feed, plus fallback requests on failure. The default backend cooldown is 240 seconds; optional browser auto-refresh is 300 seconds. Browser reads of the backend cache do not download municipal data.

Opening a camera requests a still image through the guarded backend proxy. The selected still can refresh every five minutes. This is not a video stream.

A planning request can require matrices, baseline and proposed route geometries, and bounded alternative-route checks. Cache hits reduce requests. A failed external call does not authorize an illustrative fallback or an invented successful result.

One model invocation and one tool call are different events. An investigation may require several model requests; local tool execution is not itself another model request. Token usage is displayed only when reported by the provider.

## Deployment limits

No fixed free allowance or spend figure is promised. Check the selected account's billing tier and current model/endpoint quotas before enabling a provider. Public multi-user use requires authentication, isolated state, request limits and shared provider budgets; those are not implemented by this single-user prototype.

Official service information: [Madrid](https://datos.madrid.es/), [OpenFreeMap](https://openfreemap.org/), [OSRM](https://project-osrm.org/), [OpenRouteService](https://openrouteservice.org/), [Gemini](https://ai.google.dev/), [Groq](https://console.groq.com/docs/).
