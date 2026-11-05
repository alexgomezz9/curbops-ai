from fastapi.testclient import TestClient
from app.main import app
from app.store import store

client=TestClient(app)

def test_demo_api_workflow(monkeypatch):
    import app.main as main_mod
    monkeypatch.setattr(main_mod.settings, 'routing_provider', 'illustrative')  # legacy API coverage only
    client.post('/api/reset')
    r=client.get('/api/mission')
    assert r.status_code==200
    payload=r.json()
    assert payload['simulation'] is True
    assert len(payload['deliveries'])==15
    assert payload['source_mode']=='demo'
    assert all(x['provenance']['origin']=='synthetic' for x in payload['incidents'])
    proposed=client.post('/api/replan',json={'include_incidents':True}).json()
    assert proposed['status']=='proposed'
    approved=client.post('/api/approve',json={'plan_id':proposed['id'],'reviewer':'Portfolio tester'}).json()
    assert approved['status']=='approved'
    client.post('/api/reset')


def test_agent_no_key_is_explicit_fallback(monkeypatch):
    monkeypatch.setenv('AGENT_PROVIDER','demo')
    get_settings=__import__('app.settings',fromlist=['get_settings']).get_settings
    get_settings.cache_clear()
    monkeypatch.setattr(get_settings(), 'routing_provider', 'illustrative')
    r=client.post('/api/agent/run',json={'message':'Replan all routes for our fleet'})
    assert r.status_code==200
    result=r.json()
    assert result['mode']=='deterministic_demo'
    assert any('no LLM was called' in w for w in result['warnings'])
    assert result['proposed_plan'] is None  # No fake road plan when provider is disabled
    client.post('/api/reset')


def test_agent_stream_reports_actual_tool_events_without_llm(monkeypatch):
    import json
    from app.settings import get_settings
    monkeypatch.setenv('AGENT_PROVIDER','demo')
    get_settings.cache_clear()
    monkeypatch.setattr(get_settings(), 'routing_provider', 'illustrative')
    client.post('/api/reset')
    with client.stream('POST','/api/agent/stream',json={'message':'Replan deliveries around incidents'}) as response:
        assert response.status_code == 200
        assert response.headers['content-type'].startswith('text/event-stream')
        payloads = [json.loads(line[6:]) for line in response.iter_lines() if line.startswith('data: ')]
    names = [event['type'] for event in payloads]
    assert names[0]=='session.started'
    assert 'tool.started' in names
    assert 'tool.completed' in names
    assert names[-1]=='result'
    assert payloads[-1]['result']['mode']=='deterministic_demo'
    assert len(payloads[-1]['result']['traces'])>=3
    client.post('/api/reset')


def test_gemini_multimodal_content_is_rendered_as_text_only():
    from app.agents.runner import readable_content
    blocks=[{'type':'reasoning','text':'PRIVATE THINKING'},
            {'type':'text','text':'Resumen de la operación'},
            {'type':'tool_call','name':'inspect_fleet'}]
    assert readable_content(blocks)=='Resumen de la operación'
    assert readable_content(str(blocks))=='Resumen de la operación'


def test_model_tier_is_optional_and_validated(monkeypatch):
    monkeypatch.setenv('AGENT_PROVIDER', 'demo')
    from app.settings import get_settings
    get_settings.cache_clear()
    valid = client.post('/api/agent/run', json={'message': 'Analyze routes', 'model_tier': 'advanced'})
    assert valid.status_code == 200
    assert valid.json()['mode'] == 'deterministic_demo'
    assert valid.json()['model_requests_observed'] is None
    invalid = client.post('/api/agent/run', json={'message': 'Analyze routes', 'model_tier': 'unknown'})
    assert invalid.status_code == 422
    get_settings.cache_clear()
