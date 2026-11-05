# Verified source catalogue — 03 November 2026

Source pages and downloads were checked via published official documentation. **Network retrieval of source bytes and API key quota enforcement have not been tested from the build environment**; this is why the app has an explicit Demo/Live split.

| Dataset | Exact resource URL / portal | Format | Authentication | Cadence | Limitations |
|---|---|---|---|---|---|
| Traffic incidents | https://datos.madrid.es/dataset/202062-0-trafico-incidencias-viapublica/resource/202062-0-trafico-incidencias-viapublica/download/202062-0-trafico-incidencias-viapublica.xml | XML | No | Approx. 5 min | Includes construction, accidents, events; **not necessarily precise road-link geometry** |
| Fixed traffic camera locations | https://datos.madrid.es/dataset/202088-0-trafico-camaras/resource/202088-0-trafico-camaras/download/202088-0-trafico-camaras.kml | KML + images referenced | No | Snapshots ~5 min | Still photos, **not video**; some URLs may not be accessible or parseable |
| Loading/unloading reserves (2026) | https://datos.madrid.es/dataset/208072-0-carga-descarga/resource/208072-0-carga-descarga-geo/download/208072-0-carga-descarga-geo.geo | GeoJSON | No | Monthly | Locations, some schedules. **No reliable real-time bay availability** |
| Sensor measurements | https://datos.madrid.es/dataset/202087-0-trafico-intensidad/resource/202087-0-trafico-intensidad/download/202087-0-trafico-intensidad.xml | XML | No | Approx. 5 min | Point occupancy/intensity, **not per-road driving time** |
| Location of traffic sensors | https://datos.madrid.es/dataset/202468-0-intensidad-trafico | CSV/geo resources | No | Monthly | Useful when interpreting sensor IDs |
| Events | https://datos.madrid.es/dataset/300107-0-agenda-actividades-eventos | GeoJSON/JSON/CSV | No | Daily | Cultural agenda: not an exhaustive catalog of road restrictions |
| Low emission zone cameras | https://datos.madrid.es/dataset/300654-0-circulacion-camaras-trafico | dataset | No | irregular | **Camera placement is not legal routing authorization**; consult official regulations |

### Licensing

Madrid dataset pages identify **Creative Commons Attribution 4.0 International (CC BY 4.0)**. Cite Ayuntamiento de Madrid as source, retain dates, do not imply municipal endorsement, and do not distort data. Reuse terms: https://datos.madrid.es/ . Other providers (OSM, tiles, routes, Gemini) have **separate terms and quotas**.

### Intended MVP source set

- `incidents`: `fetch_source('incidents')` downloads and parses XML with guarded tags, latitude/longitude and optional ETRS89 UTM via pyproj.
- `loading`: GeoJSON points from municipal 2026 inventory, included if geographic coordinates valid.
- `cameras`: KML placemark coordinates; images shown **only if an allowed official HTTPS source is verified**. The initial UI intentionally shows no fake camera image.
- All sources: hold in memory, refresh only on explicit user action with 240-second global cooldown. Errors are returned individually, no silent 'LIVE' substitution.

### API quotas, as of source check

| Service | Public/free availability | Quota / condition |
|---|---|---|
| Madrid downloads | Free open downloads; no API key | No single universal published calls/day cap found. Poll politely once per update cycle; not once per visitor. |
| OpenFreeMap | Hosted vector tiles without key | Free public service with provider policy; not a business SLA, no automatic mass downloads. |
| HeiGIT OpenRouteService | Standard free tier with registered key | Published examples: Directions ~2,000/day, Matrix/Optimization ~500/day; confirm endpoint-specific rates **in your account** before use. |
| Google Gemini API | Selected models on eligible free projects | Limits **per project and model**: RPM, TPM and RPD. View https://aistudio.google.com/rate-limit . Token prices/pricing https://ai.google.dev/gemini-api/docs/pricing . Free-tier inputs may be used to improve products. |
| GroqCloud | Free usage for certain models | Example `openai/gpt-oss-20b`: base 30 RPM, 1,000 RPD, 8,000 TPM, 200,000 TPD on published plan. Confirm actual account caps at https://console.groq.com/docs/rate-limits . |

Do not interpret **free** as **unlimited**. API behaviour can change. Request access requires clicking through provider account and accepting its terms.

### Additional product hypotheses worth exploring later

**EventOps:** merge verified cultural event locations and traffic incidents to highlight impact to a scheduled services fleet, with explicit distinction between event and road closure.

**Fleet ZBE compliance:** vehicle environmental category and municipal low emission rule knowledge, with a separate legal rules engine. No ZBE decision should rely only on OCR camera locations.

**Curb-space intelligence:** recommend legally eligible loading bays by schedule and vehicle size. This requires more reliable per-bay metadata. Do not present bay occupancy without an official provider.

**Camera evidence workspace:** location-based indexing of traffic camera snapshots around an incident, clearly showing source, time and potential mismatch between camera and incident location.


## v0.5 measured traffic sensor integration

- `GET /api/signals`: currently cached **observed** sensor readings, never fictitious entries.
- Official traffic XML: https://datos.madrid.es/dataset/202087-0-trafico-intensidad/resource/202087-0-trafico-intensidad/download/202087-0-trafico-intensidad.xml
- Official direct Informo mirror, if dataset resource fails: https://informo.madrid.es/informo/tmadrid/pm.xml
- Source catalogue metadata: https://datos.gob.es/es/catalogo/l01280796-trafico-datos-del-trafico-en-tiempo-real
- Raw fields: `idelem`, `intensidad`, `ocupacion`, `velocidad`, `nivelServicio`, `st_x`, `st_y`. EPSG:25830 conversion with pyproj to WGS84. Invalid negatives ignored.
- `GET /api/signals`: returns valid total plus max 1,800 sampled geolocated sensor points to bound browser memory; counts in distribution apply to the **mapped sample**, not the full raw feed. The UI makes this explicit.
- If direct municipal URLs return failures, backend returns feed-specific errors and the UI keeps showing empty live observations. Never label demo vehicle data live.
- Some official datasets redirect or require additional access handling. Source bytes could not be verified from the offline build sandbox, so do not claim working 2026 integration until tested on developer machine.


## v0.6 verified official changes
- Reserves 2026 GeoJSON distribution: `https://datos.madrid.es/dataset/208072-0-carga-descarga/resource/208072-0-carga-descarga-geo/download/208072-0-carga-descarga-geo.geo` (catalogued on the municipal and datos.gob.es portals). This replaces an older/incorrect filename. Actual remote response must be tested from the user's WSL machine.
- Traffic cameras municipal KML publishes locations and image snapshots (typically ~5 min). Some camera image links historically use `http://informo.munimadrid.es/cameras/Camara*.jpg`; the server-side image proxy checks URL hosts, image magic bytes and response size. If unavailable, display source error rather than fabricated imagery.
- Municipal sensor heatmap is a visualization of **sampled real readings**, not proof of street-level congestion along a route.
