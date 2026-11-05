"""No external road provider, municipality, or Gemini calls."""
import asyncio
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
import pytest
from app.main import app
from app.models import Incident, DataProvenance, DispatchPlan, RouteLine, PlanMetrics, MapAction
from app.store import DemoStore,store
from app.services.road_detours import attempt_rehearsal_detours
from app.services.road_risk import corridor_hit
from app.scenario import DEPOT,DELIVERIES


def scenario_incident():
    now=datetime.now(timezone.utc)
    return Incident(id='SIM-ROADWORKS',title='Synthetic rehearsal',location=(-3.711,40.419),
        kind='roadworks',severity='high',radius_m=180,detail='not a real road closure',
        starts_at=now.isoformat(),ends_at=(now+timedelta(hours=2)).isoformat(),
        provenance=DataProvenance(origin='synthetic',label='operator rehearsal'))


def test_rehearsal_requires_verified_B_routes_and_clears_on_reset():
    # The app singleton is only used for this isolated handler test.
    store.reset()
    c=TestClient(app)
    assert c.post('/api/decision/rehearsal',json={'vehicle_id':'UNKNOWN'}).status_code==422
    assert c.post('/api/decision/rehearsal',json={'vehicle_id':'V-01'}).status_code==409
    # Fake existing B, with actual street polyline vertices, as the endpoint requires.
    fake=store.original.model_copy(deep=True)
    fake.routes[0].coordinates=[DEPOT,(-3.713,40.42),(-3.715,40.423),(-3.713,40.426),(-3.710,40.429),DEPOT]
    store.no_risk_plan=fake
    response=c.post('/api/decision/rehearsal',json={'vehicle_id':'V-01'})
    assert response.status_code==200,response.text
    assert response.json()['incident']['provenance']['origin']=='synthetic'
    assert 'SIM-ROADWORKS' in [i.id for i in store.incidents]
    assert store.proposed is None and store.no_risk_plan is None
    cleared=c.post('/api/decision/rehearsal',json={'vehicle_id':'V-01','clear':True})
    assert cleared.status_code==200
    assert not cleared.json()['active']
    store.reset()


def test_avoidance_uses_provider_geometry_and_detour_budget():
    incident=scenario_incident()
    from app.scenario import VEHICLES
    route=RouteLine(vehicle_id='V-01',stop_ids=['D-104'],color='#2ADBC2',
        coordinates=[DEPOT,incident.location,DELIVERIES[3].location],
        distance_km=3.0,estimated_minutes=10.0,incidents_near=[incident.id],fidelity='road_network')
    plan=DispatchPlan(id='synthetic',status='proposed',generated_at=datetime.now(timezone.utc).isoformat(),
        routes=[route],metrics=PlanMetrics(distance_km=3,travel_minutes=10,late_deliveries=0,
                                          exposures=1,total_stops=1,score=3),
        explanation='fixture',limitations=[])
    called=[]
    async def real_provider_mock(points):
        called.append(points)
        # True provider would snap the via coordinate to the street graph.
        path=[points[0],points[1],points[-1]]
        # Baseline street-leg calls must not report the detour cost: inconsistent
        # provider test data would make an extra-km calculation meaningless.
        km, minutes = (4.0,12.0) if len(points)>2 else (3.0,10.0)
        return path, km, minutes
    computed,proof=asyncio.run(attempt_rehearsal_detours(plan,incident,real_provider_mock))
    assert proof['V-01']['checked_alternatives']>=1
    assert proof['V-01']['geometry_changed'],proof
    assert not corridor_hit(computed.routes[0].coordinates,incident)
    # Both outbound and return road legs cross the hypothetical zone;
    # one provider-verified detour per affected leg adds 1 km each.
    assert computed.routes[0].distance_km==5
    assert incident.id not in computed.routes[0].incidents_near
    # A dramatic detour must be rejected even when it avoids the risk.
    async def expensive_provider(points):return [points[0],points[1],points[-1]],15.0,120.0
    original,detail=asyncio.run(attempt_rehearsal_detours(plan,incident,expensive_provider))
    assert not detail['V-01']['geometry_changed']
    assert original.routes[0].distance_km==3


def test_rehearsal_does_not_masquerade_as_an_official_closure():
    demo=DemoStore()
    i=scenario_incident()
    demo.rehearsal_incident=i
    assert any(x.id==i.id and x.provenance.origin=='synthetic' for x in demo.snapshot().incidents)
    demo.reset()
    assert not any(x.id==i.id for x in demo.incidents)
    with pytest.raises(Exception):MapAction(type='approve_real_vehicles')
