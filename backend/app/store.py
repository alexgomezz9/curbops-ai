"""Demo-only state store. Replace with Postgres before deploying for multiple users."""
from __future__ import annotations
from dataclasses import dataclass,field
from datetime import datetime,timezone
from threading import RLock
from .models import *
from .scenario import DEPOT,DELIVERIES,VEHICLES,INCIDENTS,LOADING_ZONES,CAMERAS
from .services.planner import calculate_plan

@dataclass
class DemoStore:
    lock: RLock=field(default_factory=RLock)
    original: DispatchPlan=field(default_factory=lambda:calculate_plan(VEHICLES,DELIVERIES,INCIDENTS,False))
    generation: int=0  # Invalidate in-flight route operations after a new agent run
    road_baseline: DispatchPlan | None=None
    decision_context: dict | None=None
    no_risk_plan: DispatchPlan | None=None
    planned_incident_signature: tuple | None=None  # signature of source incidents used in C
    proposed: DispatchPlan | None=None
    approved: DispatchPlan | None=None
    override_incidents: list[Incident] | None=None
    rehearsal_incident: Incident | None=None
    override_zones: list[LoadingZone] | None=None
    override_cameras: list[Camera] | None=None
    traffic_points: list[TrafficSensor]=field(default_factory=list)
    previous_traffic_points: list[TrafficSensor]=field(default_factory=list)
    previous_traffic_fetched_at: str | None=None
    traffic_total_valid: int=0
    traffic_fetched_at: str | None=None
    traffic_observed_at: str | None=None
    traffic_source_error: str | None=None
    source_mode: SourceMode=SourceMode.demo
    live_last_fetch: str | None=None
    live_errors: list[str]=field(default_factory=list)

    def incident_signature(self) -> tuple:
        """Only route-relevant evidence. Traffic snapshots do not change OSRM travel times."""
        return tuple(sorted((i.id, tuple(i.location), i.radius_m, i.severity,
                             i.starts_at, i.ends_at, i.provenance.origin)
                            for i in self.incidents))

    @property
    def incidents(self)->list[Incident]:
        primary=self.override_incidents if self.source_mode==SourceMode.live and self.override_incidents is not None else INCIDENTS
        return [*primary,*([self.rehearsal_incident] if self.rehearsal_incident else [])]
    @property
    def zones(self)->list[LoadingZone]:return self.override_zones if self.source_mode==SourceMode.live and self.override_zones is not None else LOADING_ZONES
    @property
    def cameras(self)->list[Camera]:return self.override_cameras if self.source_mode==SourceMode.live and self.override_cameras is not None else CAMERAS

    def snapshot(self)->MissionSnapshot:
        with self.lock:
            is_live=self.source_mode==SourceMode.live
            sources=[
                SourceStatus(id='incidents',name='Traffic incidents',connected=is_live and self.override_incidents is not None,
                             updated_at=self.live_last_fetch if is_live else None,count=len(self.incidents),
                             provenance=('municipal_open_data' if is_live and self.override_incidents is not None else 'synthetic'),
                             detail=('Municipal XML data' if is_live and self.override_incidents is not None else 'Reproducible demo fixture')),
                SourceStatus(id='loading',name='Loading reserves',connected=is_live and self.override_zones is not None,
                             updated_at=self.live_last_fetch if is_live else None,count=len(self.zones),
                             provenance=('municipal_open_data' if is_live and self.override_zones is not None else 'synthetic'),
                             detail=('Municipal GeoJSON inventory; NOT availability' if is_live and self.override_zones is not None else 'Illustrative locations, NOT availability')),
                SourceStatus(id='cameras',name='Traffic cameras',connected=is_live and self.override_cameras is not None,
                             updated_at=self.live_last_fetch if is_live else None,count=len(self.cameras),
                             provenance=('municipal_open_data' if is_live and self.override_cameras is not None else 'synthetic'),
                             detail=('Municipal KML; snapshots may not resolve' if is_live and self.override_cameras is not None else 'Mock locations, no real imagery')),
            ]
            sources.append(SourceStatus(id='traffic',name='Traffic measurement points',connected=bool(self.traffic_points),
                 updated_at=self.traffic_fetched_at,count=self.traffic_total_valid,
                 provenance='municipal_open_data' if self.traffic_points else 'synthetic',
                 detail='Read-only municipal sensors; never simulated and never used as live ETAs' if self.traffic_points else 'Not loaded; no synthetic sensor readings'))
            return MissionSnapshot(scenario_name='Madrid · Last-mile response',source_mode=self.source_mode,simulation=True,
                generated_at=datetime.now(timezone.utc).isoformat(),depot=DEPOT,vehicles=VEHICLES,deliveries=DELIVERIES,
                incidents=self.incidents,loading_zones=self.zones,cameras=self.cameras,original_plan=self.road_baseline or self.original,
                proposed_plan=self.proposed,approved_plan=self.approved,sources=sources)

    def replan(self,include_incidents:bool=True, selected_ids:list[str]|None=None)->DispatchPlan:
        incidents=[i for i in self.incidents if selected_ids is None or i.id in selected_ids] if include_incidents else []
        plan=calculate_plan(VEHICLES,DELIVERIES,incidents,True)
        with self.lock:self.generation+=1;self.proposed=plan;self.approved=None;self.road_baseline=None;self.decision_context=None;self.no_risk_plan=None;self.planned_incident_signature=None
        return plan

    def begin_investigation(self) -> None:
        """Invalidate the preceding proposal and approval before the first model call.

        A previous approved demonstration plan must not be shown as the approval
        status for a new independent agent run. No real dispatch ever occurs.
        """
        with self.lock:
            self.generation += 1
            self.proposed = None
            self.approved = None
            self.road_baseline = None
            self.decision_context = None
            self.no_risk_plan = None
            self.planned_incident_signature = None

    def approve(self,plan_id:str)->DispatchPlan:
        with self.lock:
            if not self.proposed or self.proposed.id!=plan_id:raise ValueError('Plan not found or superseded')
            if (self.planned_incident_signature is not None and
                self.planned_incident_signature != self.incident_signature()):
                raise ValueError('Incident data changed since planning; replan before approving')
            self.approved=self.proposed.model_copy(update={'status':'approved'})
            return self.approved

    def reset(self):
        with self.lock:
            self.generation+=1;self.proposed=None;self.approved=None;self.road_baseline=None;self.decision_context=None;self.no_risk_plan=None;self.rehearsal_incident=None;self.planned_incident_signature=None

store=DemoStore()
