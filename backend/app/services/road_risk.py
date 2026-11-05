"""Evaluate *road polyline* point-proximity for possible pairwise driving legs.

Potential relevance is screened using a conservative length bound: a route
with length L cannot enter the radius r around p unless d(a,p)+d(p,b)<=L+2r.
Screening never treats a chord as evidence of exposure; actual geometric
exposure is established only from a routing-provider polyline. No road closure
is inferred, and exposure does not quantify real delay.
"""
from __future__ import annotations
from typing import Awaitable, Callable, Sequence
from math import radians, cos, sin, asin, sqrt
from ..models import Incident, Coordinate
from .geo import point_segment_km
from .matrix_optimizer import RoadCostMatrix

LegFetcher = Callable[[list[Coordinate]], Awaitable[tuple[list[Coordinate],float,float]]]


def haversine_km(a: Coordinate, b: Coordinate) -> float:
    lon1,lat1,lon2,lat2=map(radians, (a[0],a[1],b[0],b[1]))
    h=sin((lat2-lat1)/2)**2+cos(lat1)*cos(lat2)*sin((lon2-lon1)/2)**2
    return 12742*asin(min(1,sqrt(h)))


def corridor_hit(polyline: Sequence[Coordinate], incident: Incident) -> bool:
    return any(point_segment_km(incident.location,a,b)<=incident.radius_m/1000
               for a,b in zip(polyline[:-1],polyline[1:]))


async def evaluate_road_leg_risk(matrix: RoadCostMatrix, points: dict[str,Coordinate],
                                 incidents: list[Incident], fetcher: LegFetcher, *,
                                 max_pairs: int = 72) -> tuple[dict[tuple[str,str],tuple[Incident,...]],dict]:
    """Only risk candidate pairs are fetched; no silent fallback to straight lines.

    A provider failure or exhausted budget aborts the optimized C proposal,
    instead of implying a verified road-geometry penalty when none was computed.
    """
    exposure:dict[tuple[str,str],tuple[Incident,...]]={}
    candidates:list[tuple[str,str,list[Incident]]]=[]
    ids=matrix.stop_ids
    offsets={name:k for k,name in enumerate(ids)}
    for a in ids:
        for b in ids:
            if a==b:
                exposure[(a,b)]=()
                continue
            road_km=matrix.kilometres[offsets[a]][offsets[b]]
            hits=[i for i in incidents if haversine_km(points[a],i.location)+haversine_km(i.location,points[b])
                  <=road_km+2*i.radius_m/1000+0.1]
            if hits:
                candidates.append((a,b,hits))
            else:
                exposure[(a,b)]=()
    if len(candidates)>max_pairs:
        raise ValueError(f'Road-risk verification needs {len(candidates)} pair geometries (budget {max_pairs}). Use a dedicated routing provider or reduce events; no unverified proxy is substituted.')
    # fetcher enforces provider-specific rate limits/caching. Include direction:
    # different one-way routes may have distinct incident exposure.
    for a,b,may_hit in candidates:
        geometry,km,_=await fetcher([points[a],points[b]])
        if len(geometry)<2 or km<0:
            raise ValueError(f'Invalid road geometry for {a} -> {b}')
        exposure[(a,b)]=tuple(i for i in may_hit if corridor_hit(geometry,i))
    return exposure,{'method':'road_polyline_point_proximity',
                     'candidate_legs_checked':len(candidates),
                     'candidate_legs_skipped_by_length_bound':len(ids)*(len(ids)-1)-len(candidates),
                     'total_directed_legs':len(ids)*(len(ids)-1),
                     'provider_geometry_complete':True,
                     'verified_road_closures':0}

async def evaluate_selected_road_legs(matrix: RoadCostMatrix,points:dict[str,Coordinate],
                                     incidents:list[Incident],fetcher:LegFetcher,
                                     assignments:list[dict[str,list[str]]],
                                     known:dict[tuple[str,str],tuple[Incident,...]]|None=None,
                                     *,max_total_pairs:int=80)->tuple[dict[tuple[str,str],tuple[Incident,...]],dict]:
    """Budgeted exact-road checks for the *considered* routes (not all VRP moves).

    Unchecked legs are unknown, not proved clear. The next optimizer iteration
    can propose a different route; those new legs are checked in another pass.
    This is a route-level risk-sensitive heuristic, NOT a globally certified
    road-constrained optimizer.
    """
    existing=dict(known or {})
    offset={name:k for k,name in enumerate(matrix.stop_ids)}
    pairs=set()
    for assignment in assignments:
        for order in assignment.values():
            prev='DEPOT'
            for stop in [*order,'DEPOT']:
                pairs.add((prev,stop))
                prev=stop
    required=[pair for pair in sorted(pairs) if pair not in existing]
    candidates=[]
    for a,b in required:
        if a==b:
            existing[(a,b)]=()
            continue
        length=matrix.kilometres[offset[a]][offset[b]]
        plausible=[i for i in incidents if
                   haversine_km(points[a],i.location)+haversine_km(i.location,points[b])
                   <=length+2*i.radius_m/1000+0.1]
        if plausible:candidates.append((a,b,plausible))
        else:existing[(a,b)]=()
    if len(existing)+len(candidates)>max_total_pairs and candidates:
        raise ValueError('Road geometry inspection budget exhausted; no route was committed.')
    for a,b,nearby in candidates:
        shape,km,_=await fetcher([points[a],points[b]])
        if len(shape)<2 or km<0:raise ValueError(f'Incomplete geometry for {a}->{b}')
        existing[(a,b)]=tuple(i for i in nearby if corridor_hit(shape,i))
    checked=len(existing)
    return existing,{'method':'selected_road_polyline_point_proximity',
                     'selected_road_legs_checked':checked,
                     'total_directed_legs':len(matrix.stop_ids)*(len(matrix.stop_ids)-1),
                     'candidate_space_complete':False,
                     'verified_road_closures':0}
