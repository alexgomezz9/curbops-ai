from app.integrations.madrid import parse_traffic_xml
from app.main import app
from fastapi.testclient import TestClient
from app.store import store
from app.models import TrafficSensor


def test_traffic_parser_utm_and_missing_data():
    # UTM coordinate near central Madrid; negative measurements mean missing observations.
    xml=b'<root><pm><idelem>52</idelem><st_x>440000</st_x><st_y>4474000</st_y><intensidad>1200</intensidad><ocupacion>21</ocupacion><nivelServicio>3</nivelServicio><velocidad>18</velocidad></pm><pm><idelem>99</idelem><st_x>440000</st_x><st_y>4474000</st_y><intensidad>-1</intensidad><ocupacion>-1</ocupacion><velocidad>-1</velocidad><nivelServicio>-1</nivelServicio></pm></root>'
    rows,total,_=parse_traffic_xml(xml)
    assert total==1 and len(rows)==1
    assert rows[0].id=='52' and rows[0].service_level==3
    assert -4<rows[0].location[0]<-3.3
    assert 40.2<rows[0].location[1]<40.7


def test_signals_endpoint_empty_without_external_fetch():
    c=TestClient(app)
    with store.lock:
        previous=list(store.traffic_points)
        store.traffic_points=[]
    try:
        r=c.get('/api/signals')
        assert r.status_code==200
        assert r.json()['status']=='unavailable'
        assert r.json()['points']==[]
    finally:
        with store.lock:store.traffic_points=previous


def test_signals_endpoint_actual_only():
    c=TestClient(app)
    with store.lock:
        old=list(store.traffic_points)
        store.traffic_points=[TrafficSensor(id='x',location=(-3.7,40.42),intensity_vph=400,service_level=2)]
    try:
        j=c.get('/api/signals').json()
        assert j['status']=='municipal_open_data'
        assert j['distribution']['delayed']==1
        assert j['points'][0]['intensity_vph']==400
    finally:
        with store.lock:store.traffic_points=old


def test_refresh_integrates_real_only_sensors(monkeypatch):
    """E2E backend contract with mocked official fetch; no outbound calls."""
    import app.main as main_mod
    from app.models import Incident,DataProvenance,LoadingZone,Camera,SourceMode
    from datetime import datetime,timezone
    from types import SimpleNamespace
    clock = [0.0]
    fetched = []
    provenance=DataProvenance(origin='municipal_open_data',label='test official fixture')
    async def fake_fetch(kind):
        fetched.append(kind)
        if kind=='traffic':
            return ([TrafficSensor(id='m-123',location=(-3.70,40.42),service_level=3,intensity_vph=850)],1,'2026-11-03T20:00:00')
        if kind=='incidents':
            return [Incident(id='m-i',title='Municipal incident',location=(-3.7,40.42),kind='roadworks',severity='medium',radius_m=100,detail='test',provenance=provenance)]
        if kind=='cameras':
            return [Camera(id='m-c',label='Camera',location=(-3.7,40.42),provenance=provenance)]
        return [LoadingZone(id='m-z',label='Loading reserve',location=(-3.7,40.42),district='Madrid',provenance=provenance)]
    saved={key:getattr(store,key) for key in ['traffic_points','traffic_total_valid','traffic_fetched_at','traffic_observed_at','previous_traffic_points','previous_traffic_fetched_at','traffic_source_error','override_incidents','override_cameras','override_zones','source_mode','live_last_fetch','live_errors']}
    old_refresh=main_mod._last_refresh
    try:
        monkeypatch.setattr(main_mod,'fetch_source',fake_fetch)
        monkeypatch.setattr(main_mod,'time',SimpleNamespace(monotonic=lambda:clock[0]))
        main_mod._last_refresh=None
        client=TestClient(app)
        response=client.post('/api/sources/refresh')
        assert response.status_code==200
        assert set(response.json()['results'])=={'traffic','incidents','cameras','loading'}
        assert all(x['ok'] for x in response.json()['results'].values())
        assert len(fetched)==4
        assert client.post('/api/sources/refresh').status_code==429
        assert len(fetched)==4
        clock[0] += main_mod.settings.source_refresh_min_seconds
        assert client.post('/api/sources/refresh').status_code==200
        assert len(fetched)==8
        assert client.post('/api/mode',json={'mode':'live'}).status_code==200
        assert client.get('/api/signals').json()['points'][0]['id']=='m-123'
        assert client.get('/api/mission').json()['sources'][3]['connected'] is True
    finally:
        with store.lock:
            for name,value in saved.items():setattr(store,name,value)
        main_mod._last_refresh=old_refresh
