"""No external traffic/geocoding services are contacted by these tests."""
from __future__ import annotations
import importlib
import pytest
from fastapi.testclient import TestClient
from app.main import app, settings
from app.models import SourceMode
from app.store import store
from app.services import routing

client = TestClient(app)
main = importlib.import_module('app.main')

@pytest.fixture(autouse=True)
def reset_plan():
    store.reset()
    store.source_mode = SourceMode.demo
    yield
    store.reset()


def test_road_baseline_and_proposal_use_same_provider(monkeypatch):
    monkeypatch.setattr(settings, 'routing_provider', 'osrm_demo')
    requests = []
    async def pretend_roads(points, avoid_polygons=None):
        requests.append(points)
        assert 2 <= len(points) <= 10
        return list(points), float(len(points)) * 1.4, float(len(points)) * 3
    monkeypatch.setattr(main, 'fetch_road_route', pretend_roads)
    result = client.post('/api/replan/road-network')
    assert result.status_code == 200, result.text
    snap = client.get('/api/mission').json()
    assert len([points for points in requests if len(points)>2]) == 9
    assert len(requests) >= 9
    assert {r['fidelity'] for r in snap['original_plan']['routes']} == {'road_network'}
    assert {r['fidelity'] for r in snap['proposed_plan']['routes']} == {'road_network'}
    assert snap['approved_plan'] is None
    audit = client.get('/api/decision/audit').json()
    assert audit['comparable'] is True
    assert 'street-network provider' in audit['limitations'][1].lower()
    assert len(audit['vehicles']) == 3
    assert client.post('/api/approve',json={'plan_id':result.json()['id']}).status_code == 200


def test_partial_network_failure_does_not_commit_mixed_plans(monkeypatch):
    monkeypatch.setattr(settings, 'routing_provider', 'osrm_demo')
    before=store.replan(include_incidents=True).model_dump()  # Legacy HTTP endpoint is disabled for real-street mode
    count=0
    async def flaky(points,avoid_polygons=None):
        nonlocal count
        count+=1
        if count==4:
            raise RuntimeError('remote server unavailable')
        return list(points), 4., 10.
    monkeypatch.setattr(main, 'fetch_road_route', flaky)
    response=client.post('/api/replan/road-network')
    assert response.status_code==502
    snap=client.get('/api/mission').json()
    assert snap['proposed_plan']['id']==before['id']
    assert all(r['fidelity']=='illustrative' for r in snap['original_plan']['routes'])


def test_public_demo_requires_opt_in_and_disabled_error(monkeypatch):
    monkeypatch.setattr(settings, 'routing_provider', 'illustrative')
    response=client.post('/api/replan/road-network')
    assert response.status_code==409
    assert client.get('/api/routing/availability').json()['enabled'] is False
    monkeypatch.setattr(settings,'routing_provider','osrm_demo')
    status=client.get('/api/routing/availability').json()
    assert status['enabled'] is True
    assert 'no SLA' in status['note']


def test_osrm_rejects_unallowed_points_and_incident_polygons(monkeypatch):
    from app.settings import get_settings
    config=get_settings()
    monkeypatch.setattr(config,'routing_provider','osrm_demo')
    with pytest.raises(ValueError):
        import asyncio
        asyncio.run(routing.fetch_road_route([(-3.7,40.4),(-12.,45.)]))
    with pytest.raises(ValueError):
        import asyncio
        asyncio.run(routing.fetch_road_route([(-3.7,40.4),(-3.71,40.42)],avoid_polygons={'type':'Polygon'}))


def test_osrm_response_parsing_and_in_process_cache(monkeypatch):
    """Validate the wire format without calling the external OSRM demonstration server."""
    import asyncio
    from app.settings import get_settings
    config = get_settings()
    monkeypatch.setattr(config, 'routing_provider', 'osrm_demo')
    routing._cache.clear()
    monkeypatch.setattr(routing, '_osrm_last_request', 0.0)
    calls=[]
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {'code':'Ok','routes':[{'distance':4700.5,'duration':730.,
                'geometry':{'type':'LineString','coordinates':[
                    [-3.7,40.42],[-3.703,40.421],[-3.71,40.43]]}}]}
    class Client:
        def __init__(self,*a,**kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*a): pass
        async def get(self,url,params):
            calls.append((url,params))
            return Response()
    monkeypatch.setattr(routing.httpx,'AsyncClient',Client)
    points=[(-3.7,40.42),(-3.71,40.43)]
    async def check():
        first=await routing.fetch_road_route(points)
        second=await routing.fetch_road_route(points)
        assert first==second
        assert len(calls)==1
        assert first[1]==4.7005
        assert first[2]==730/60
        assert first[0][1]==(-3.703,40.421)
        assert 'geometries' in calls[0][1]
    asyncio.run(check())
