"""v1.4 route explainability: no live network/LLM calls in tests."""
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError
from app.main import app
from app.store import DemoStore
from app.models import Incident,DataProvenance,TrafficSensor,MapAction,AgentRequest
from app.scenario import INCIDENTS,VEHICLES,DELIVERIES,DEPOT
from app.services.incident_policy import incident_status,eligible_incidents
from app.services.road_risk import evaluate_selected_road_legs
from app.services.matrix_optimizer import RoadCostMatrix,optimize_road_matrix
from app.services.road_plans import build_road_network_plan
from app.services.decision_explain import scenario_payload,vehicle_explanation,incident_impact
from app.services.route_traffic import inspect_route_traffic
from app.agents.runner import run_agent
from app.services.geo import distance_km


def sample_matrix():
    points=[DEPOT,*[d.location for d in DELIVERIES]]
    return RoadCostMatrix(('DEPOT',*[d.id for d in DELIVERIES]),
      tuple(tuple(round(distance_km(a,b)*4.7,4) for b in points) for a in points),
      tuple(tuple(round(distance_km(a,b)*1.25,4) for b in points) for a in points))

async def fake_street(points):
    # Synthetic polylines from a mocked provider; they are not called actual Madrid geometry.
    return list(points),len(points)*1.4,len(points)*3.6

async def fake_matrix(points):
    m=sample_matrix()
    return {'minutes':[list(x) for x in m.minutes],'kilometres':[list(x) for x in m.kilometres]}


def test_scheduled_incident_outside_window_not_penalized():
    now=datetime(2026,11,4,16,0,tzinfo=ZoneInfo('Europe/Madrid'))
    live=DataProvenance(origin='municipal_open_data',label='Madrid')
    night=Incident(id='night',title='Nocturnal tunnel warning',location=(-3.7,40.42),
       kind='closure',severity='high',starts_at='04/11/2026 23:00',ends_at='05/11/2026 06:00',
       detail='Scheduled',provenance=live)
    unknown=night.model_copy(update={'id':'unknown','starts_at':None,'ends_at':None})
    ongoing=night.model_copy(update={'id':'ongoing','starts_at':'04/11/2026 14:00','ends_at':'04/11/2026 19:00'})
    assert incident_status(night,now)=='outside_window'
    assert incident_status(ongoing,now)=='active'
    assert incident_status(unknown,now)=='unknown'
    included,statuses=eligible_incidents([night,ongoing,unknown],now)
    assert [x.id for x in included]==['ongoing']
    assert not any(status['verified_road_closure'] for status in statuses)


def test_road_risk_uses_provider_polyline_not_straight_chord():
    a=(-3.710,40.412);b=(-3.690,40.412)
    # Point far north of the direct chord, on the mock provider's road detour.
    i=INCIDENTS[0].model_copy(update={'id':'detour','location':(-3.700,40.420),'radius_m':130})
    matrix=RoadCostMatrix(('DEPOT','D-101'),((0,12),(12,0)),((0,4.5),(4.5,0)))
    async def detour(points):return [points[0],i.location,points[-1]],4.5,12
    observed,proof=asyncio.run(evaluate_selected_road_legs(matrix,{'DEPOT':a,'D-101':b},[i],detour,
                           [{'V-01':['D-101']}]))
    assert [x.id for x in observed['DEPOT','D-101']]==['detour']
    assert proof['candidate_space_complete'] is False
    assert proof['verified_road_closures']==0


def test_all_three_scenarios_have_street_routes_and_reconstruct_leg_costs():
    store=DemoStore()
    plan=asyncio.run(build_road_network_plan(store,fake_street,matrix_fetcher=fake_matrix,explainable=True))
    bundle=scenario_payload(store)
    assert bundle['plan_id']==plan.id
    assert bundle['B'] is not None and bundle['C'] is not None
    assert bundle['B']['id']!=bundle['C']['id']
    for label in 'ABC':
        assert len(bundle[label]['routes'])==3
        assert all(x['fidelity']=='road_network' for x in bundle[label]['routes'])
        stops=[sid for r in bundle[label]['routes'] for sid in r['stop_ids']]
        assert sorted(stops)==sorted(d.id for d in DELIVERIES)
    for vehicle in VEHICLES:
        detail=vehicle_explanation(store,vehicle.id)
        for label in ('B','C'):
            row=detail['scenarios'][label]
            assert row['has_leg_detail']
            original=store.decision_context['breakdown'][label][vehicle.id]
            assert abs(sum(x['road_km'] for x in row['legs'])-original['road_km'])<.03
            assert all(not i['verified_road_closure'] for x in row['legs'] for i in x['nearby_incidents'])
    assert bundle['risk_evidence']['candidates_fully_checked']
    assert bundle['risk_evidence']['candidate_space_complete'] is False
    assert not bundle['risk_evidence']['verified_road_closures']


def test_ablation_individual_does_not_invent_causal_road_effect():
    store=DemoStore()
    asyncio.run(build_road_network_plan(store,fake_street,matrix_fetcher=fake_matrix,explainable=True))
    impact=incident_impact(store,INCIDENTS[0].id)
    assert impact['candidate_ablation']['method']=='same_candidate_pool_with_one_event_removed'
    assert impact['causal_route_change_measured'] is False
    assert impact['restriction_verified'] is False
    assert impact['candidate_ablation']['selection_changed'] in (True,False)


def test_route_sensor_point_has_real_fields_but_unknown_duration():
    store=DemoStore()
    asyncio.run(build_road_network_plan(store,fake_street,matrix_fetcher=fake_matrix,explainable=True))
    first=store.proposed.routes[0]
    coord=first.coordinates[0]
    store.traffic_points=[TrafficSensor(id='sensor-a',location=coord,intensity_vph=1245,
                                         occupancy_pct=78,speed_kmh=12,service_level=3)]
    store.traffic_observed_at='2026-11-04T15:00:00Z'
    measured=inspect_route_traffic(store,first.vehicle_id,'C')
    assert measured['sampled_nearby_count']==1
    assert measured['congested_nearby_count']==1
    assert measured['congestion_duration_minutes'] is None
    assert measured['observations'][0]['speed_kmh']==12
    assert measured['observations'][0]['occupancy_pct']==78


def test_agent_read_only_does_not_reset_approved_plan_or_routing(monkeypatch):
    from app.settings import get_settings
    settings=get_settings()
    monkeypatch.setattr(settings,'agent_provider','demo')
    store=DemoStore()
    plan=store.replan()
    store.approve(plan.id)
    before=store.generation
    result=run_agent(store,AgentRequest(message='Explica la ruta V-02 sin regenerarla'))
    assert store.generation==before
    assert store.approved is not None
    assert store.proposed.id==plan.id
    assert result.proposed_plan is None
    assert not any(trace.tool == 'prepare_dispatch_proposal' for trace in result.traces)
    assert result.map_actions[0].type=='open_map'
    assert result.map_actions[1].value=='V-02'
    with pytest.raises(ValidationError):MapAction(type='approve',value='yes')
