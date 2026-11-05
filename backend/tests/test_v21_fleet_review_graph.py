"""Review workflow is a real LangGraph and cannot silently dispatch or alter routes."""
import pytest
pytest.importorskip("langgraph", reason="LangGraph installed in the Docker API image; unavailable in this offline artifact runner")
from app.services.fleet_review_graph import review_fleet_graph
from app.services.route_traffic import inspect_route_traffic
from app.models import TrafficSensor
from app.store import DemoStore


def road_fixture():
    store=DemoStore()
    baseline=store.original.model_copy(deep=True)
    for route in baseline.routes:
        route.coordinates=[(-3.701,40.421),(-3.700,40.420),(-3.699,40.419)]
        route.fidelity='road_network'
    store.road_baseline=baseline
    store.no_risk_plan=baseline.model_copy(deep=True)
    store.proposed=baseline.model_copy(deep=True)
    store.traffic_points=[
        TrafficSensor(id='observed-congestion',location=(-3.7,40.42),service_level=3,intensity_vph=600),
        TrafficSensor(id='observed-slow',location=(-3.7003,40.4203),service_level=1,intensity_vph=300),
    ]
    return store


def test_explicit_graph_visits_real_steps_without_mutating_plan():
    store=road_fixture()
    proposal=store.proposed
    steps=[]
    result=review_fleet_graph(store,'C',on_step=steps.append)
    assert steps==['inspect_road_corridors','prioritize_sensor_and_incident_evidence','prepare_read_only_map_actions']
    assert result['workflow']['engine']=='LangGraph StateGraph'
    assert result['workflow']['read_only'] is True
    assert result['recommended_focus'] in {'V-01','V-02','V-03'}
    assert store.proposed is proposal
    assert store.approved is None


def test_sensor_levels_are_observed_advisory_not_route_penalty():
    store=road_fixture()
    report=inspect_route_traffic(store,'V-01','C')
    assert report['service_level_counts']['1']==1
    assert report['service_level_counts']['3']==1
    result=review_fleet_graph(store)
    row=result['vehicles'][0]
    assert row['sensor_service_levels']['3']==1
    assert row['sensor_advisory_points']==4
    assert 'NOT a route cost or ETA' in result['interpretation']
    assert all('sensor' not in str(route.incidents_near).lower() for route in store.proposed.routes)


def test_graph_rejects_unloaded_road_geometry():
    with pytest.raises(ValueError,match='Street geometry'):
        review_fleet_graph(DemoStore(),'A')
