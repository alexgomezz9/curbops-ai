"""Verified, stop-preserving road detours for long multi-stop routes.

Works at the street leg level: public OSRM allows at most ten waypoints per
request, not per vehicle. Replacements are accepted only when provider-returned
polylines miss the selected buffer; failures are retained as failures.
"""
from __future__ import annotations
from math import cos, radians, hypot
from typing import Any, Awaitable, Callable
from ..models import Coordinate, Incident
from ..scenario import DEPOT, DELIVERIES
from .road_risk import corridor_hit
from .geo import point_segment_km

RouteFetcher = Callable[[list[Coordinate]], Awaitable[tuple[list[Coordinate],float,float]]]
AlternativeFetcher = Callable[[list[Coordinate]], Awaitable[list[tuple[list[Coordinate],float,float]]]]


def _near_m(point: Coordinate, geometry: list[Coordinate]) -> float:
    if len(geometry) < 2:
        return float('inf')
    return 1000*min(point_segment_km(point,a,b) for a,b in zip(geometry,geometry[1:]))


def _partition(geometry:list[Coordinate],stops:list[Coordinate]) -> list[list[Coordinate]] | None:
    """Split an already routed polyline at its ordered, provider-snapped stops."""
    if len(geometry)<len(stops) or len(stops)<2:
        return None
    boundaries=[0]
    for ix, stop in enumerate(stops[1:-1],1):
        lo=boundaries[-1]+1
        hi=len(geometry)-(len(stops)-ix)
        if lo>hi:return None
        j=min(range(lo,hi+1),key=lambda k:hypot(
            (geometry[k][0]-stop[0])*111195*cos(radians(stop[1])),
            (geometry[k][1]-stop[1])*111195))
        if hypot((geometry[j][0]-stop[0])*111195*cos(radians(stop[1])),
                 (geometry[j][1]-stop[1])*111195)>220:return None
        boundaries.append(j)
    boundaries.append(len(geometry)-1)
    return [geometry[a:b+1] for a,b in zip(boundaries,boundaries[1:])]


def _candidates(geometry:list[Coordinate],incident:Incident)->list[list[Coordinate]]:
    """Plausible via-point corridors on both sides of the affected street.

    They are only requests to a road provider. They are NEVER drawn as roads.
    """
    i=min(range(len(geometry)-1),key=lambda j:point_segment_km(
        incident.location,geometry[j],geometry[j+1]))
    a,b=geometry[i:i+2]
    scale=111195*cos(radians(incident.location[1]))
    dx=(b[0]-a[0])*scale;dy=(b[1]-a[1])*111195
    n=hypot(dx,dy) or 1.0
    tx,ty=dx/n,dy/n;nx,ny=-ty,tx
    x,y=incident.location
    out=[]
    for off in (max(290,incident.radius_m+180),max(470,incident.radius_m+330),
                max(700,incident.radius_m+500)):
        for side in (-1,1):
            via=(x+side*nx*off/scale,y+side*ny*off/111195)
            out.append([via])
            span=max(260,incident.radius_m+180)
            first=(x+(side*nx*off-tx*span)/scale,y+(side*ny*off-ty*span)/111195)
            last=(x+(side*nx*off+tx*span)/scale,y+(side*ny*off+ty*span)/111195)
            out.append([first,last])
    return [pts for pts in out if all(-4.05<px<-3.3 and 40.2<py<40.7 for px,py in pts)]


async def find_leg_detours(route:Any, incidents:list[Incident],fetcher:RouteFetcher,
                           *,max_checks:int=20,alternative_fetcher:AlternativeFetcher|None=None)->tuple[Any,dict]:
    """Attempt street-leg avoidance without changing delivery order.

    Legs are replaced independently; if the requested zones cannot all be
    avoided, report the incomplete result, never a 'fully avoided' result.
    """
    detail={'vehicle_id':route.vehicle_id,'incident_ids':[e.id for e in incidents],
            'avoided_ids':[],'still_near_ids':[],'provider_checks':0,
            'verified':False,'reason':'No relevant avoid zone on road geometry',
            'extra_km':0.0,'extra_base_minutes':0.0,'strategy':'per_leg_provider_geometry'}
    relevant=[i for i in incidents if corridor_hit(route.coordinates,i)]
    if not relevant:return route,detail
    stops={d.id:d.location for d in DELIVERIES}
    points=[DEPOT]+[stops[x] for x in route.stop_ids]+[DEPOT]
    # A required stop within an exclusion zone cannot be bypassed: the point
    # must be visited. We may still avoid other independent incidents.
    blocked={e.id for e in relevant if any(_near_m(e.location,[p,p])<=e.radius_m for p in points)}
    pieces=_partition(route.coordinates,points)
    if pieces is None:
        pieces=[]
        for a,b in zip(points,points[1:]):
            try:
                geom,_,_=await fetcher([a,b]);detail['provider_checks']+=1
            except Exception:
                detail.update(reason='Cannot verify original street legs',still_near_ids=[e.id for e in relevant])
                return route,detail
            pieces.append(geom)
    changes={}
    remaining_checks=max_checks-detail['provider_checks']
    extra_km=extra_min=0.0
    for leg_index,(start,end,geom) in enumerate(zip(points,points[1:],pieces)):
        affected=[i for i in relevant if i.id not in blocked and corridor_hit(geom,i)]
        if not affected or remaining_checks<=0:continue
        # If a single leg intersects several zones, the complete set must be
        # avoided by the returned geometry, not only the first point.
        try:
            original_geom,old_km,old_min=await fetcher([start,end]);remaining_checks-=1
            detail['provider_checks']+=1
        except Exception:
            continue
        if not original_geom or old_km<=0:continue
        # A provider response wildly inconsistent with the already verified B
        # distance/time cannot be used to 'save' a bogus detour cost.
        if old_km>route.distance_km*1.4 or old_min>route.estimated_minutes*1.6:
            continue
        best=None
        # OSRM may already know another drivable path between these stops.
        # Evaluate its actual returned alternatives before making via requests.
        if alternative_fetcher is not None and remaining_checks>0:
            remaining_checks-=1;detail['provider_checks']+=1
            try:
                direct_alternatives=await alternative_fetcher([start,end])
            except Exception:
                direct_alternatives=[]
            for road,km,minutes in direct_alternatives:
                if len(road)<2 or km<=0 or minutes<=0:continue
                if any(corridor_hit(road,obstacle) for obstacle in affected):continue
                if _near_m(start,road)>120 or _near_m(end,road)>120:continue
                if extra_km+km-old_km>max(5.0,route.distance_km*0.55):continue
                if extra_min+minutes-old_min>max(12.0,route.estimated_minutes*0.55):continue
                if best is None or minutes<best[2]:best=(road,km,minutes)
        if best is not None:
            changes[leg_index]=best[0]
            extra_km+=best[1]-old_km;extra_min+=best[2]-old_min
            continue
        for event in affected:
            for via in _candidates(geom,event):
                if remaining_checks<=0:break
                remaining_checks-=1;detail['provider_checks']+=1
                try:road,km,minutes=await fetcher([start,*via,end])
                except Exception:continue
                if len(road)<2 or km<=0 or minutes<=0:continue
                if any(corridor_hit(road,obstacle) for obstacle in affected):continue
                # Both ends must connect to the actual street leg; prevent
                # discontinuities if a mock/provider returns unrelated geometry.
                if _near_m(start,road)>120 or _near_m(end,road)>120:continue
                candidate_extra_km=km-old_km;candidate_extra_min=minutes-old_min
                limit_km=max(5.0,route.distance_km*0.55)
                limit_min=max(12.0,route.estimated_minutes*0.55)
                if extra_km+candidate_extra_km>limit_km or extra_min+candidate_extra_min>limit_min:continue
                if best is None or minutes<best[2]:best=(road,km,minutes)
            if remaining_checks<=0:break
        if best:
            changes[leg_index]=best[0]
            extra_km+=best[1]-old_km;extra_min+=best[2]-old_min
    if not changes:
        detail.update(still_near_ids=[e.id for e in relevant],reason=(
            'A delivery/depot lies inside the avoidance zone' if len(blocked)==len(relevant)
            else 'No verified street-leg bypass found within the provider and detour budgets'))
        return route,detail
    combined=[]
    for index,geom in enumerate(pieces):
        segment=changes.get(index,geom)
        combined.extend(segment if not combined else segment[1:])
    # Complete verification catches re-entry into another leg's exclusion area.
    still=[e.id for e in relevant if corridor_hit(combined,e)]
    avoided=[e.id for e in relevant if e.id not in still]
    if not avoided:
        detail.update(still_near_ids=still,reason='Candidate geometry still intersects the requested zones')
        return route,detail
    detail.update(verified=True,avoided_ids=avoided,still_near_ids=still,
                  extra_km=round(extra_km,2),extra_base_minutes=round(extra_min,1),
                  reason=('All requested zones bypassed on verified street legs' if not still else
                          'Partial bypass: some risk zones remain on the route'),
                  changed_legs=sorted(changes))
    new=route.model_copy(update={
        'coordinates':combined,'distance_km':round(route.distance_km+extra_km,2),
        'estimated_minutes':round(route.estimated_minutes+extra_min,1),
        'incidents_near':sorted(set(route.incidents_near)-set(avoided))})
    return new,detail
