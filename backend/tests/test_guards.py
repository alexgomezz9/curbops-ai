from fastapi.testclient import TestClient
from app.main import app
from app.store import store
from app.models import SourceMode

client=TestClient(app)

def test_no_unapproved_approval_and_source_mode_restriction():
    store.reset()
    store.source_mode=SourceMode.demo
    store.override_incidents=None
    store.override_cameras=None
    store.override_zones=None
    res=client.post('/api/approve',json={'plan_id':'invalid','reviewer':'Human reviewer'})
    assert res.status_code==409
    res=client.post('/api/mode',json={'mode':'live'})
    assert res.status_code==409
    assert client.get('/api/mission').json()['source_mode']=='demo'


def test_external_routing_disabled_by_default():
    res=client.get('/api/routing/availability')
    assert res.status_code==200
    if res.json()['enabled'] is False:
        q=client.post('/api/replan/road-network')
        assert q.status_code==409
        assert 'disabled' in q.json()['detail']


def test_tools_do_not_grant_approval():
    store.reset()
    answer=client.post('/api/agent/run',json={'message':'Optimize Madrid delivery routes'}).json()
    assert answer['actions_require_approval'] is True
    assert store.approved is None
    store.reset()
