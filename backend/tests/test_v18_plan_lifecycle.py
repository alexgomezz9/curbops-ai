"""Regression coverage for the portfolio MVP: no invented closure and correct plan lifecycle."""
from datetime import datetime, timedelta, timezone
import pytest
from app.models import DataProvenance,Incident,SourceMode
from app.store import DemoStore
from app.services.decision_explain import scenario_payload
from app.services.rehearsal import set_rehearsal
from app.scenario import DEPOT


def municipal_notice(point):
    now=datetime.now(timezone.utc)
    return Incident(id='Madrid-fixture',title='Municipal notice (fixture)',location=point,
                    kind='closure',severity='medium',radius_m=100,detail='Not a confirmed road block',
                    starts_at=(now-timedelta(minutes=10)).isoformat(),
                    ends_at=(now+timedelta(minutes=10)).isoformat(),
                    provenance=DataProvenance(origin='municipal_open_data',label='fixture'))


def road_demo():
    demo=DemoStore()
    b=demo.original.model_copy(deep=True)
    b.routes[0].coordinates=[DEPOT,(-3.713,40.420),(-3.715,40.423),(-3.713,40.426),(-3.710,40.429),DEPOT]
    b.routes[0].fidelity='road_network'
    demo.no_risk_plan=b
    demo.proposed=b.model_copy(update={'id':'simulated-proposal','status':'proposed'})
    return demo


def test_incident_refresh_stales_existing_proposal_without_reoptimizing():
    demo=road_demo()
    demo.source_mode=SourceMode.live
    demo.override_incidents=[municipal_notice((-3.713,40.423))]
    demo.planned_incident_signature=demo.incident_signature()
    previous=demo.proposed
    assert scenario_payload(demo)['plan_stale'] is False
    demo.override_incidents=[municipal_notice((-3.714,40.423))]
    assert scenario_payload(demo)['plan_stale'] is True
    assert demo.proposed is previous
    with pytest.raises(ValueError,match='replan before approving'):
        demo.approve(previous.id)
    # Sensor updates alone are observational: B/C use base OSRM times.
    demo.traffic_fetched_at='new snapshot'
    assert scenario_payload(demo)['plan_stale'] is True
    demo.planned_incident_signature=demo.incident_signature()
    assert scenario_payload(demo)['plan_stale'] is False


def test_rehearse_published_notice_as_explicit_synthetic_hypothesis():
    demo=road_demo()
    demo.source_mode=SourceMode.live
    demo.override_incidents=[municipal_notice((-3.715,40.423))]
    impact=set_rehearsal(demo,'V-01',incident_id='Madrid-fixture')
    assert impact is not None
    assert impact.id=='SIM-ROADWORKS'
    assert impact.provenance.origin=='synthetic'
    assert 'Madrid-fixture' in impact.title
    assert demo.proposed is None
    assert any(i.id=='Madrid-fixture' and i.provenance.origin=='municipal_open_data' for i in demo.incidents)
    assert demo.approved is None


def test_rehearsal_rejects_distant_notice_and_preserves_plan():
    demo=road_demo()
    demo.source_mode=SourceMode.live
    demo.override_incidents=[municipal_notice((-3.65,40.47))]
    proposal=demo.proposed
    generation=demo.generation
    with pytest.raises(ValueError,match='too far'):
        set_rehearsal(demo,'V-01',incident_id='Madrid-fixture')
    assert demo.proposed is proposal and demo.generation==generation
