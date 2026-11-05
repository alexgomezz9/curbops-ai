"""Optional, explicitly synthetic route-geometry what-if for portfolio demonstrations.

Use REAL provider street lines both for the baseline and any alternative route.
A via waypoint is only an experiment: we accept a detour if its returned street
geometry demonstrably avoids the synthetic risk point and the extra journey is
small. This does not block an OSRM edge and cannot represent municipal closures.
"""
from __future__ import annotations
from math import cos, radians, hypot
from typing import Awaitable, Callable
from ..models import DispatchPlan, Incident, Coordinate
from ..scenario import DEPOT, DELIVERIES
from .geo import point_segment_km
from .road_risk import corridor_hit

RouteFetcher = Callable[[list[Coordinate]], Awaitable[tuple[list[Coordinate], float, float]]]


def _bypass_positions(polyline: list[Coordinate], incident: Incident) -> list[Coordinate]:
    """Two perpendicular samples across a road segment near an incident point."""
    if len(polyline)<2:
        return []
    k=min(range(len(polyline)-1), key=lambda ix:point_segment_km(
        incident.location,polyline[ix],polyline[ix+1]))
    a,b=polyline[k],polyline[k+1]
    meters_per_lon=111195*cos(radians(incident.location[1]))
    east=(b[0]-a[0])*meters_per_lon
    north=(b[1]-a[1])*111195
    length=hypot(east,north)
    if length<1:
        # Degenerate geometry; use a deterministic north/south bypass instead.
        east,north,length=1,0,1
    normal=(-north/length,east/length)
    radius=max(320,min(650,incident.radius_m*2.4))
    lon,lat=incident.location
    return [(lon+sign*radius*normal[0]/meters_per_lon,
             lat+sign*radius*normal[1]/111195) for sign in (-1,1)]


async def attempt_rehearsal_detours(plan: DispatchPlan, incident: Incident,
                                    fetcher: RouteFetcher)->tuple[DispatchPlan,dict]:
    """Backward-compatible synthetic rehearsal, now using provider-verified
    multi-side waypoint search rather than the first approximate leg only.
    No arbitrary line is drawn and impossible detours remain explicit.
    """
    from .precautionary import _shape_one_route
    rows=[]
    provenance={}
    for route in plan.routes:
        updated,details=await _shape_one_route(route,[incident],fetcher,max_candidates=10)
        rows.append(updated)
        provenance[route.vehicle_id]={
            'vehicle_id':route.vehicle_id,'incident_id':incident.id,
            'geometry_changed':details['verified'],
            'checked_alternatives':details['provider_checks'],
            'reason':details['reason'],
            'extra_km':details['extra_km'],
            'extra_base_minutes':details['extra_base_minutes'],
            'avoided_ids':details['avoided_ids']}
    metrics=plan.metrics.model_copy(update={
        'distance_km':round(sum(r.distance_km for r in rows),2),
        'travel_minutes':round(sum(r.estimated_minutes for r in rows),1),
        'exposures':sum(len(r.incidents_near) for r in rows)})
    return plan.model_copy(update={'routes':rows,'metrics':metrics}),provenance
