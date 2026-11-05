"""Incomplete LLM runs must never masquerade as completed offline workflows."""
from types import SimpleNamespace
from app.agents import runner
from app.store import DemoStore
from app.models import AgentRequest, MapAction


def test_graph_recursion_is_explicit_without_fabricated_demo_calls(monkeypatch):
    class GraphRecursionError(Exception):pass
    monkeypatch.setattr(runner,'get_settings',lambda:SimpleNamespace(agent_provider='google',google_api_key='placeholder',groq_api_key=''))
    def fail(*args,**kwargs):raise GraphRecursionError('limit')
    monkeypatch.setattr(runner,'_try_real_agent',fail)
    monkeypatch.setattr(runner,'_respond_demo',lambda *a,**k: (_ for _ in ()).throw(AssertionError('must not call offline demo')))
    events=[]
    output=runner.run_agent(DemoStore(),AgentRequest(message='Inspect vehicle V-01'),events.append)
    assert output.mode=='agent_error'
    assert output.traces==[]
    assert events[-1]['type']=='session.failed'
    assert 'execution limit' in output.summary


def test_allowlisted_route_sensor_map_action():
    action=MapAction(type='highlight_route_sensors',value='V-03:C',generation=1)
    assert action.type=='highlight_route_sensors'
