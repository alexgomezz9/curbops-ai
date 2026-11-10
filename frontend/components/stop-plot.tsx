import { useId } from 'react';
import type { DispatchPlan, MissionSnapshot, Position } from '@/lib/types';
import { fleetColor } from '@/lib/fleet-colors';

// A local coordinate plot keeps the original stops visible if the basemap is unavailable.
// It draws lines only for geometry actually returned by the routing provider.
export default function StopPlot({ mission, plan }: { mission: MissionSnapshot; plan: DispatchPlan }) {
  const grid = useId();
  const roadRoutes = plan.routes.filter(route => route.fidelity === 'road_network');
  const coordinates = [mission.depot, ...mission.deliveries.map(stop => stop.location), ...roadRoutes.flatMap(route => route.coordinates)];
  const longitude = coordinates.map(point => point[0]);
  const latitude = coordinates.map(point => point[1]);
  const west = Math.min(...longitude), east = Math.max(...longitude);
  const south = Math.min(...latitude), north = Math.max(...latitude);
  const ratio = Math.cos((north + south) * Math.PI / 360);
  const scale = Math.min(636 / Math.max((east - west) * ratio, .001), 248 / Math.max(north - south, .001));
  const project = ([lon, lat]: Position) => [360 + (lon - (east + west) / 2) * scale * ratio, 160 - (lat - (north + south) / 2) * scale];
  const [depotX, depotY] = project(mission.depot);
  const stopColors = new Map(plan.routes.flatMap(route => route.stop_ids.map(id => [id, fleetColor(route.vehicle_id, route.color)] as const)));

  return <svg className="stopPlot" viewBox="0 0 720 320" role="img" aria-label={`Coordinate plot of the Madrid depot and ${mission.deliveries.length} delivery stops`}>
    <defs><pattern id={grid} width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="currentColor" strokeOpacity=".15"/></pattern></defs>
    <rect x="-720" y="-320" width="2160" height="960" fill={`url(#${grid})`}/>
    <path d={`M0 ${depotY}H720 M${depotX} 0V320`} fill="none" stroke="currentColor" strokeOpacity=".35" strokeDasharray="5 5"/>
    {roadRoutes.map(route => <polyline key={route.vehicle_id} points={route.coordinates.map(point => project(point).join(',')).join(' ')} fill="none" stroke={fleetColor(route.vehicle_id, route.color)} strokeWidth="2.5" strokeLinejoin="round"/>)}
    {mission.deliveries.map(stop => {
      const [x, y] = project(stop.location);
      return <circle key={stop.id} cx={x} cy={y} r="5" fill={stopColors.get(stop.id) || '#9ac8bd'} stroke="#e3eddd" strokeWidth="1.5"><title>{stop.id} · {stop.district}</title></circle>;
    })}
    <circle cx={depotX} cy={depotY} r="13" fill="none" stroke="currentColor" strokeOpacity=".55"/>
    <rect x={depotX - 4} y={depotY - 4} width="8" height="8" fill="currentColor" transform={`rotate(45 ${depotX} ${depotY})`}/>
    <text x={depotX + 18} y={depotY + 4} fill="currentColor" fontSize="11" letterSpacing="2">DEPOT</text>
  </svg>;
}
