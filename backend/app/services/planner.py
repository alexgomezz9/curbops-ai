"""Small explainable dispatcher.

This is an *illustrative* routing baseline with local metric distances. It is
NOT road-legal routing, not live traffic ETA, and not a replacement for a TMS.
With ORS enabled, road-network geometry is requested separately.
"""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from typing import Sequence
import math
from ..models import Delivery,Vehicle,Incident,RouteLine,DispatchPlan,PlanMetrics,Coordinate
from ..scenario import DEPOT
from .geo import distance_km,point_segment_km,offset_point_km

ROAD_MULTIPLIER=1.22
CRUISING_KMH=23.0

def segment_exposure(a: Coordinate,b:Coordinate, incidents:Sequence[Incident]) -> list[Incident]:
    return [i for i in incidents if point_segment_km(i.location,a,b) <= i.radius_m/1000]

def route_cost(order:list[str], lookup:dict[str,Delivery], incidents:Sequence[Incident], include_risk:bool=True) -> float:
    origin=DEPOT;elapsed=0.0;total_km=0.;exposure=0.;late=0.
    for stop_id in order:
        stop=lookup[stop_id]
        leg=distance_km(origin,stop.location)*ROAD_MULTIPLIER
        total_km+=leg
        elapsed+=60*leg/CRUISING_KMH
        if include_risk:
            exposure+=sum({'low':0.8,'medium':2,'high':4}[i.severity] for i in segment_exposure(origin,stop.location,incidents))
        late+=max(0.,elapsed-stop.scheduled_minutes)
        elapsed+=stop.service_minutes
        origin=stop.location
    total_km+=distance_km(origin,DEPOT)*ROAD_MULTIPLIER
    return total_km+exposure*0.75+late*0.06

def optimize_assignments(vehicles:list[Vehicle], deliveries:list[Delivery], incidents:list[Incident]) -> dict[str,list[str]]:
    lookup={d.id:d for d in deliveries}
    routes={v.id:v.stop_ids.copy() for v in vehicles}
    caps={v.id:v.capacity for v in vehicles}
    # Deterministic, bounded best-improvement local search: intra-route relocations, swaps, inter-vehicle moves.
    def score(candidate:dict[str,list[str]]) -> float:
        return sum(route_cost(order,lookup,incidents) for order in candidate.values())
    current=score(routes)
    for _ in range(18):
        best=routes;best_cost=current
        for va in vehicles:
            for index_a,item in enumerate(routes[va.id]):
                for vb in vehicles:
                    if va.id!=vb.id and sum(lookup[x].load_units for x in routes[vb.id])+lookup[item].load_units>caps[vb.id]:
                        continue
                    for target_index in range(len(routes[vb.id])+1):
                        if va.id==vb.id and target_index in (index_a,index_a+1):
                            continue
                        candidate={key:value.copy() for key,value in routes.items()}
                        candidate[va.id].pop(index_a)
                        insert_at=target_index-(1 if va.id==vb.id and target_index>index_a else 0)
                        candidate[vb.id].insert(insert_at,item)
                        value=score(candidate)
                        if value<best_cost-1e-6:
                            best,best_cost=candidate,value
        if best_cost>=current-1e-6:break
        routes,current=best,best_cost
    return routes

def _detour(a:Coordinate,b:Coordinate,incident:Incident) -> Coordinate:
    """Illustrative waypoint outside incident circle. This is NOT validated on roads."""
    ax,ay=a;bx,by=b
    mid=((ax+bx)/2,(ay+by)/2)
    # Take perpendicular from incident centroid towards outer side of route.
    from .geo import to_xy
    x1,y1=to_xy(a);x2,y2=to_xy(b);cx,cy=to_xy(incident.location)
    dx,dy=x2-x1,y2-y1;length=max(.0001,math.hypot(dx,dy))
    nx,ny=-dy/length,dx/length
    side=1 if (cx-x1)*nx+(cy-y1)*ny>=0 else -1
    # Detour on the opposite side, tangential to the barrier.
    off=incident.radius_m/1000+0.19
    return offset_point_km(incident.location,-side*nx*off,-side*ny*off)

def _route_points(order:list[str],lookup:dict[str,Delivery],incidents:list[Incident],avoid:bool) -> list[Coordinate]:
    points=[DEPOT]
    for stop_id in order:
        target=lookup[stop_id].location;previous=points[-1]
        if avoid:
            hazards=sorted(segment_exposure(previous,target,incidents),key=lambda i: {'high':0,'medium':1,'low':2}[i.severity])
            if hazards:
                waypoint=_detour(previous,target,hazards[0])
                points.append(waypoint)
        points.append(target)
    points.append(DEPOT)
    return points

def calculate_plan(vehicles:list[Vehicle], deliveries:list[Delivery], incidents:list[Incident],optimized:bool) -> DispatchPlan:
    lookup={x.id:x for x in deliveries}
    assignment=optimize_assignments(vehicles,deliveries,incidents) if optimized else {v.id:list(v.stop_ids) for v in vehicles}
    lines=[];all_late=0;total_minutes=0.;total_km=0.;exposures=0
    for vehicle in vehicles:
        order=assignment[vehicle.id]
        geometry=_route_points(order,lookup,incidents,avoid=optimized)
        km=sum(distance_km(a,b) for a,b in zip(geometry[:-1],geometry[1:]))*ROAD_MULTIPLIER
        total_km+=km
        # Estimate timings on stop-to-stop distance, not on illustrative detours.
        elapsed=0.0;prev=DEPOT
        for stop_id in order:
            stop=lookup[stop_id]
            elapsed+=60*distance_km(prev,stop.location)*ROAD_MULTIPLIER/CRUISING_KMH
            if elapsed>stop.scheduled_minutes:all_late+=1
            elapsed+=stop.service_minutes;prev=stop.location
        total_minutes+=km/CRUISING_KMH*60
        hits=sorted(set(i.id for a,b in zip(geometry[:-1],geometry[1:]) for i in segment_exposure(a,b,incidents)))
        exposures+=len(hits)
        lines.append(RouteLine(vehicle_id=vehicle.id,coordinates=geometry,color=vehicle.color,stop_ids=order,
            distance_km=round(km,2),estimated_minutes=round(km/CRUISING_KMH*60,1),incidents_near=hits))
    metrics=PlanMetrics(distance_km=round(total_km,2),travel_minutes=round(total_minutes,1),
        late_deliveries=all_late,exposures=exposures,total_stops=len(deliveries),
        score=round(sum(route_cost(assignment[v.id],lookup,incidents) for v in vehicles),2))
    now=datetime.now(timezone.utc).isoformat()
    return DispatchPlan(id=('proposal-'+str(uuid4())[:8] if optimized else 'baseline'),status=('proposed' if optimized else 'baseline'),
        generated_at=now,routes=lines,metrics=metrics,
        explanation=('Heuristic assignment with illustrative hazard avoidance' if optimized else 'Original fictional dispatcher assignments'),
        limitations=['Schematic geometries: not turn-by-turn drivable routes unless road-network provider enabled.',
          'Travel times are modelled, not verified real-time ETAs.','Orders, vehicles and baseline are fictional.'])
