from fastapi.testclient import TestClient
from app.main import app
from app.store import store
from app.services.evidence import distance_m, incident_evidence
from app.models import TrafficSensor

client=TestClient(app)


def test_geodistance_accuracy():
    assert distance_m((-3.7,40.42),(-3.7,40.42))==0
    assert 800 < distance_m((-3.7,40.42),(-3.69,40.42)) < 900


def test_evidence_is_geographic_and_explicit_about_provenance():
    client.post('/api/mode',json={'mode':'demo'})
    snap=client.get('/api/mission').json()
    incident_id=snap['incidents'][0]['id']
    resp=client.get(f'/api/intelligence/incidents/{incident_id}?radius_m=800')
    assert resp.status_code==200
    result=resp.json()
    assert result['incident']['id']==incident_id
    assert result['radius_m']==800
    assert result['calculation']=='haversine_proximity'
    assert 'not connectivity or evidence' in result['note']
    assert result['incident']['provenance']['origin']=='synthetic'


def test_validation_unknown_and_limits():
    assert client.get('/api/intelligence/incidents/DOES-NOT-EXIST').status_code==404
    assert client.get('/api/intelligence/incidents/DOES-NOT-EXIST?radius_m=50000').status_code==422


def test_real_sensor_near_incident_is_reported_with_sample_caveat():
    snap=store.snapshot();incident=snap.incidents[0]
    with store.lock:
        old=store.traffic_points;oldtotal=store.traffic_total_valid
        store.traffic_points=[TrafficSensor(id='TEST-01',location=incident.location,
                                            service_level=3,speed_kmh=14)]
        store.traffic_total_valid=999
    try:
        evidence=incident_evidence(store,incident.id)
        assert evidence is not None
        assert evidence['sensor_count_nearby']==1
        assert evidence['congested_sensor_count']==1
        assert evidence['sensors'][0]['distance_m']==0
        assert evidence['sensor_records_total_reported']==999
    finally:
        with store.lock:
            store.traffic_points=old;store.traffic_total_valid=oldtotal
