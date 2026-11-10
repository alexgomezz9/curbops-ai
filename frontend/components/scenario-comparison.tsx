import type { ComparisonId, DispatchPlan, ScenarioId } from '@/lib/types';

export const scenarioNames = { A: 'Original', B: 'Road cost', C: 'Risk-aware' } satisfies Record<ScenarioId, string>;

const oneDecimal = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 1 });
const signed = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 1, signDisplay: 'exceptZero' });

function readMetrics(plan: DispatchPlan, vehicle: string | null) {
  const routes = vehicle ? plan.routes.filter(route => route.vehicle_id === vehicle) : plan.routes;
  if (!routes.length || routes.some(route => route.fidelity !== 'road_network')) return null;
  if (vehicle) {
    const route = routes[0];
    return { km: route.distance_km, minutes: route.estimated_minutes, stops: route.stop_ids.length };
  }
  return { km: plan.metrics.distance_km, minutes: plan.metrics.travel_minutes, stops: plan.metrics.total_stops };
}

type Props = {
  pair: ComparisonId;
  availablePairs: ComparisonId[];
  referenceId: ScenarioId;
  candidateId: ScenarioId;
  reference: DispatchPlan;
  candidate: DispatchPlan;
  vehicle: string | null;
  mix: number;
  stale: boolean;
  onPair: (pair: ComparisonId) => void;
  onMix: (mix: number) => void;
};

export default function ScenarioComparison({ pair, availablePairs, referenceId, candidateId, reference, candidate, vehicle, mix, stale, onPair, onMix }: Props) {
  const before = readMetrics(reference, vehicle);
  const after = readMetrics(candidate, vehicle);
  const metrics = before && after ? [
    { label: 'Road distance', from: before.km, to: after.km, unit: 'km' },
    { label: 'Base drive time', from: before.minutes, to: after.minutes, unit: 'min' },
    { label: 'Delivery stops', from: before.stops, to: after.stops, unit: '' },
  ] : [];

  return <section className="scenarioCompare" aria-label="Route comparison">
    <div className="scenarioCompareTop">
      <div className="scenarioCompareTitle"><strong>Route comparison</strong><span>{vehicle ?? 'Entire fleet'} · {stale ? 'Notices changed since planning' : 'Simulated dispatch'}</span></div>
      <select value={pair} aria-label="Compared scenarios" onChange={e => onPair(e.target.value as ComparisonId)}>
        <option value="AB" disabled={!availablePairs.includes('AB')}>A vs B · Road optimization</option>
        <option value="BC" disabled={!availablePairs.includes('BC')}>B vs C · Incident proximity</option>
        <option value="AC" disabled={!availablePairs.includes('AC')}>A vs C · Overall change</option>
      </select>
    </div>

    {metrics.length ? <dl className="scenarioMetrics" aria-label="Reference and candidate metrics">
      {metrics.map(({ label, from, to, unit }) => {
        const delta = (Math.round(to * 10) - Math.round(from * 10)) / 10;
        return <div key={label}>
          <dt>{label}</dt>
          <dd><span aria-label={`${oneDecimal.format(from)} to ${oneDecimal.format(to)} ${unit}`}>{oneDecimal.format(from)} <span aria-hidden="true">→</span> <strong>{oneDecimal.format(to)}</strong>{unit && ` ${unit}`}</span>
            <small>{delta ? `${signed.format(delta)}${unit ? ` ${unit}` : ''}` : 'No change'}</small></dd>
        </div>;
      })}
    </dl> : <p className="scenarioCompareEmpty">Metrics require street routes in both scenarios for this selection.</p>}

    <div className="scenarioCompareControls">
      <div className="scenarioOverlayKey" aria-label="Map line styles">
        <span><i className="reference" aria-hidden="true"/>{referenceId} · {scenarioNames[referenceId]}</span>
        <span><i aria-hidden="true"/>{candidateId} · {scenarioNames[candidateId]}</span>
      </div>
      <div className="scenarioMix">
        <input type="range" min="0" max="100" value={mix} aria-label="Route comparison visibility" onChange={e => onMix(Number(e.target.value))}/>
        <div role="group" aria-label="Route visibility presets">
          {([[0, 'Reference'], [50, 'Both'], [100, 'Candidate']] as const).map(([value, label]) =>
            <button key={value} aria-pressed={mix === value} onClick={() => onMix(value)}>{label}</button>)}
        </div>
      </div>
    </div>
  </section>;
}
