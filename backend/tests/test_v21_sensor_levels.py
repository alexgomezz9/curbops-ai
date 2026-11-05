"""Level 0–3 observations support screening, not synthetic travel ETAs."""
from app.services.route_traffic import inspect_route_traffic
from app.services.fleet_impact import fleet_impact
from app.models import TrafficSensor
from app.store import DemoStore


def test_sensor_service_levels_are_exposed_but_do_not_rewrite_routes():
    store=DemoStore()
    plan=store.original.model_copy(deep=True)
    for route in plan.routes:
        route.coordinates=[(-3.701,40.421),(-3.700,40.420),(-3.699,40.419)]
        route.fidelity='road_network'
    store.road_baseline=plan
    store.proposed=plan.model_copy(deep=True)
    store.traffic_points=[
        TrafficSensor(id='s3',location=(-3.7,40.42),service_level=3),
        TrafficSensor(id='s1',location=(-3.7003,40.4203),service_level=1),
    ]
    before=store.proposed.model_dump()
    observation=inspect_route_traffic(store,'V-01','C')
    assert observation['service_level_counts']['3']==1
    assert observation['service_level_counts']['1']==1
    report=fleet_impact(store)
    assert report['vehicles'][0]['sensor_advisory_points']==4
    assert 'NOT a route cost or ETA' in report['interpretation']
    assert store.proposed.model_dump()==before
