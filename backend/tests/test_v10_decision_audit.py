from fastapi.testclient import TestClient
from app.main import app
from app.models import DispatchPlan, PlanMetrics, RouteLine
from app.services.decision_audit import audit_plan

client = TestClient(app)


def test_audit_requires_active_plan():
    client.post('/api/reset')
    result = client.get('/api/decision/audit')
    assert result.status_code == 404


def test_audit_reports_changes_without_claiming_causality(monkeypatch):
    import app.main as main_mod
    monkeypatch.setattr(main_mod.settings, 'routing_provider', 'illustrative')  # exercise historical audit only
    client.post('/api/reset')
    assert client.post('/api/replan', json={'include_incidents':True}).status_code == 200
    data = client.get('/api/decision/audit').json()
    assert data['simulated'] is True
    assert data['comparable'] is True
    assert len(data['vehicles']) == 3
    assert all('stops_before' in row and 'stops_after' in row for row in data['vehicles'])
    assert 'no' in ' '.join(data['limitations']).lower()


def test_audit_excludes_cross_fidelity_numeric_delta():
    client.post('/api/reset')
    original = client.get('/api/mission').json()['original_plan']
    nextplan = DispatchPlan.model_validate(original)
    nextplan.routes[0].fidelity='road_network'
    data = audit_plan(DispatchPlan.model_validate(original),nextplan)
    assert data['comparable'] is False
    assert data['distance_delta_km'] is None
