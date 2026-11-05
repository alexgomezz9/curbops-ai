"""Provider and mission state are mocked. No real OSRM/ORS/municipal requests."""
import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models import RouteLine, DataProvenance, Incident
from app.store import DemoStore
from app.scenario import DEPOT, DELIVERIES
from app.services.precautionary import prepare_precautionary_plan, _shape_one_route
from app.services.road_risk import corridor_hit


POINT=(-3.711,40.419)

def obstacle():
    return Incident(id='SIM-ROADWORKS', title='Test hypothetical obstruction',
        location=POINT, kind='roadworks',severity='high', radius_m=180,
        detail='synthetic', provenance=DataProvenance(origin='synthetic',label='test'))


def fake_store():
    demo=DemoStore()
    b=demo.original.model_copy(deep=True)
    b.routes=b.routes[:1]
    r=b.routes[0]
    r.stop_ids=['D-104']
    r.coordinates=[DEPOT,POINT,DELIVERIES[3].location,DEPOT]
    r.fidelity='road_network'
    r.distance_km=3
    r.estimated_minutes=10
    r.incidents_near=['SIM-ROADWORKS']
    b.metrics.distance_km=3
    b.metrics.travel_minutes=10
    demo.no_risk_plan=b
    demo.rehearsal_incident=obstacle()
    return demo


def test_preventative_avoids_only_provider_checked_geometry():
    demo=fake_store()
    calls=[]
    async def provider(points):
        calls.append(points)
        # Mock street provider makes a viable route exactly when given a waypoint
        if len(points)>3:
            return [points[0],points[1],points[-1]],4.0,12
        return [points[0],POINT,points[-1]],3.0,10
    result=asyncio.run(prepare_precautionary_plan(demo,provider,incident_ids=['SIM-ROADWORKS']))
    assert result['verified_vehicle_detours']==1
    assert result['status']=='verified_detour'
    assert result['vehicles'][0]['avoided_ids']==['SIM-ROADWORKS']
    assert not corridor_hit(demo.proposed.routes[0].coordinates,obstacle())
    assert demo.no_risk_plan.routes[0].coordinates[1]==POINT  # B intact
    assert demo.proposed.status=='proposed' and demo.approved is None
    assert demo.planned_incident_signature==demo.incident_signature()
    assert calls


def test_unsuccessful_provider_cannot_claim_reroute():
    demo=fake_store()
    async def no_change(points):return [DEPOT,POINT,DEPOT],3,10
    result=asyncio.run(prepare_precautionary_plan(demo,no_change))
    assert result['verified_vehicle_detours']==0
    assert result['status']=='no_verified_detour'
    assert demo.proposed.routes[0].coordinates==demo.no_risk_plan.routes[0].coordinates
    assert 'SIM-ROADWORKS' in result['vehicles'][0]['still_near_ids']


def test_abort_when_incident_changed_mid_search():
    demo=fake_store()
    async def corrupt_snapshot(points):
        demo.rehearsal_incident.radius_m+=1
        return [DEPOT,POINT,DEPOT],3,10
    with pytest.raises(RuntimeError,match='Mission changed'):
        asyncio.run(prepare_precautionary_plan(demo,corrupt_snapshot))
    assert demo.proposed is None


def test_avoid_endpoint_requires_computed_B():
    from app.store import store
    store.reset()
    result=TestClient(app).post('/api/decision/precautionary-avoidance',json={'vehicle_id':'ALL'})
    assert result.status_code==409
    assert 'Generate B' in result.text
    store.reset()
