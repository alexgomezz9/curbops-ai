"""Geographic context stays separate from eligible optimization signals."""
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.models import Incident,DataProvenance,SourceMode
from app.store import DemoStore,store
from app.services.route_corridor import vehicle_corridor,incident_fleet_corridor


def notice(ident, at, when='active',origin='municipal_open_data'):
    start=(at-timedelta(hours=1)).isoformat() if when=='active' else None
    end=(at+timedelta(hours=1)).isoformat() if when=='active' else None
    if when=='past':
        start=(at-timedelta(days=2)).isoformat();end=(at-timedelta(days=1)).isoformat()
    return Incident(id=ident,title='Fixture '+ident,location=(-3.70,40.42),kind='roadworks',
                    severity='medium',radius_m=250,detail='test only',starts_at=start,ends_at=end,
                    provenance=DataProvenance(origin=origin,label='fixture'))


def seed():
    demo=DemoStore()
    base=demo.original.model_copy(deep=True)
    base.id='road-v16';base.routes[0].fidelity='road_network'
    base.routes[0].coordinates=[(-3.701,40.421),(-3.700,40.420),(-3.699,40.419)]
    base.routes[0].incidents_near=['active']
    for route in base.routes[1:]:
        route.fidelity='road_network';route.coordinates=[(-3.8,40.46),(-3.8,40.47)]
    demo.road_baseline=base
    demo.no_risk_plan=base.model_copy(deep=True)
    demo.proposed=base.model_copy(deep=True)
    at=datetime.now(timezone.utc)
    demo.source_mode=SourceMode.live
    demo.override_incidents=[notice('active',at),notice('past',at,when='past'),notice('unknown',at,when='unknown'),
                             Incident(id='far',title='Far',location=(-3.4,40.8),kind='roadworks',severity='high',radius_m=100,detail='test',provenance=DataProvenance(origin='municipal_open_data',label='fixture'))]
    demo.decision_context={'temporal_evidence':[{'id':'active','temporal_status':'active'},
                 {'id':'past','temporal_status':'outside_window'},
                 {'id':'unknown','temporal_status':'unknown'}],
                 'breakdown':{'C':{'V-01':{'legs':[{'incidents':[{'id':'active'}]}]}}}}
    return demo


def test_corridor_includes_all_nearby_but_marks_only_applied():
    demo=seed(); report=vehicle_corridor(demo,'V-01','C')
    assert report['nearby_count']==3
    assert report['applied_count']==1
    by_id={x['id']:x for x in report['nearby_incidents']}
    assert by_id['active']['applied_to_optimizer']
    assert not by_id['past']['applied_to_optimizer']
    assert by_id['unknown']['temporal_status']=='unknown'
    assert 'far' not in by_id
    assert all(not x['restriction_verified'] for x in report['nearby_incidents'])
    assert vehicle_corridor(demo,'V-01','B')['applied_count']==0


def test_incident_matches_only_road_near_vehicle():
    demo=seed()
    result=incident_fleet_corridor(demo,'active','C')
    assert [x['vehicle_id'] for x in result['nearby_vehicles']]==['V-01']


def test_invalid_scenario_and_unknown_van():
    import pytest
    demo=seed()
    with pytest.raises(ValueError):vehicle_corridor(demo,'V-99')
    with pytest.raises(ValueError):vehicle_corridor(demo,'V-01','X')
    with pytest.raises(ValueError):incident_fleet_corridor(demo,'missing','C')


def test_http_endpoint_is_read_only():
    store.reset()
    client=TestClient(app)
    assert client.get('/api/decision/vehicles/V-99/corridor').status_code==409
    assert client.get('/api/decision/incidents/nonexistent/fleet').status_code==409
    assert store.proposed is None
