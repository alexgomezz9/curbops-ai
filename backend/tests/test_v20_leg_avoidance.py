"""Long fleet routes and obstruction verification use synthetic provider data."""
import asyncio
from math import cos, radians
from app.services.leg_avoidance import find_leg_detours
from app.services.road_risk import corridor_hit
from app.models import RouteLine, DataProvenance, Incident
from app.scenario import DEPOT, DELIVERIES


def _mid(a,b):return ((a[0]+b[0])/2,(a[1]+b[1])/2)

def test_stop_preserving_local_detour_on_long_route():
    stop_ids=[d.id for d in DELIVERIES[:7]]
    pts=[DEPOT]+[d.location for d in DELIVERIES[:7]]+[DEPOT]
    midpoint=_mid(pts[5],pts[6])
    incident=Incident(id='SIM-LONG',title='Synthetic street interruption',kind='roadworks',severity='high',
        location=midpoint,radius_m=100,detail='test',provenance=DataProvenance(origin='synthetic',label='test'))
    route=RouteLine(vehicle_id='V-01',stop_ids=stop_ids,color='#2563eb',coordinates=pts,
        distance_km=40,estimated_minutes=100,incidents_near=[incident.id],fidelity='road_network')
    calls=[]
    async def provider(points):
        calls.append(points)
        # Valid road polyline fixture through provider-requested waypoints;
        # straight base leg passes the middle of the synthetic obstruction.
        return points, 1.25 if len(points)==2 else 1.85, 2 if len(points)==2 else 3
    updated,proof=asyncio.run(find_leg_detours(route,[incident],provider))
    assert proof['verified'],proof
    assert 'SIM-LONG' in proof['avoided_ids']
    assert updated.stop_ids==stop_ids
    assert not corridor_hit(updated.coordinates,incident)
    assert all(len(c)<=4 for c in calls)  # Never exceeds OSRM's 10-point cap.
    assert proof['provider_checks']>0


def test_no_verified_geometry_is_not_presented_as_avoidance():
    a=DEPOT;b=DELIVERIES[0].location
    midpoint=_mid(a,b)
    incident=Incident(id='SIM-STOP',title='Cannot avoid stop',kind='roadworks',severity='high',
        location=a,radius_m=190,detail='test',provenance=DataProvenance(origin='synthetic',label='test'))
    route=RouteLine(vehicle_id='V-01',stop_ids=[DELIVERIES[0].id],color='#2563eb',
        coordinates=[a,b,a],distance_km=5,estimated_minutes=15,incidents_near=[incident.id],fidelity='road_network')
    async def provider(points):return points,2,4
    updated,proof=asyncio.run(find_leg_detours(route,[incident],provider))
    assert not proof['verified']
    assert updated.coordinates==route.coordinates
    assert incident.id in proof['still_near_ids']


def test_prefers_valid_osrm_alternative_over_waypoint_search():
    a=DEPOT;b=DELIVERIES[0].location
    event=Incident(id='SIM-ALTERNATIVE',title='Road corridor',kind='roadworks',severity='high',
        location=_mid(a,b),radius_m=120,detail='test',
        provenance=DataProvenance(origin='synthetic',label='test'))
    route=RouteLine(vehicle_id='V-01',stop_ids=[DELIVERIES[0].id],color='#2563eb',
        coordinates=[a,b,a],distance_km=8,estimated_minutes=15,
        incidents_near=[event.id],fidelity='road_network')
    calls=[]
    async def provider(points):
        calls.append(points)
        return points,3,6
    async def alternates(points):
        # Both endpoints retained; an offset polyline is from the mock street
        # provider, not an LLM drawing.
        midpoint=_mid(*points)
        offset=(midpoint[0],midpoint[1]+0.01)
        return [([points[0],offset,points[-1]],3.6,7.4)]
    changed,proof=asyncio.run(find_leg_detours(route,[event],provider,alternative_fetcher=alternates))
    assert proof['verified'] and proof['avoided_ids']==[event.id]
    assert not corridor_hit(changed.coordinates,event)
    assert not any(len(c)>2 for c in calls)  # no via requests needed
