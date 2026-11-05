"""CurbOps HTTP API: portfolio/demo safe defaults, explicit data provenance."""
from __future__ import annotations
from datetime import datetime,timezone
import time
import json
import httpx
import queue
from threading import Thread
from fastapi.responses import StreamingResponse,Response
from fastapi import FastAPI,HTTPException,Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .settings import get_settings
from .models import (AgentRequest,AgentResponse,ReplanRequest,ApprovalRequest,DispatchPlan,
    MissionSnapshot,SourceMode,CitySignals)
from .store import store
from .agents.runner import run_agent
from .integrations.madrid import fetch_source,SOURCES
from .services.camera_images import camera_snapshot
from .services.routing import fetch_road_route,fetch_road_matrix
from .services.road_plans import build_road_network_plan,build_road_baseline
from .services.geo import point_segment_km
from .services.evidence import incident_evidence
from .services.traffic_delta import summarize_changes
from .services.decision_audit import audit_plan
from .services.decision_explain import scenario_payload,vehicle_explanation,incident_impact
from .services.route_traffic import inspect_route_traffic
from .services.route_corridor import vehicle_corridor, incident_fleet_corridor
from .scenario import DEPOT, DELIVERIES, VEHICLES
from .services.planner import calculate_plan

settings=get_settings()
app=FastAPI(title='CurbOps AI API',version='0.1.0',description='A fictional dispatch scenario and opt-in Madrid Open Data ingestion.')
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in settings.cors_origins.split(',')],
    allow_methods=['GET','POST'],allow_headers=['Content-Type'],allow_credentials=False)
_last_refresh=0.0

@app.get('/health')
def health():return {'status':'ok','service':'CurbOps','mode':store.source_mode}

@app.get('/api/mission',response_model=MissionSnapshot)
def get_mission():return store.snapshot()

@app.post('/api/replan',response_model=DispatchPlan, deprecated=True)
def replan(body:ReplanRequest):
    if settings.routing_provider in ('ors','osrm_demo'):
        raise HTTPException(status_code=409,detail='Legacy geometric routing disabled. Use /api/replan/road-network for real streets.')
    return store.replan(include_incidents=body.include_incidents,selected_ids=body.avoid_incident_ids)

@app.post('/api/approve',response_model=DispatchPlan)
def approve(body:ApprovalRequest):
    try:return store.approve(body.plan_id)
    except ValueError as ex:raise HTTPException(status_code=409,detail=str(ex)) from ex

@app.post('/api/reset',response_model=MissionSnapshot)
def reset():
    store.reset();return store.snapshot()

@app.post('/api/agent/run',response_model=AgentResponse)
def agent_run(body:AgentRequest):
    # The tools are bounded and approval is never executed by an LLM.
    return run_agent(store,body)



@app.post('/api/agent/stream')
def agent_stream(body: AgentRequest):
    """ND-friendly SSE over POST. Events are emitted at real tool boundaries.

    The final event contains exactly the same contract as /api/agent/run. We do
    not stream the LLM's private reasoning or pretend to have GPS telemetry.
    """
    def event_source():
        events: queue.Queue[dict | None] = queue.Queue()

        def worker():
            try:
                result = run_agent(store, body, on_event=events.put)
                events.put({'type': 'result', 'result': result.model_dump(mode='json')})
            except Exception as ex:
                events.put({'type': 'error', 'message': f'Unexpected agent error: {type(ex).__name__}'})
            finally:
                events.put(None)

        Thread(target=worker, daemon=True).start()
        while True:
            item = events.get()
            if item is None:
                break
            yield f'data: {json.dumps(item, ensure_ascii=False)}\n\n'

    return StreamingResponse(event_source(), media_type='text/event-stream',
                             headers={'Cache-Control': 'no-cache, no-transform',
                                      'X-Accel-Buffering': 'no'})

@app.get('/api/decision/audit')
def decision_audit():
    """Explain objective, stop reassignment, order and proximity flags, not causal real-world routing."""
    with store.lock:
        plan = store.approved or store.proposed
        if plan is None:
            raise HTTPException(status_code=404, detail='No proposed or approved plan to audit')
        return audit_plan(store.road_baseline or store.original, plan,
                          decision_context=store.decision_context, incidents=list(store.incidents))

@app.get('/api/decision/scenarios')
def get_decision_scenarios():
    return scenario_payload(store)

@app.get('/api/decision/vehicles/{vehicle_id}')
def get_vehicle_decision(vehicle_id:str):
    try:return vehicle_explanation(store,vehicle_id)
    except ValueError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc

@app.get('/api/decision/vehicles/{vehicle_id}/corridor')
def get_vehicle_corridor(vehicle_id:str,scenario:str='C'):
    try:return vehicle_corridor(store,vehicle_id,scenario)
    except ValueError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc

@app.get('/api/decision/incidents/{incident_id:path}/fleet')
def get_incident_fleet(incident_id:str,scenario:str='C'):
    try:return incident_fleet_corridor(store,incident_id,scenario)
    except ValueError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc

@app.get('/api/decision/incidents/{incident_id:path}')
def get_incident_route_impact(incident_id:str):
    try:return incident_impact(store,incident_id)
    except ValueError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc

@app.get('/api/decision/vehicles/{vehicle_id}/traffic')
def get_vehicle_traffic(vehicle_id:str,scenario:str='C',radius_m:int=Query(default=250,ge=50,le=1000)):
    try:return inspect_route_traffic(store,vehicle_id,scenario,radius_m)
    except ValueError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc

@app.get('/api/signals',response_model=CitySignals)
def signals():
    """Observed municipal traffic point snapshot; never synthesized."""
    with store.lock:
        pts=list(store.traffic_points)
        distribution={name:sum(1 for point in pts if point.service_level==code)
                      for code,name in enumerate(('free','slow','delayed','congested'))}
        distribution['unknown']=sum(1 for point in pts if point.service_level is None)
        return CitySignals(status='municipal_open_data' if pts else 'unavailable',
            fetched_at=store.traffic_fetched_at,observed_at=store.traffic_observed_at,
            total_valid=store.traffic_total_valid,points=pts,distribution=distribution,
            source_url=SOURCES['traffic']['page'],
            note='Valid geolocated sensor records; map shows sampled points, not drivable road speeds.' if pts
                else (store.traffic_source_error or 'Fetch municipal sources to obtain genuine sensor measurements.'))

@app.get('/api/signals/changes')
def signals_changes():
    """Two consecutive observed municipal snapshots only (no synthetic trend)."""
    with store.lock:
        return summarize_changes(store.previous_traffic_points,store.traffic_points,
                                 store.previous_traffic_fetched_at,store.traffic_fetched_at)

@app.get('/api/intelligence/incidents/{incident_id:path}')
def get_incident_evidence(incident_id: str, radius_m: int = Query(default=800,ge=100,le=2500),
                          limit: int = Query(default=6,ge=1,le=20)):
    """Investigate *geometric proximity* to a documented incident, with provenance.

    The values do not establish causality, congestion at a specific junction,
    actual road closure, vehicle exposure or travel delay.
    """
    data=incident_evidence(store, incident_id, radius_m, limit)
    if data is None:raise HTTPException(status_code=404,detail='Incident not found in selected data mode')
    return data

@app.get('/api/sources')
def sources():return {'sources':SOURCES,'note':'Municipal metadata is freely published; refresh endpoints fetch at most once per configured interval.'}

class ModeUpdate(BaseModel):
    mode:SourceMode

@app.post('/api/mode',response_model=MissionSnapshot)
def update_mode(body:ModeUpdate):
    with store.lock:
        if body.mode==SourceMode.live and all(x is None for x in (store.override_incidents,store.override_zones,store.override_cameras)) and not store.traffic_points:
            raise HTTPException(status_code=409,detail='No live datasets loaded. Use POST /api/sources/refresh first.')
        # A fresh feed refresh must not invalidate an approved demonstration plan.
        # Switching between demo/live domains DOES reset it, because evidence changes.
        if store.source_mode != body.mode:
            store.generation+=1;store.proposed=None;store.approved=None;store.road_baseline=None;store.no_risk_plan=None;store.decision_context=None;store.planned_incident_signature=None
        store.source_mode=body.mode
    return store.snapshot()

@app.post('/api/sources/refresh')
async def refresh_sources():
    global _last_refresh
    now=time.monotonic()
    if now-_last_refresh<settings.source_refresh_min_seconds:
        raise HTTPException(status_code=429,detail=f'Cooldown: municipal sources can only be refreshed every {settings.source_refresh_min_seconds}s')
    _last_refresh=now
    status={}
    # Fixed allowlist. No user-provided URLs or source paths.
    for kind in ('incidents','loading','cameras','traffic'):
        try:
            rows=await fetch_source(kind)
            with store.lock:
                if kind=='incidents':store.override_incidents=rows
                elif kind=='loading':store.override_zones=rows
                elif kind=='cameras':store.override_cameras=rows
                else:
                    points,total,observed=rows
                    if store.traffic_points:
                        store.previous_traffic_points=list(store.traffic_points)
                        store.previous_traffic_fetched_at=store.traffic_fetched_at
                    store.traffic_points=points
                    store.traffic_total_valid=total
                    store.traffic_observed_at=observed
                    store.traffic_fetched_at=datetime.now(timezone.utc).isoformat()
                    store.traffic_source_error=None
            status[kind]={'ok':True,'count':len(rows[0]) if kind=='traffic' else len(rows)}
        except Exception as exc:
            status[kind]={'ok':False,'error':f'{type(exc).__name__}: {str(exc)[:250]}'}
            if kind=='traffic':
                with store.lock:store.traffic_source_error=status[kind]['error']
    with store.lock:
        store.live_last_fetch=datetime.now(timezone.utc).isoformat()
        store.live_errors=[f'{k}: {v["error"]}' for k,v in status.items() if not v['ok']]
    return {'results':status,'source_mode':store.source_mode,
            'note':'If a source failed, demo records remain clearly marked synthetic. Live mode must be selected explicitly.'}


@app.get('/api/cameras/{camera_id}/snapshot')
async def get_camera_snapshot(camera_id: str):
    """Fetch the latest still image from the official KML URL; never video/GPS.

    Camera must have been loaded from official data. No arbitrary proxy URL.
    """
    if not camera_id.startswith('C-M') or len(camera_id)>20:
        raise HTTPException(status_code=404,detail='Unknown camera')
    with store.lock:
        camera=next((c for c in (store.override_cameras or []) if c.id==camera_id),None)
    if camera is None:
        raise HTTPException(status_code=404,detail='Camera not loaded; refresh municipal sources first')
    if not camera.image_url:
        raise HTTPException(status_code=404,detail='Official KML has no supported still-image URL for this camera')
    try:
        data,mime,_cached=await camera_snapshot(camera.image_url)
        return Response(content=data,media_type=mime,headers={
            'Cache-Control':'public, max-age=60',
            'X-Camera-Source':'Ayuntamiento de Madrid - still image, not live video',
            'X-Content-Type-Options':'nosniff',
        })
    except (ValueError,httpx.HTTPError) as exc:
        raise HTTPException(status_code=502,detail=f'Municipal snapshot unavailable: {type(exc).__name__}') from exc

@app.get('/api/routing/availability')
def routing_availability():
    return {'enabled':settings.routing_provider=='osrm_demo' or (settings.routing_provider=='ors' and bool(settings.ors_api_key)),
        'provider':('OSRM public demo' if settings.routing_provider=='osrm_demo' else 'HeiGIT OpenRouteService'),
        'mode':settings.routing_provider,
        'note':('OSRM demonstration: free, non-commercial, max 1 request/second, no SLA. ' if settings.routing_provider=='osrm_demo'
                else 'ORS requires an API key. ') + 'Neither provider applies Madrid incidents or live traffic to route costs.'}

class RoadRouteRequest(BaseModel):
    points:list[tuple[float,float]]

@app.post('/api/routing/road-route')
async def road_route(body:RoadRouteRequest):
    if len(body.points)>10:raise HTTPException(status_code=422,detail='Maximum 10 points per route')
    if len(body.points)<2:raise HTTPException(status_code=422,detail='At least two points required')
    if not all(-4.05<lon<-3.3 and 40.2<lat<40.7 for lon,lat in body.points):
        raise HTTPException(status_code=422,detail='Only Madrid-area coordinates supported')
    try:
        coordinates,km,minutes=await fetch_road_route(body.points)
        return {'coordinates':coordinates,'distance_km':round(km,2),'duration_minutes':round(minutes,1),
             'fidelity':'road_network','note':'ORS base map estimates; municipal traffic incidents are NOT automatically applied.'}
    except (ValueError,RuntimeError) as ex:raise HTTPException(status_code=409,detail=str(ex)) from ex
    except Exception as ex:raise HTTPException(status_code=502,detail=f'Routing provider error: {type(ex).__name__}') from ex

@app.post('/api/replan/road-network', response_model=DispatchPlan)
async def replan_road_network():
    """Commit BOTH road-network plans atomically; no schematic fallback."""
    if not (settings.routing_provider == 'osrm_demo' or
            (settings.routing_provider == 'ors' and bool(settings.ors_api_key))):
        raise HTTPException(status_code=409, detail='Road routing disabled. Configure ROUTING_PROVIDER=osrm_demo (or ors with ORS_API_KEY) to calculate real streets')
    try:
        return await build_road_network_plan(store, fetch_road_route, matrix_fetcher=fetch_road_matrix if settings.road_matrix_optimization else None,
                                             explainable=bool(settings.road_matrix_optimization))
    except (httpx.HTTPError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=502, detail=f'Road network unavailable; no plan was changed: {type(exc).__name__}: {str(exc)[:160]}') from exc



class RehearsalRequest(BaseModel):
    vehicle_id: str = 'V-01'
    clear: bool = False
    incident_id: str | None = None


@app.post('/api/decision/rehearsal')
def change_rehearsal(body: RehearsalRequest):
    """Explicit synthetic roadworks at an existing B road polyline position.

    This changes a hypothetical scenario, NOT the city data, and never claims
    that the selected street is actually closed. The caller must replan.
    """
    from .services.rehearsal import set_rehearsal
    try:
        active = set_rehearsal(store, body.vehicle_id, clear=body.clear,
                               incident_id=body.incident_id)
    except ValueError as ex:
        raise HTTPException(status_code=422 if str(ex)=='Unknown vehicle' else 409,detail=str(ex)) from ex
    return {'active': bool(active), 'incident': active.model_dump() if active else None,
            'note': 'Synthetic rehearsal only; rerun road optimization to compare B/C.'}



class PrecautionaryAvoidanceRequest(BaseModel):
    vehicle_id: str = 'ALL'
    incident_ids: list[str] | None = None

@app.post('/api/decision/precautionary-avoidance')
async def precautionary_avoidance(body: PrecautionaryAvoidanceRequest):
    """Operator-requested hypothetical avoidance; never a certified closure."""
    from .services.precautionary import prepare_precautionary_plan
    from .settings import get_settings
    configuration=get_settings()
    async def ors_avoid(points, geojson):
        return await fetch_road_route(points, avoid_polygons=geojson)
    try:
        return await prepare_precautionary_plan(
            store, fetch_road_route, vehicle_id=body.vehicle_id,
            incident_ids=body.incident_ids,
            ors_avoid=ors_avoid if configuration.routing_provider=='ors' else None)
    except ValueError as exc:
        raise HTTPException(status_code=409,detail=str(exc)) from exc
    except (RuntimeError,httpx.HTTPError) as exc:
        raise HTTPException(status_code=502,detail=f'Avoidance failed; no plan was changed: {type(exc).__name__}: {str(exc)[:140]}') from exc

@app.post('/api/routing/baseline',response_model=DispatchPlan)
async def route_original_fleet_only():
    """Show CURRENT fictional routes on real streets without creating a proposal."""
    if settings.routing_provider not in ('ors','osrm_demo') or (settings.routing_provider=='ors' and not settings.ors_api_key):
        raise HTTPException(status_code=409,detail='Configure OSRM demo or ORS before routing current fleet')
    try:
        return await build_road_baseline(store,fetch_road_route)
    except Exception as exc:
        raise HTTPException(status_code=502,detail=f'Baseline routing failed without creating a plan: {type(exc).__name__}: {str(exc)[:150]}') from exc
