"""Road-time optimization and risk counterfactual are explicitly distinguishable.

All provider responses are synthetic: never contact the public demo in tests.
"""
import asyncio
from copy import deepcopy
from fastapi.testclient import TestClient
import pytest
from app.main import app
from app.settings import get_settings
from app.services.routing import _validate_matrix_payload
from app.services.matrix_optimizer import RoadCostMatrix,optimize_road_matrix
from app.services.road_plans import build_road_network_plan
from app.services.geo import distance_km
from app.scenario import DEPOT,DELIVERIES,VEHICLES,INCIDENTS
from app.store import DemoStore
from app.services.decision_audit import audit_plan


def mock_table():
    pts=[DEPOT]+[d.location for d in DELIVERIES]
    ids=('DEPOT',*[d.id for d in DELIVERIES])
    mins=tuple(tuple(round(distance_km(p,q)*4.2,5) for q in pts) for p in pts)
    kms=tuple(tuple(round(distance_km(p,q)*1.3,5) for q in pts) for p in pts)
    return RoadCostMatrix(ids,mins,kms)


def test_counterfactual_uses_same_road_cost_matrix_and_valid_capacities():
    matrix=mock_table()
    res=optimize_road_matrix(VEHICLES,DELIVERIES,INCIDENTS,matrix)
    assert res.risk_adjusted_objective['base_travel_minutes']>0
    assert res.no_incident_objective['base_travel_minutes']>0
    assert set(x for order in res.risk_adjusted.values() for x in order)=={d.id for d in DELIVERIES}
    assert sum(len(x) for x in res.risk_adjusted.values())==len(DELIVERIES)
    assert all(len(res.risk_adjusted[v.id])<=v.capacity for v in VEHICLES)
    assert res.incident_affected_optimization == (res.risk_adjusted!=res.no_incident_counterfactual)
    # Counterfactual with no events cannot claim that incidents changed an order.
    no_events=optimize_road_matrix(VEHICLES,DELIVERIES,[],matrix)
    assert not no_events.incident_affected_optimization
    assert no_events.risk_adjusted==no_events.no_incident_counterfactual


def test_matrix_invalid_or_unreachable_never_falls_back_to_flying_lines():
    with pytest.raises(ValueError,match='complete'):
        mock_table().validate() if False else RoadCostMatrix(('DEPOT','A'),((0.,),),((0.,1.),(1.,0.))).validate()
    with pytest.raises(ValueError,match='Unreachable'):
        _validate_matrix_payload({'durations':[[0,None],[1,0]],'distances':[[0,1],[1,0]]},2)


def test_six_street_routes_and_model_attribution_atomic():
    store=DemoStore()
    events=[]
    async def fake_route(points):
        return list(points),len(points)*1.6,len(points)*4.8
    async def fake_matrix(points):
        assert len(points)==16
        return {'minutes':[list(row) for row in mock_table().minutes],
                'kilometres':[list(row) for row in mock_table().kilometres]}
    plan=asyncio.run(build_road_network_plan(store,fake_route,
                                             lambda name,data:events.append(name),matrix_fetcher=fake_matrix))
    assert all(r.fidelity=='road_network' for r in plan.routes)
    assert [x for x in events if x=='routing.route_completed']==['routing.route_completed']*6
    assert events.index('routing.matrix_completed')<events.index('routing.route_completed')
    assert store.decision_context is not None
    audit=audit_plan(store.road_baseline,plan,decision_context=store.decision_context,incidents=INCIDENTS)
    counter=audit['risk_attribution']
    assert counter is not None and counter['road_costs_compared']
    assert counter['changed_by_soft_incident_penalty']==(
        counter['no_incident_counterfactual'] != {r.vehicle_id:r.stop_ids for r in plan.routes})
    assert all('counterfactual_stops_no_risk' in v for v in audit['vehicles'])
    assert any('geographic' in text.lower() or 'geom' in text.lower() for text in audit['limitations'])


def test_failed_matrix_does_not_commit_plans():
    store=DemoStore()
    async def fake_route(points):
        raise AssertionError('Routes should not start after matrix failure')
    async def failed_matrix(points):
        raise RuntimeError('Unavailable road table')
    with pytest.raises(RuntimeError,match='Unavailable road table'):
        asyncio.run(build_road_network_plan(store,fake_route,matrix_fetcher=failed_matrix))
    assert store.proposed is None and store.road_baseline is None
    assert store.decision_context is None


def test_http_audit_returns_counterfactual_when_api_builds_matrix(monkeypatch):
    import app.main as main
    from app.store import store
    store.reset()
    monkeypatch.setattr(main.settings,'routing_provider','osrm_demo')
    monkeypatch.setattr(main.settings,'road_matrix_optimization',True)
    async def fake_route(points):
        return list(points),len(points)*1.6,len(points)*4.8
    monkeypatch.setattr(main,'fetch_road_route',fake_route)
    c=TestClient(app)
    result=c.post('/api/replan/road-network')
    assert result.status_code==200,result.text
    audit=c.get('/api/decision/audit')
    assert audit.status_code==200
    assert audit.json()['risk_attribution']['method']=='road_time_matrix_plus_bounded_street_geometry_candidate_ranking'
    store.reset()


def test_baseline_loads_only_current_street_routes_not_a_proposal(monkeypatch):
    from app import main
    from app.store import store
    store.reset()
    monkeypatch.setattr(main.settings,'routing_provider','osrm_demo')
    calls=[]
    async def fake_route(points):
        calls.append(points)
        return list(points),len(points)*1.1,len(points)*3.1
    monkeypatch.setattr(main,'fetch_road_route',fake_route)
    c=TestClient(app)
    result=c.post('/api/routing/baseline')
    assert result.status_code==200,result.text
    assert len(calls)==3
    snap=c.get('/api/mission').json()
    assert all(r['fidelity']=='road_network' for r in snap['original_plan']['routes'])
    assert snap['proposed_plan'] is None
    assert snap['approved_plan'] is None
    # Repeated clicks reuse the baseline; do not waste public API requests.
    again=c.post('/api/routing/baseline')
    assert again.status_code==200 and len(calls)==3
    store.reset()


def test_baseline_partial_failure_never_commits_fake_plan(monkeypatch):
    from app import main
    from app.store import store
    store.reset()
    monkeypatch.setattr(main.settings,'routing_provider','osrm_demo')
    calls=0
    async def flaky(points):
        nonlocal calls
        calls+=1
        if calls==2:raise RuntimeError('public demo failure')
        return list(points),3.,8.
    monkeypatch.setattr(main,'fetch_road_route',flaky)
    c=TestClient(app)
    result=c.post('/api/routing/baseline')
    assert result.status_code==502
    assert store.road_baseline is None
    assert store.proposed is None
    store.reset()


def test_osrm_table_parser_converts_units_without_fabrication():
    payload={'durations':[[0,120],[180,0]],'distances':[[0,1400],[1600,0]]}
    matrix=_validate_matrix_payload(payload,2)
    assert matrix['minutes']==[[0,2],[3,0]]
    assert matrix['kilometres']==[[0,1.4],[1.6,0]]
    with pytest.raises(ValueError,match='complete'):
        _validate_matrix_payload({'durations':[[0,120],[180,0]],'distances':[]},2)
