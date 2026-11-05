"""Keep API tests fully offline even when matrix optimization is enabled by default.

Integration of OSRM/ORS wire formats has dedicated fake-client unit tests.
"""
import pytest
from app.scenario import DEPOT, DELIVERIES
from app.services.geo import distance_km

@pytest.fixture(autouse=True)
def use_offline_matrix_in_http_tests(monkeypatch):
    from app.agents import runner
    from app import main
    async def fake_matrix(points):
        return {
            'minutes': [[round(distance_km(a,b)*4.2,5) for b in points] for a in points],
            'kilometres': [[round(distance_km(a,b)*1.3,6) for b in points] for a in points],
        }
    monkeypatch.setattr(main, 'fetch_road_matrix', fake_matrix)
    monkeypatch.setattr(runner, 'fetch_road_matrix', fake_matrix)
