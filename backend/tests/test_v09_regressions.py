"""v0.9 regression: observed incidents with slash IDs + lifecycle approval."""
from fastapi.testclient import TestClient
from app.main import app
from app.store import store
from app.models import Incident,SourceMode,DataProvenance,AgentRequest
from app.agents.runner import run_agent

client=TestClient(app)

def test_slash_containing_municipal_incident_id_is_supported():
    inc=Incident(id='2026/883',title='Official test fixture',location=(-3.70,40.42),
        kind='roadworks',severity='medium',radius_m=160,detail='fixture',
        provenance=DataProvenance(origin='municipal_open_data',label='fixture only'))
    with store.lock:
        prev_mode,prev_incidents=store.source_mode,store.override_incidents
        store.source_mode=SourceMode.live
        store.override_incidents=[inc]
    try:
        response=client.get('/api/intelligence/incidents/2026/883?radius_m=800')
        assert response.status_code==200,response.text
        assert response.json()['incident']['id']=='2026/883'
        encoded=client.get('/api/intelligence/incidents/2026%2F883?radius_m=800')
        assert encoded.status_code==200,encoded.text
    finally:
        with store.lock:
            store.source_mode=prev_mode
            store.override_incidents=prev_incidents

def test_read_only_investigation_preserves_prior_approval():
    store.reset()
    old=store.replan()
    approved=store.approve(old.id)
    assert store.snapshot().approved_plan and approved.status=='approved'
    result=run_agent(store,AgentRequest(message='Explain status of sources'))
    assert result is not None
    assert store.approved is not None
    assert store.snapshot().approved_plan is not None
    store.reset()


def test_reapplying_live_mode_does_not_erase_approved_plan():
    with store.lock:
        old_mode,old_incidents=store.source_mode,store.override_incidents
        store.source_mode=SourceMode.live
        store.override_incidents=[]
    try:
        store.reset()
        plan=store.replan()
        store.approve(plan.id)
        response=client.post('/api/mode',json={'mode':'live'})
        assert response.status_code==200,response.text
        assert response.json()['approved_plan']['id']==plan.id
    finally:
        store.reset()
        with store.lock:
            store.source_mode=old_mode
            store.override_incidents=old_incidents
