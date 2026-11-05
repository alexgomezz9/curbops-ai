from app.scenario import VEHICLES,DELIVERIES,INCIDENTS,DEPOT
from app.services.planner import calculate_plan,optimize_assignments
from app.services.geo import distance_km,point_segment_km
from app.store import DemoStore
from app.models import SourceMode


def test_plan_has_every_delivery_once_and_respects_vehicle_capacities():
    proposed=calculate_plan(VEHICLES,DELIVERIES,INCIDENTS,True)
    actual=[stop for route in proposed.routes for stop in route.stop_ids]
    assert sorted(actual)==sorted(d.id for d in DELIVERIES)
    lookup={x.id:x for x in DELIVERIES}
    for route in proposed.routes:
        cap=next(v.capacity for v in VEHICLES if v.id==route.vehicle_id)
        assert sum(lookup[s].load_units for s in route.stop_ids)<=cap
        assert route.coordinates[0]==DEPOT and route.coordinates[-1]==DEPOT
        assert route.fidelity=='illustrative'


def test_optimized_objective_not_worse_than_initial():
    base=calculate_plan(VEHICLES,DELIVERIES,INCIDENTS,False)
    proposed=calculate_plan(VEHICLES,DELIVERIES,INCIDENTS,True)
    assert proposed.metrics.score <= base.metrics.score
    assert proposed.id != base.id


def test_approval_requires_matching_proposal_id():
    db=DemoStore()
    plan=db.replan()
    try:db.approve('old-id'); assert False
    except ValueError:pass
    approved=db.approve(plan.id)
    assert approved.status=='approved'
    db.reset()
    assert db.proposed is None and db.approved is None


def test_metric_distances():
    assert distance_km(DEPOT,DEPOT)==0
    assert point_segment_km(DEPOT,DEPOT,(-3.704,40.425))<.01
