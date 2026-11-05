"""CurbOps API contracts. Values carrying simulated provenance must say so."""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field

Coordinate = tuple[float, float]  # GeoJSON: longitude, latitude

class SourceMode(str, Enum):
    demo = 'demo'
    live = 'live'

class DataProvenance(BaseModel):
    origin: Literal['synthetic', 'municipal_open_data', 'computed', 'routing_provider']
    label: str
    updated_at: str | None = None
    url: str | None = None

class Delivery(BaseModel):
    id: str
    customer: str
    location: Coordinate
    district: str
    scheduled_minutes: int = Field(ge=0, le=1440)
    service_minutes: int = Field(default=8, ge=1, le=120)
    priority: Literal['standard','urgent','critical'] = 'standard'
    load_units: int = Field(default=1, ge=1)

class Vehicle(BaseModel):
    id: str
    driver: str
    callsign: str
    color: str
    capacity: int = 10
    location: Coordinate
    stop_ids: list[str]
    status: Literal['en_route', 'idle', 'attention'] = 'en_route'

class Incident(BaseModel):
    id: str
    title: str
    location: Coordinate
    kind: Literal['roadworks','closure','event','accident','other']
    severity: Literal['low','medium','high']
    radius_m: int = 210
    detail: str
    starts_at: str | None = None
    ends_at: str | None = None
    provenance: DataProvenance

class LoadingZone(BaseModel):
    id: str
    label: str
    location: Coordinate
    district: str
    schedule: str = 'See posted signage'
    provenance: DataProvenance

class Camera(BaseModel):
    id: str
    label: str
    location: Coordinate
    image_url: str | None = None
    provenance: DataProvenance


class TrafficSensor(BaseModel):
    id: str
    location: Coordinate
    intensity_vph: float | None = None
    occupancy_pct: float | None = None
    speed_kmh: float | None = None
    service_level: int | None = None  # 0 fluent, 1 slow, 2 hold-ups, 3 congestion
    road_name: str | None = None

class CitySignals(BaseModel):
    status: Literal['unavailable','municipal_open_data'] = 'unavailable'
    fetched_at: str | None = None
    observed_at: str | None = None
    source_url: str
    total_valid: int = 0
    points: list[TrafficSensor] = Field(default_factory=list)
    distribution: dict[str,int] = Field(default_factory=dict)
    note: str = ''

class RouteLine(BaseModel):
    vehicle_id: str
    coordinates: list[Coordinate]
    color: str
    stop_ids: list[str]
    distance_km: float
    estimated_minutes: float
    incidents_near: list[str]
    fidelity: Literal['illustrative', 'road_network'] = 'illustrative'

class PlanMetrics(BaseModel):
    distance_km: float
    travel_minutes: float
    late_deliveries: int
    exposures: int
    total_stops: int
    score: float

class DispatchPlan(BaseModel):
    id: str
    status: Literal['baseline','proposed','approved']
    generated_at: str
    routes: list[RouteLine]
    metrics: PlanMetrics
    explanation: str
    limitations: list[str]

class SourceStatus(BaseModel):
    id: str
    name: str
    connected: bool
    updated_at: str | None
    count: int
    provenance: Literal['synthetic', 'municipal_open_data']
    detail: str

class MissionSnapshot(BaseModel):
    scenario_name: str
    source_mode: SourceMode
    simulation: bool = True
    generated_at: str
    depot: Coordinate
    vehicles: list[Vehicle]
    deliveries: list[Delivery]
    incidents: list[Incident]
    loading_zones: list[LoadingZone]
    cameras: list[Camera]
    original_plan: DispatchPlan
    proposed_plan: DispatchPlan | None
    approved_plan: DispatchPlan | None
    sources: list[SourceStatus]

class ConversationTurn(BaseModel):
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=1800)


class AgentMapContext(BaseModel):
    scenario: Literal['A', 'B', 'C'] | None = None
    selected_vehicle: str | None = Field(default=None, max_length=32)
    selected_incident: str | None = Field(default=None, max_length=90)


class AgentRequest(BaseModel):
    message: str = Field(min_length=4,max_length=1200)
    model_tier: Literal['efficient','advanced'] = 'efficient'
    # Only brief user/assistant text. No hidden model reasoning, secrets,
    # trace objects or unbounded transcript persistence.
    history: list[ConversationTurn] = Field(default_factory=list,max_length=12)
    context: AgentMapContext | None = None

class AgentTrace(BaseModel):
    step: int
    tool: str
    detail: str
    status: Literal['success','warning','error'] = 'success'
    duration_ms: int = 0

class MapAction(BaseModel):
    """Allowlisted UI instruction only; never dispatches vehicles or fetches URLs."""
    type: Literal['select_vehicle','select_scenario','select_incident','show_comparison','open_map','fit_routes','show_traffic','highlight_route_incidents','highlight_route_sensors','highlight_avoidance_results']
    value: str | None = None
    plan_id: str | None = None
    generation: int | None = None

class AgentResponse(BaseModel):
    mode: Literal['llm_tool_agent','deterministic_demo','agent_error']
    provider: str
    model_id: str | None = None
    model_requests_observed: int | None = None
    model_input_tokens: int | None = None
    model_output_tokens: int | None = None
    model_calls_with_usage: int | None = None
    summary: str
    traces: list[AgentTrace]
    recommendations: list[str]
    warnings: list[str]
    proposed_plan: DispatchPlan | None = None
    actions_require_approval: bool = True
    map_actions: list[MapAction] = Field(default_factory=list)

class ReplanRequest(BaseModel):
    include_incidents: bool = True
    avoid_incident_ids: list[str] | None = None

class ApprovalRequest(BaseModel):
    plan_id: str
    reviewer: str = Field(default='Portfolio demo operator', min_length=3, max_length=90)
