"""Read-only municipal point observations near a routed vehicle path.

A point sample is not a segment speed or a live delivery ETA. We never infer
congestion duration from two noncontinuous snapshots or from download time.
"""
from __future__ import annotations
from ..services.geo import point_segment_km
from ..store import DemoStore


def inspect_route_traffic(store:DemoStore,vehicle_id:str,scenario:str='C',radius_m:int=250,limit:int=12)->dict:
    if scenario not in ('A','B','C'):raise ValueError('Unknown scenario')
    if not 50 <= radius_m <= 1000:raise ValueError('Radius outside permitted range')
    with store.lock:
        plans={'A':store.road_baseline or store.original,
               'B':store.no_risk_plan,
               'C':store.approved or store.proposed}
        plan=plans[scenario]
        if plan is None:raise ValueError('Scenario not available')
        route=next((r for r in plan.routes if r.vehicle_id==vehicle_id),None)
        if route is None:raise ValueError('Unknown vehicle')
        if route.fidelity!='road_network':raise ValueError('Street geometry not loaded')
        observations=list(store.traffic_points)
        observed_at=store.traffic_observed_at
        fetched_at=store.traffic_fetched_at
        previous_at=store.previous_traffic_fetched_at
    rows=[]
    for p in observations:
        nearest=min((point_segment_km(p.location,a,b) for a,b in zip(route.coordinates[:-1],route.coordinates[1:])),default=float('inf'))
        if nearest<=radius_m/1000:
            rows.append({'id':p.id,'road_name':p.road_name,'distance_m':round(nearest*1000),
                         'service_level':p.service_level,'intensity_vph':p.intensity_vph,
                         'occupancy_pct':p.occupancy_pct,'speed_kmh':p.speed_kmh,
                         'location':p.location})
    rows.sort(key=lambda x:(x['distance_m'],x['id']))
    return {'vehicle_id':vehicle_id,'scenario':scenario,'route_fidelity':'road_network',
            'sampled_nearby_count':len(rows),'showing':min(limit,len(rows)),
            'congested_nearby_count':sum(r['service_level']==3 for r in rows),
            'service_level_counts':{str(level):sum(r['service_level']==level for r in rows) for level in range(4)},
            'unknown_level_count':sum(r['service_level'] is None for r in rows),
            'observations':rows[:limit], 'observed_at':observed_at,'downloaded_at':fetched_at,
            'previous_snapshot_available':bool(previous_at),
            'congestion_duration_minutes':None,
            'congestion_duration_status':'unknown_no_continuous_sensor_history',
            'note':'Municipal sensor points within an indicative corridor. Intensity (veh/h) and occupancy (%) are NOT spatial vehicle density. No real-time street ETA, verified closure, or persistent-congestion duration is inferred.'}
