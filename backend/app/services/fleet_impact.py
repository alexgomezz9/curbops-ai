"""Deterministic, read-only fleet-disruption briefing for the reactive map copilot.

Uses provider street geometries *already computed*. Municipal notices and sensor
measurements are observations, never verified closures or live segment ETAs.
No optimization, dispatch, or new proposal occurs here.
"""
from __future__ import annotations
from ..store import DemoStore
from .route_corridor import vehicle_corridor
from .route_traffic import inspect_route_traffic


def fleet_impact(store: DemoStore, scenario: str = 'C', *, radius_m: int = 200) -> dict:
    if scenario not in {'A', 'B', 'C'}:
        raise ValueError('Scenario must be A, B or C')
    with store.lock:
        plan = {'A': store.road_baseline or store.original,
                'B': store.no_risk_plan,
                'C': store.proposed or store.approved}[scenario]
        if plan is None:
            raise ValueError(f'Scenario {scenario} not yet calculated; load road routes first')
        if not all(route.fidelity == 'road_network' for route in plan.routes):
            raise ValueError('Street geometry required; do not infer exposure from straight-line routes')
        vehicles = [r.vehicle_id for r in plan.routes]
        has_observations = bool(store.traffic_points)
        sampled_at = store.traffic_observed_at
        downloaded_at = store.traffic_fetched_at

    rows = []
    for vehicle_id in vehicles:
        corridor = vehicle_corridor(store, vehicle_id, scenario)
        measurements = (inspect_route_traffic(store, vehicle_id, scenario, radius_m, limit=10)
                        if has_observations else None)
        notices = corridor['nearby_incidents']
        congested = [o for o in (measurements or {}).get('observations', [])
                     if o.get('service_level') == 3]
        rows.append({
            'vehicle_id': vehicle_id,
            'nearby_notices': corridor['nearby_count'],
            'risk_penalties_applied': corridor['applied_count'],
            'municipal_notices': sum(n['origin'] == 'municipal_open_data' for n in notices),
            'synthetic_notices': sum(n['origin'] == 'synthetic' for n in notices),
            'notice_ids': [n['id'] for n in notices[:8]],
            'congested_sensor_points_nearby': (measurements or {}).get('congested_nearby_count', 0),
            'displayed_congested_sensor_count': len(congested),
            'congested_sensor_ids': [o['id'] for o in congested[:5]],
            'measurements_available': measurements is not None,
        })
    rows.sort(key=lambda r: (
        -r['risk_penalties_applied'],
        -r['congested_sensor_points_nearby'],
        -r['nearby_notices'], r['vehicle_id']))
    return {
        'scenario': scenario, 'vehicles': rows,
        'observed_at': sampled_at, 'downloaded_at': downloaded_at,
        'recommended_focus': rows[0]['vehicle_id'] if rows else None,
        'interpretation': ('Priority order is a screening heuristic, not a measured delay or optimized dispatch. '
                           'A sensor near a route is not proof of congestion on its actual lanes. '
                           'Municipal notices include unknown or outside-window records. '
                           'No closures confirmed, historical trend or dynamic ETAs.'),
    }
