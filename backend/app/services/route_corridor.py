"""Road-geometry incident proximity for operator investigation, not closure detection.

This deliberately includes temporally unknown/inactive notices as *context* while
separately identifying which eligible ones were used in scenario C. No street
is declared closed. The inspected route is a provider road polyline.
"""
from __future__ import annotations
from ..store import DemoStore
from .decision_explain import scenario_payload
from .road_risk import corridor_hit


def vehicle_corridor(store: DemoStore, vehicle_id: str, scenario: str = 'C') -> dict:
    if scenario not in ('A', 'B', 'C'):
        raise ValueError('Scenario must be A, B or C')
    with store.lock:
        payload = scenario_payload(store)
        plan = payload.get(scenario)
        route = next((r for r in (plan or {}).get('routes', [])
                      if r['vehicle_id'] == vehicle_id), None)
        if route is None or route['fidelity'] != 'road_network':
            raise ValueError('No road-network route for this vehicle and scenario')
        if len(route['coordinates']) < 2:
            raise ValueError('Cannot inspect an empty road route')
        notices = list(store.incidents)
        context = dict(store.decision_context or {})
    time_status = {r['id']:r['temporal_status'] for r in payload.get('temporal_evidence', [])}
    applied_ids = set()
    if scenario == 'C':
        legs = ((context.get('breakdown') or {}).get('C') or {}).get(vehicle_id, {}).get('legs', [])
        applied_ids = {hit['id'] for leg in legs for hit in leg.get('incidents', [])}
    affected = []
    for item in notices:
        if not corridor_hit(route['coordinates'], item):
            continue
        status = time_status.get(item.id, 'unknown')
        affected.append({
            'id': item.id, 'title': item.title, 'location': list(item.location),
            'severity': item.severity, 'origin': item.provenance.origin,
            'temporal_status': status, 'radius_m': item.radius_m,
            'applied_to_optimizer': item.id in applied_ids,
            'restriction_verified': False,
        })
    affected.sort(key=lambda r: (not r['applied_to_optimizer'], r['origin'] != 'synthetic',r['id']))
    return {
        'vehicle_id': vehicle_id, 'scenario': scenario,
        'plan_id': payload.get('plan_id'), 'generation': payload['generation'],
        'route_fidelity': 'road_network',
        'nearby_count': len(affected),
        'applied_count': sum(i['applied_to_optimizer'] for i in affected),
        'nearby_incidents': affected,
        'note': ('Every point is within its recorded approximate radius of a road polyline segment. '
                 'Includes temporally unknown or inactive notices, which are NOT optimizer risk. '
                 'Applied flags describe C pre-detour risk evidence and may not reflect a subsequent synthetic via-point detour. '
                 'None establishes a blocked street, live traffic delay or current closure.'),
    }


def incident_fleet_corridor(store: DemoStore, incident_id: str, scenario: str = 'C') -> dict:
    with store.lock:
        incident = next((i for i in store.incidents if i.id == incident_id), None)
        if incident is None:
            raise ValueError('Unknown incident')
        plan = scenario_payload(store).get(scenario)
        if not plan:
            raise ValueError('Scenario is not available')
        vehicle_ids = [route['vehicle_id'] for route in plan['routes']]
    matches = []
    for vehicle_id in vehicle_ids:
        report = vehicle_corridor(store, vehicle_id, scenario)
        hit = next((r for r in report['nearby_incidents'] if r['id'] == incident_id), None)
        if hit:
            matches.append({'vehicle_id':vehicle_id,'applied_to_optimizer':hit['applied_to_optimizer'],
                            'temporal_status':hit['temporal_status']})
    return {'incident_id':incident_id,'scenario':scenario,'nearby_vehicles':matches,
            'note':'Point proximity on road geometries; no verified lane closure or delay impact.'}
