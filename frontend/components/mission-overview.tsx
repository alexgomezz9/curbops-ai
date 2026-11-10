import { ArrowRight, ArrowUpRight, BrainCircuit, ChevronRight, Layers3, MapPinned, RefreshCw, Route } from 'lucide-react';
import type { ReactNode } from 'react';
import type { CitySignals, DispatchPlan, MissionSnapshot } from '@/lib/types';
import { fleetColor } from '@/lib/fleet-colors';

const count = new Intl.NumberFormat('en-GB');
const distance = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 1 });
const priority = { high: 0, medium: 1, low: 2 };

type Props = {
  mission: MissionSnapshot;
  baseline: DispatchPlan;
  signals: CitySignals | null;
  map: ReactNode;
  connected: boolean;
  roadAvailable: boolean;
  busy: boolean;
  loadingRoutes: boolean;
  loadingSources: boolean;
  comparisonLabel?: string;
  onMap: (vehicle?: string) => void;
  onCompare: () => void;
  onLoadRoutes: () => void;
  onInvestigate: () => void;
  onIncident: (id: string) => void;
  onIncidents: () => void;
  onSignals: () => void;
  onLoadSources: () => void;
};

export default function MissionOverview({
  mission, baseline, signals, map, connected, roadAvailable, busy, loadingRoutes, loadingSources,
  comparisonLabel, onMap, onCompare, onLoadRoutes, onInvestigate, onIncident, onIncidents, onSignals, onLoadSources,
}: Props) {
  const hasRoutes = baseline.routes.length > 0 && baseline.routes.every(route => route.fidelity === 'road_network');
  const notices = [...mission.incidents].sort((a, b) => priority[a.severity] - priority[b.severity]);
  const municipalNotices = notices.filter(notice => notice.provenance.origin === 'municipal_open_data').length;
  const hasReadings = signals?.status === 'municipal_open_data';
  const fetched = hasReadings && signals.fetched_at ? new Date(signals.fetched_at) : null;
  const fetchedLabel = fetched && Number.isFinite(fetched.getTime()) ? new Intl.DateTimeFormat('en-GB', {
    dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Madrid',
  }).format(fetched) : null;

  return <div className="missionOverview">
    <header className="missionIntro">
      <div>
        <div className="missionLocator"><MapPinned size={15} aria-hidden="true"/> Madrid, Spain <span/> Last-mile dispatch</div>
        <h1>Madrid fleet operations</h1>
        <p>Review the fleet, investigate disruptions and compare street routes before approving a dispatch plan.</p>
      </div>
      <button className="missionButton missionButtonPrimary" onClick={() => onMap()}>
        Open operations map <ArrowUpRight size={17} aria-hidden="true"/>
      </button>
    </header>

    <div className="missionBoard">
      <section className="missionMap" aria-labelledby="mission-map-title">
        <header className="missionPanelHead">
          <div><span className="missionEyebrow">Scenario A</span><h2 id="mission-map-title">Original dispatch</h2></div>
          <span className="missionTag"><span/>{hasRoutes ? 'Street routes' : 'Stop locations'}</span>
        </header>
        <div className="missionMapStage">{map}</div>
        <div className="missionMapLegend" aria-label="Street map symbols">
          <span><i className="missionLegendStop" aria-hidden="true"/> Delivery stop</span>
          {notices.length > municipalNotices && <span><i className="missionLegendScenario" aria-hidden="true">S</i> Scenario notice</span>}
          {municipalNotices > 0 && <span><i className="missionLegendNotice" aria-hidden="true">!</i> Municipal notice</span>}
        </div>
        <footer className="missionMapFoot">
          <div><strong>{hasRoutes ? `${distance.format(baseline.metrics.distance_km)} km` : `${count.format(mission.deliveries.length)} stops`}</strong>
            <span>{hasRoutes ? 'Estimated road distance' : 'Original delivery locations'}</span></div>
          {!hasRoutes && roadAvailable && connected && <button className="missionButton missionButtonQuiet" onClick={onLoadRoutes} disabled={busy}>
            <Route size={16} aria-hidden="true"/> {loadingRoutes ? 'Loading routes…' : 'Load street routes'}
          </button>}
          {hasRoutes && comparisonLabel && <button className="missionButton missionButtonQuiet" onClick={onCompare}>
            {comparisonLabel} <ArrowUpRight size={16} aria-hidden="true"/>
          </button>}
        </footer>
      </section>

      <aside className="missionRail" aria-label="Dispatch briefing">
        <section className="missionFleet" aria-labelledby="mission-fleet-title">
          <header className="missionPanelHead">
            <div><span className="missionEyebrow">Simulated fleet</span><h2 id="mission-fleet-title">Dispatch roster</h2></div>
            <span className="missionFleetCount">{count.format(mission.vehicles.length)} vans</span>
          </header>
          <ul className="missionRows">
            {mission.vehicles.map(vehicle => {
              const stops = baseline.routes.find(route => route.vehicle_id === vehicle.id)?.stop_ids ?? vehicle.stop_ids;
              const stopIds = new Set(stops);
              const districts = new Set(mission.deliveries.filter(delivery => stopIds.has(delivery.id)).map(delivery => delivery.district));
              return <li key={vehicle.id}>
                <button onClick={() => onMap(vehicle.id)} aria-label={`Open ${vehicle.id} on the map`}>
                  <span className="missionVehicleCode" style={{ borderInlineStartColor: fleetColor(vehicle.id, vehicle.color) }}>{vehicle.id}</span>
                  <span className="missionRowTitle"><strong>{vehicle.driver}</strong><small>{districts.size} {districts.size === 1 ? 'district' : 'districts'}</small></span>
                  <span className="missionRowCount">{stops.length} {stops.length === 1 ? 'stop' : 'stops'}</span>
                  <ChevronRight size={15} aria-hidden="true"/>
                </button>
              </li>;
            })}
          </ul>
        </section>

        <section className="missionReview" aria-labelledby="mission-review-title">
          <span className="missionEyebrow"><BrainCircuit size={15} aria-hidden="true"/> Dispatch copilot</span>
          <h2 id="mission-review-title">Review fleet disruptions</h2>
          <p>Ask the copilot to inspect the fleet and nearby notices. Follow each tool call in the trace; the review leaves plans unchanged.</p>
          <button className="missionButton missionButtonReview" onClick={onInvestigate} disabled={!connected || busy}>
            {connected ? 'Run fleet review' : 'Fleet review requires the API'} <ArrowRight size={16} aria-hidden="true"/>
          </button>
        </section>
      </aside>
    </div>

    <div className="missionLower">
      <section className="missionFleet" aria-labelledby="mission-notices-title">
        <header className="missionPanelHead"><div><span className="missionEyebrow">{municipalNotices} municipal · {notices.length - municipalNotices} scenario</span><h2 id="mission-notices-title">Notices to inspect</h2></div>
          <button className="missionButton missionButtonQuiet" onClick={onIncidents}>All notices <ArrowRight size={15} aria-hidden="true"/></button>
        </header>
        {notices.length ? <ul className="missionRows">{notices.slice(0, 3).map(notice => <li key={notice.id}>
          <button onClick={() => onIncident(notice.id)}>
            <span className="missionSeverity" data-severity={notice.severity}>{notice.severity}</span>
            <span className="missionRowTitle"><strong>{notice.title}</strong><small>{notice.provenance.origin === 'municipal_open_data' ? 'Madrid Open Data' : 'Simulated notice'}</small></span>
            <ChevronRight size={15} aria-hidden="true"/>
          </button>
        </li>)}</ul> : <p className="missionEmpty">There are no notices in the current snapshot.</p>}
      </section>
      <section className="missionSources" aria-labelledby="mission-sources-title">
        <span className="missionEyebrow"><Layers3 size={15} aria-hidden="true"/> Ayuntamiento de Madrid</span>
        <h2 id="mission-sources-title">Municipal readings</h2>
        <p>{hasReadings ? `${count.format(signals.total_valid)} valid sensor readings${fetchedLabel ? ` · downloaded ${fetchedLabel} (Madrid time)` : ''}.` : 'No sensor snapshot has been loaded. Fetch the municipal feed to inspect its coverage and observation times.'}</p>
        <button className="missionButton missionButtonQuiet" onClick={hasReadings ? onSignals : onLoadSources} disabled={!hasReadings && (!connected || busy || loadingSources)}>
          {hasReadings ? 'Explore readings' : loadingSources ? 'Fetching Madrid data…' : 'Fetch Madrid data'}
          {hasReadings ? <ArrowRight size={15} aria-hidden="true"/> : <RefreshCw size={15} aria-hidden="true"/>}
        </button>
      </section>
    </div>
  </div>;
}
