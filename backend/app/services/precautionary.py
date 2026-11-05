"""Operator-requested, hypothetical avoidance on **provider returned roads**.

No municipal point is treated as a certified road closure. A successful detour
means the resulting route geometry is outside an explicitly selected geometric
buffer, not that observed traffic would have been faster. When there is no
verifiable alternative we report failure rather than making up a detour.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, hypot
from collections.abc import Awaitable, Callable
from typing import Any
from datetime import datetime, timezone

from ..models import Coordinate, DispatchPlan, Incident
from ..scenario import DEPOT, DELIVERIES
from ..store import DemoStore
from .geo import point_segment_km
from .road_risk import corridor_hit

RouteFetcher = Callable[[list[Coordinate]], Awaitable[tuple[list[Coordinate], float, float]]]


def _distance_m(point: Coordinate, geometry: list[Coordinate]) -> float:
    if len(geometry) < 2:
        return float('inf')
    return 1000 * min(point_segment_km(point, a, b) for a, b in zip(geometry, geometry[1:]))


def _visits_required_stops(geometry: list[Coordinate], waypoints: list[Coordinate]) -> bool:
    # A route cannot count as a verified bypass if the provider response has
    # silently dropped a delivery, even when it avoids all obstacle buffers.
    # Allow modest road snapping around a delivery coordinate.
    return len(geometry) > 1 and all(_distance_m(stop, geometry) <= 125 for stop in waypoints)


def _side_points(geometry: list[Coordinate], incident: Incident) -> list[Coordinate]:
    """Generate bounded, deterministic shapes; road provider must verify each."""
    position = min(range(len(geometry)-1), key=lambda i:point_segment_km(
        incident.location, geometry[i], geometry[i+1]))
    a, b = geometry[position:position+2]
    per_lon = 111195 * cos(radians(incident.location[1]))
    dx, dy = (b[0]-a[0])*per_lon, (b[1]-a[1])*111195
    magnitude = hypot(dx, dy) or 1.0
    nx, ny = -dy/magnitude, dx/magnitude
    x, y = incident.location
    points = []
    # Both sides of the path, then cardinal directions. The provider may snap
    # these to nearby streets; only its RETURNED road geometry is accepted.
    for distance in (max(300, incident.radius_m+150),
                     max(520, incident.radius_m+330),
                     max(800, incident.radius_m+540)):
        for side in (-1, 1):
            points.append((x+side*nx*distance/per_lon, y+side*ny*distance/111195))
    for direction in ((1,0),(0,1),(-1,0),(0,-1)):
        distance=max(450,incident.radius_m+280)
        points.append((x+direction[0]*distance/per_lon,y+direction[1]*distance/111195))
    return [p for p in points if -4.04 < p[0] < -3.31 and 40.21 < p[1] < 40.69]


def _bypass_pairs(geometry: list[Coordinate], incident: Incident) -> list[tuple[Coordinate, Coordinate]]:
    """Try two ordered waypoints outside the same side of a risk buffer.

    Single via-points often let a shortest-road router re-enter the original
    affected street. Two ordered via-points can keep the actual provider path
    on the bypass street longer. Both returned geometries are still verified.
    """
    ix=min(range(len(geometry)-1), key=lambda n:point_segment_km(
        incident.location,geometry[n],geometry[n+1]))
    a,b=geometry[ix],geometry[ix+1]
    lon_factor=111195*cos(radians(incident.location[1]))
    vx,vy=(b[0]-a[0])*lon_factor,(b[1]-a[1])*111195
    norm=hypot(vx,vy) or 1.0
    tx,ty=vx/norm,vy/norm
    nx,ny=-ty,tx
    x,y=incident.location
    pairs=[]
    for sideways in (max(360, incident.radius_m+220), max(600,incident.radius_m+400)):
        for side in (-1,1):
            ahead=max(220,incident.radius_m+150)
            start=(x+(side*nx*sideways-tx*ahead)/lon_factor,
                   y+(side*ny*sideways-ty*ahead)/111195)
            end=(x+(side*nx*sideways+tx*ahead)/lon_factor,
                 y+(side*ny*sideways+ty*ahead)/111195)
            if all(-4.04 < p[0] < -3.31 and 40.21 < p[1] < 40.69 for p in (start,end)):
                pairs.append((start,end))
    return pairs


def _polygon(incidents: list[Incident]) -> dict[str, Any]:
    # ORS accepts GeoJSON MultiPolygon (one small square per point).
    polygons=[]
    for incident in incidents:
        lon,lat=incident.location
        radius=max(incident.radius_m+40,120)
        dx=radius/(111195*cos(radians(lat)))
        dy=radius/111195
        ring=[[lon-dx,lat-dy],[lon+dx,lat-dy],[lon+dx,lat+dy],[lon-dx,lat+dy],[lon-dx,lat-dy]]
        polygons.append([ring])
    return {'type':'MultiPolygon','coordinates':polygons}


async def _shape_one_route(route, events: list[Incident], fetcher: RouteFetcher,
                           *, ors_avoid: RouteFetcher | None = None,
                           max_candidates: int = 10,alternative_fetcher=None) -> tuple[Any,dict]:
    affected=[event for event in events if corridor_hit(route.coordinates,event)]
    detail={'vehicle_id':route.vehicle_id,'incident_ids':[e.id for e in affected],
            'avoided_ids':[],'still_near_ids':[],'provider_checks':0,
            'verified':False,'reason':'No selected risk corridor intersects this road route',
            'extra_km':0.0,'extra_base_minutes':0.0}
    if not affected:
        return route,detail
    if len(affected) > 1:
        # Treat each candidate zone independently first. Previously the entire
        # vehicle detour was rejected unless ONE path avoided every adjacent
        # municipal point: a viable one-zone detour could be lost this way.
        # The other points remain explicitly unresolved in the audit.
        winner = None
        attempts = []
        for event in affected:
            candidate, proof = await _shape_one_route(
                route, [event], fetcher, ors_avoid=ors_avoid,
                max_candidates=max_candidates, alternative_fetcher=alternative_fetcher)
            attempts.append({'incident_id':event.id, 'verified':proof['verified'],
                             'reason':proof['reason'], 'provider_checks':proof['provider_checks']})
            detail['provider_checks'] += proof['provider_checks']
            if not proof['verified'] or not _visits_required_stops(candidate.coordinates, [
                DEPOT, *[d.location for stop in route.stop_ids for d in DELIVERIES if d.id == stop], DEPOT
            ]):
                continue
            avoided = [e.id for e in affected if not corridor_hit(candidate.coordinates, e)]
            score = (len(avoided), -max(0.0, candidate.estimated_minutes-route.estimated_minutes))
            if winner is None or score > winner[0]:
                winner = (score, candidate, proof, avoided)
        detail['zone_attempts'] = attempts
        if winner is None:
            detail.update(reason='No individual requested risk zone could be bypassed within limits',
                          still_near_ids=[e.id for e in affected])
            return route, detail
        _, candidate, proof, avoided = winner
        detail.update(verified=True, avoided_ids=avoided,
                      still_near_ids=[e.id for e in affected if e.id not in avoided],
                      reason='Best provider-verified single-zone detour; other risk zones independently reported',
                      extra_km=proof['extra_km'], extra_base_minutes=proof['extra_base_minutes'])
        return candidate, detail
    deliveries={d.id:d.location for d in DELIVERIES}
    waypoints=[DEPOT]+[deliveries[stop] for stop in route.stop_ids]+[DEPOT]
    if any(_distance_m(event.location,[stop,stop]) <= event.radius_m for event in affected for stop in waypoints):
        # A stop INSIDE the excluded disk cannot be reached by any geometry
        # outside that disk. Do not claim the algorithm found an avoidance.
        detail['reason']='A required delivery/depot lies inside the avoidance zone'
        detail['still_near_ids']=[e.id for e in affected]
        return route,detail
    max_extra_minutes=max(10.0,route.estimated_minutes*0.45)
    max_extra_km=max(4.5,route.distance_km*0.45)
    # Prefer local leg replacement for long routes: a full multi-stop OSRM
    # request cannot accept more than ten waypoints including added vias.
    # Each leg is independently routed/verified and stop order is preserved.
    if len(waypoints) >= 5 and ors_avoid is None:
        from .leg_avoidance import find_leg_detours
        local_route, local_detail = await find_leg_detours(route,affected,fetcher,max_checks=22,alternative_fetcher=alternative_fetcher)
        detail['provider_checks'] += local_detail['provider_checks']
        if local_detail['verified'] and _visits_required_stops(local_route.coordinates, waypoints):
            detail.update({k:v for k,v in local_detail.items() if k!='provider_checks'})
            return local_route,detail
        detail['leg_strategy_failure']=local_detail['reason']
        # Do not bombard the public demo with another full-route search after
        # bounded leg attempts have already exhausted the useful candidates.
        detail.update(reason=local_detail['reason'],still_near_ids=local_detail['still_near_ids'])
        return route,detail
    best=None
    if ors_avoid:
        try:
            coords,km,minutes=await ors_avoid(waypoints, _polygon(affected))
            detail['provider_checks']+=1
            if (len(coords)>1 and km>0 and minutes>0 and
                all(not corridor_hit(coords,e) for e in affected) and
                _visits_required_stops(coords,waypoints) and
                km-route.distance_km<=max_extra_km and
                minutes-route.estimated_minutes<=max_extra_minutes):
                best=(coords,km,minutes,'ORS provider avoid_polygons')
        except Exception as exc:
            detail['ors_error_type']=type(exc).__name__
    if best is None:
        # Shape the route through a genuine street waypoint. Look for the road
        # leg responsible for the conflict rather than assuming a straight chord.
        focus=affected[0]
        ranks=sorted(range(len(waypoints)-1),key=lambda i:point_segment_km(
            focus.location,waypoints[i],waypoints[i+1]))
        # A full route can diverge substantially from chords. Probe several
        # candidate legs and retain those whose provider polyline comes closest.
        leg_data=[]
        for ix in ranks[:min(4,len(ranks))]:
            try:
                geom,_,_=await fetcher(waypoints[ix:ix+2])
                detail['provider_checks']+=1
                if len(geom)>1:
                    leg_data.append((_distance_m(focus.location,geom),ix,geom))
            except Exception:
                continue
        leg_data.sort(key=lambda row:row[0])
        positions=[(ix,geom) for _,ix,geom in leg_data[:2]] or [(ranks[0],route.coordinates)]
        attempts=0
        per_leg=max(2,max_candidates//max(1,len(positions)))
        for ix,leg_geom in positions:
            local_attempts=0
            for via in _side_points(leg_geom,focus):
                if attempts>=max_candidates or local_attempts>=per_leg:break
                attempts+=1
                local_attempts+=1
                path=[*waypoints[:ix+1],via,*waypoints[ix+1:]]
                if len(path)>10:continue
                try:
                    geometry,km,minutes=await fetcher(path)
                    detail['provider_checks']+=1
                except Exception:
                    continue
                if len(geometry)<2 or km<=0 or minutes<=0:continue
                if any(corridor_hit(geometry,event) for event in affected):continue
                if not _visits_required_stops(geometry,waypoints):continue
                if km-route.distance_km>max_extra_km or minutes-route.estimated_minutes>max_extra_minutes:continue
                if best is None or minutes<best[2]:
                    best=(geometry,km,minutes,'OSRM/ORS via-waypoint verified')
            if attempts>=max_candidates:break
        # A second bounded strategy for shorter stop lists: two ordered
        # exterior waypoints can bypass an entire road corridor rather than
        # reaching one off-road point and returning immediately to the hazard.
        if len(waypoints)+2<=10 and best is None:
            for ix,leg_geom in positions:
                for first,second in _bypass_pairs(leg_geom,focus):
                    try:
                        geometry,km,minutes=await fetcher([*waypoints[:ix+1],first,second,*waypoints[ix+1:]])
                        detail['provider_checks']+=1
                    except Exception:
                        continue
                    if len(geometry)<2 or km<=0 or minutes<=0:continue
                    if any(corridor_hit(geometry,event) for event in affected):continue
                    if not _visits_required_stops(geometry,waypoints):continue
                    if km-route.distance_km>max_extra_km or minutes-route.estimated_minutes>max_extra_minutes:continue
                    if best is None or minutes<best[2]:
                        best=(geometry,km,minutes,'OSRM/ORS dual via-waypoint verified')
                if best is not None:break
    if best is None:
        # Long multi-stop routes often cannot accept additional OSRM waypoints.
        # Try independent provider-verified street legs before reporting failure.
        from .leg_avoidance import find_leg_detours
        leg_route, leg_detail = await find_leg_detours(route, affected, fetcher, max_checks=24,alternative_fetcher=alternative_fetcher)
        detail['provider_checks'] += leg_detail['provider_checks']
        if leg_detail['verified'] and _visits_required_stops(leg_route.coordinates,waypoints):
            detail.update({k:v for k,v in leg_detail.items() if k != 'provider_checks'})
            return leg_route, detail
        detail['leg_strategy_failure'] = leg_detail['reason']
    if best is None:
        detail.update(reason='No verified street detour found within limits; route remains unchanged',
                      still_near_ids=[e.id for e in affected])
        return route,detail
    geometry,km,minutes,method=best
    detail.update(verified=True,avoided_ids=[e.id for e in affected],
                  reason=method,extra_km=round(km-route.distance_km,2),
                  extra_base_minutes=round(minutes-route.estimated_minutes,1))
    return route.model_copy(update={'coordinates':geometry,'distance_km':round(km,2),
        'estimated_minutes':round(minutes,1),
        'incidents_near':sorted(set(route.incidents_near)-set(detail['avoided_ids']))}),detail


async def prepare_precautionary_plan(store: DemoStore,fetcher:RouteFetcher,*,
    vehicle_id:str='ALL',incident_ids:list[str]|None=None,
    ors_avoid=None,alternative_fetcher=None,progress=None) -> dict:
    """Prepare C as a road-verified preventative alternative to B.

    Caller explicitly requests hypothetical avoidance of municipal notices or
    synthetic events. We never silently elevate a notice to a confirmed closure.
    Atomic commit is guarded by store generation and incident signature.
    """
    with store.lock:
        generation=store.generation
        token=store.incident_signature()
        mode=store.source_mode
        base=store.no_risk_plan.model_copy(deep=True) if store.no_risk_plan else None
        incidents=list(store.incidents)
    if base is None or any(r.fidelity!='road_network' for r in base.routes):
        raise ValueError('Generate B road routes before asking to avoid incidents.')
    if vehicle_id!='ALL' and vehicle_id not in {r.vehicle_id for r in base.routes}:
        raise ValueError('Unknown fleet vehicle')
    known={i.id:i for i in incidents}
    if incident_ids:
        missing=[key for key in incident_ids if key not in known]
        if missing:raise ValueError(f'Unknown incident IDs: {missing[:3]}')
        selected=[known[key] for key in dict.fromkeys(incident_ids)]
    else:
        # Operator asked to avoid potential disruptions. Select visible route
        # intersections, prioritizing explicit simulation and severity. Do NOT
        # call this a verified closure or an active municipal incident.
        selected=[]
        ranked=sorted(incidents,key=lambda item:(item.provenance.origin!='synthetic',
                    {'high':0,'medium':1,'low':2}[item.severity],item.id))
        # Fair coverage: evaluate risks across each selected van instead of
        # taking four coincident municipal notices from the first corridor.
        # Bound public routing requests; document the bounded scope explicitly.
        for route in base.routes:
            if vehicle_id!='ALL' and route.vehicle_id!=vehicle_id:continue
            local=[item for item in ranked if corridor_hit(route.coordinates,item)]
            for item in local[:2]:
                if item.id not in {x.id for x in selected}:selected.append(item)
    rows=[];details=[]
    for route in base.routes:
        if vehicle_id!='ALL' and route.vehicle_id!=vehicle_id:
            rows.append(route);continue
        relevant=[item for item in selected if corridor_hit(route.coordinates,item)]
        if progress:progress('avoidance.route_started',{'vehicle_id':route.vehicle_id,'incident_ids':[e.id for e in relevant]})
        candidate,detail=await _shape_one_route(route,relevant,fetcher,ors_avoid=ors_avoid,alternative_fetcher=alternative_fetcher)
        rows.append(candidate);details.append(detail)
        if progress:progress('avoidance.route_completed',detail)
    # Use actual route geometry to recalculate all proximity markers, not only
    # avoidance-selected ones. These flags are not causality or observed delay.
    for route in rows:
        route.incidents_near=sorted(i.id for i in incidents if corridor_hit(route.coordinates,i))
    metrics=base.metrics.model_copy(update={'distance_km':round(sum(r.distance_km for r in rows),2),
        'travel_minutes':round(sum(r.estimated_minutes for r in rows),1),
        'exposures':sum(len(r.incidents_near) for r in rows),
        'score':round(sum(r.distance_km for r in rows),2)})
    changed=sum(1 for entry in details if entry['verified'])
    all_unavoided=sorted({key for row in details for key in row.get('still_near_ids',[])})
    all_avoided=sorted({key for row in details for key in row.get('avoided_ids',[])})

    from uuid import uuid4
    plan=base.model_copy(update={'id':f'precaution-{uuid4().hex[:9]}','status':'proposed',
        'generated_at':datetime.now(timezone.utc).isoformat(),'routes':rows,'metrics':metrics,
        'explanation':f'Preventative what-if (operator requested): {changed} road-verified vehicle detours; no municipal closure verification.',
        'limitations':[*base.limitations,'Selected municipal notices are only treated as hypothetical avoid zones when requested; they are not certified road closures.','Proximity-based avoidance is not a measured time saving or live ETA.']})
    result={'plan_id':plan.id,'mode':'operator_precautionary_what_if',
        'requested_incident_ids':[i.id for i in selected],
        'vehicles':details,'verified_vehicle_detours':changed,
        'avoided_incident_ids':all_avoided,'remaining_incident_ids':all_unavoided,
        'selection_scope':'at most two nearby notices per affected vehicle unless incident IDs specified',
        'status':('partially_verified_detour' if all_unavoided else 'verified_detour') if changed else
                 ('no_matching_incidents' if not selected else 'no_verified_detour'),
        'comparison':{'B_km':base.metrics.distance_km,'C_km':metrics.distance_km,
                      'B_base_min':base.metrics.travel_minutes,'C_base_min':metrics.travel_minutes},
        'disclaimer':'Explicitly hypothetical geometric avoidance, not an officially confirmed closure or live traffic reroute.'}
    with store.lock:
        if store.generation!=generation or store.source_mode!=mode or store.incident_signature()!=token:
            raise RuntimeError('Mission changed during avoidance; no partial plan committed.')
        # A verified C has an auditable differential relative to the same B.
        store.proposed=plan
        store.approved=None
        store.planned_incident_signature=token
        store.generation+=1
        store.decision_context={**(store.decision_context or {}), 'precautionary_avoidance':result}
    return result
