# Data sources and provenance

## Observed ingestion — 6 November 2026

A user-triggered source refresh in the running Docker application successfully loaded all four configured municipal feeds:

| Feed | Loaded records | Meaning |
|---|---:|---|
| Traffic incidents | 60 | Bounded selection of municipal point notices; not certified closed road edges |
| Loading reserves | 350 | Bounded inventory; no live occupancy or availability |
| Camera catalogue | 357 | Published camera locations and linked periodic stills |
| Traffic measurements | 3,591 valid | 1,800 geolocated readings sampled for the browser; not complete mapped coverage |

The sensor download timestamp was **2026-11-06 11:21:21 UTC**. An observation timestamp was not available in this snapshot. Download time is not a claim about when each measurement was observed. Counts and feed availability may change.

The incident evidence view returned nearby sensors/cameras for incident `2026/883`. One linked camera image loaded at 1280 × 720 through the guarded backend proxy; opening and closing it did not modify the plan. The application does not claim every camera URL is available.

## Configured source catalogue

| Dataset | Official catalogue | Format / fallback |
|---|---|---|
| Traffic incidents | [202062 — public-road incidents](https://datos.madrid.es/dataset/202062-0-trafico-incidencias-viapublica) | XML |
| Camera positions and stills | [202088 — traffic cameras](https://datos.madrid.es/dataset/202088-0-trafico-camaras) | KML with published image URLs |
| Loading reserves | [208072 — loading/unloading reserves](https://datos.madrid.es/dataset/208072-0-carga-descarga) | 2026 GeoJSON inventory; allowlisted CSV fallback |
| Traffic measurements | [202087 — traffic intensity](https://datos.madrid.es/dataset/202087-0-trafico-intensidad) | XML; official [Informo mirror](https://informo.madrid.es/informo/tmadrid/pm.xml) |

Exact configured download URLs and parsers live in `backend/app/integrations/madrid.py`. Geographic conversion uses pyproj where the source supplies projected coordinates. Invalid/missing measurements are not replaced with invented observations.

## Interpretation boundaries

- Source refresh is explicit, with backend cooldown and optional five-minute browser auto-refresh.
- API reads of the local cache do not download municipal feeds.
- Distributions and congestion counts use the mapped sample where labelled; they do not imply full-city coverage.
- A nearby municipal notice is geographic evidence, not a route closure or measured delivery delay.
- Camera images are periodic stills, not continuous video or computer vision inference.
- Loading reserves are locations, not available parking spaces.
- The synthetic fleet remains synthetic in municipal-data mode.

## Attribution

Source: **Ayuntamiento de Madrid, Portal de Datos Abiertos**. Retain source/date labels and distinguish transformed visualizations from the original data. See [municipal reuse conditions](https://datos.madrid.es/pages/condiciones-de-uso), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) and the [third-party notices](third-party-notices.md).

Map tiles, OpenStreetMap data, road routing and model providers have separate terms. [Provider usage and budgets](API_BUDGET.md) explains request triggers and account limits without promising a free allowance or SLA.
