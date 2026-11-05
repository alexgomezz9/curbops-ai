"""Regression tests for v1.2: automatic road planning, provenance and fail-closed UI contracts.

External routing provider responses are mocked, not claimed to be verified live.
"""
import asyncio
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.store import store
from app.models import SourceMode
from app.settings import get_settings
from app.services.road_plans import build_road_network_plan
from app.agents import runner

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_state():
    store.reset()
    store.source_mode = SourceMode.demo
    yield
    store.reset()


def test_agent_tool_calculates_both_plans_and_emits_six_actual_network_steps(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, 'routing_provider', 'osrm_demo')
    events, calls = [], []

    async def fake_roads(points):
        calls.append(points)
        return list(points), float(len(points)) * 1.25, float(len(points)) * 3

    monkeypatch.setattr(runner, 'fetch_road_route', fake_roads)
    explanation = runner._model_plan_summary(store, events.append)
    snap = store.snapshot()
    assert len([p for p in calls if len(p)>2]) == 9
    assert len([x for x in events if x['type'] == 'routing.route_completed']) == 9
    assert [x['completed'] for x in events if x['type'] == 'routing.route_completed'] == list(range(1, 10))
    assert events[-1]['type'] == 'routing.completed'
    assert all(r.fidelity == 'road_network' for r in snap.original_plan.routes)
    assert all(r.fidelity == 'road_network' for r in snap.proposed_plan.routes)
    assert 'REAL STREET NETWORK' in explanation
    assert 'NOT live traffic ETAs' in explanation
    assert 'NOT' in snap.proposed_plan.explanation


def test_routing_failure_does_not_publish_schematic_plan(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, 'routing_provider', 'osrm_demo')
    events = []
    counter = 0

    async def flaky(points):
        nonlocal counter
        counter += 1
        if counter == 4:
            raise RuntimeError('provider unavailable')
        return list(points), 3.0, 5.0

    monkeypatch.setattr(runner, 'fetch_road_route', flaky)
    message = runner._model_plan_summary(store, events.append)
    assert 'No plan generated' in message
    assert store.proposed is None
    assert store.road_baseline is None
    assert any(e['type'] == 'routing.failed' for e in events)
    assert not any(e['type'] == 'routing.completed' for e in events)


def test_routing_disabled_tool_does_not_publish_mock_plan(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, 'routing_provider', 'illustrative')
    msg = runner._model_plan_summary(store)
    assert 'disabled' in msg
    assert store.proposed is None


def test_legacy_schematic_endpoint_is_blocked_when_real_routing_configured(monkeypatch):
    import app.main as main_mod
    monkeypatch.setattr(main_mod.settings, 'routing_provider', 'osrm_demo')
    response = client.post('/api/replan', json={'include_incidents': True})
    assert response.status_code == 409
    assert store.proposed is None


def test_all_six_routes_committed_atomically_and_audit_uses_road_metrics(monkeypatch):
    import app.main as main_mod
    settings = get_settings()
    monkeypatch.setattr(settings, 'routing_provider', 'osrm_demo')
    monkeypatch.setattr(main_mod.settings, 'routing_provider', 'osrm_demo')

    async def fake_roads(points):
        return list(points), len(points) * 2.0, len(points) * 4.0

    monkeypatch.setattr(main_mod, 'fetch_road_route', fake_roads)
    result = client.post('/api/replan/road-network')
    assert result.status_code == 200, result.text
    snap = client.get('/api/mission').json()
    assert all(route['fidelity'] == 'road_network' for route in snap['original_plan']['routes'])
    assert all(route['fidelity'] == 'road_network' for route in snap['proposed_plan']['routes'])
    audit = client.get('/api/decision/audit').json()
    assert audit['comparable'] is True
    assert audit['distance_delta_km'] == round(snap['original_plan']['metrics']['distance_km']-snap['proposed_plan']['metrics']['distance_km'],2)


def test_sse_agent_streams_six_route_events_then_real_street_result(monkeypatch):
    import json
    settings = get_settings()
    monkeypatch.setattr(settings, 'routing_provider', 'osrm_demo')
    monkeypatch.setattr(settings, 'agent_provider', 'demo')

    async def fake_roads(points):
        return list(points), float(len(points)) * 1.7, float(len(points)) * 3.4

    monkeypatch.setattr(runner, 'fetch_road_route', fake_roads)
    with client.stream('POST', '/api/agent/stream',
                       json={'message': 'Prepare an alternative delivery plan'}) as response:
        events = [json.loads(line[6:]) for line in response.iter_lines() if line.startswith('data: ')]
    assert response.status_code == 200
    assert [e['completed'] for e in events if e['type'] == 'routing.route_completed'] == [1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert events[-1]['type'] == 'result'
    result = events[-1]['result']
    assert result['proposed_plan'] is not None
    assert {r['fidelity'] for r in result['proposed_plan']['routes']} == {'road_network'}
    assert store.snapshot().original_plan.routes[0].fidelity == 'road_network'


def test_inflight_route_invalidated_by_new_investigation(monkeypatch):
    async def pretend_roads(points):
        store.begin_investigation()
        return list(points), 1., 2.
    with pytest.raises(RuntimeError, match='Mission changed'):
        asyncio.run(build_road_network_plan(store, pretend_roads))
    assert store.proposed is None
    assert store.road_baseline is None
