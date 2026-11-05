"""Explainable road-matrix dispatch optimization for a *fictional* fleet.

Travel-time and road distance are from a routing matrix. Incident risk is an
EXPLICIT, approximate point-to-chord proximity penalty; it does not represent
an actual blocked road edge, a live ETA, or causal delay. Counterfactuals use
identical deliveries/capacities/road matrix and only toggle this risk term.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence
from ..models import Delivery, Vehicle, Incident
from .geo import point_segment_km

@dataclass(frozen=True)
class RoadCostMatrix:
    stop_ids: tuple[str, ...]  # starts with DEPOT
    minutes: tuple[tuple[float, ...], ...]
    kilometres: tuple[tuple[float, ...], ...]

    def validate(self):
        n=len(self.stop_ids)
        if not 2<=n<=26 or len(set(self.stop_ids))!=n or self.stop_ids[0]!='DEPOT':
            raise ValueError('Unexpected road matrix point inventory')
        if any(len(row)!=n for row in (*self.minutes, *self.kilometres)):
            raise ValueError('Incomplete road cost matrix')
        if any(x is None or not 0<=x<1e7 for row in (*self.minutes,*self.kilometres) for x in row):
            raise ValueError('Unreachable or invalid travel cost; no schematic fallback')

@dataclass
class OptimizationResult:
    risk_adjusted: dict[str,list[str]]
    no_incident_counterfactual: dict[str,list[str]]
    incident_affected_optimization: bool
    risk_adjusted_objective: dict[str,float]
    no_incident_objective: dict[str,float]
    approximate_incident_ids: list[str]
    estimated_affected_legs: int
    breakdown: dict


def optimize_road_matrix(vehicles: Sequence[Vehicle], deliveries: Sequence[Delivery],
                          incidents: Sequence[Incident], matrix: RoadCostMatrix,
                          risk_weight: float = 1.0,
                          road_exposures: dict[tuple[str,str],tuple[Incident,...]] | None = None,
                          risk_candidate_assignments: list[dict[str,list[str]]] | None = None) -> OptimizationResult:
    matrix.validate()
    lookup={d.id:d for d in deliveries}
    expected={'DEPOT',*lookup}
    if set(matrix.stop_ids)!=expected:raise ValueError('Road matrix and shipment inventory do not match')
    offsets={name:i for i,name in enumerate(matrix.stop_ids)}
    capacity={v.id:v.capacity for v in vehicles}
    baseline={v.id:list(v.stop_ids) for v in vehicles}
    if {x for ids in baseline.values() for x in ids}!=set(lookup):
        raise ValueError('Every fictional delivery must appear exactly once')
    if any(sum(lookup[x].load_units for x in baseline[v.id])>capacity[v.id] for v in vehicles):
        raise ValueError('Baseline exceeds a vehicle capacity')

    # In v1.4 the production road pipeline injects route geometry verified
    # exposures for EVERY potentially relevant directed street leg. The legacy
    # point-to-chord proxy remains only for explicit offline unit tests and
    # callers without a geometry provider (never labelled road-verified).
    if road_exposures is not None:
        required={(a,b) for a in matrix.stop_ids for b in matrix.stop_ids}
        if set(road_exposures)!=required:
            raise ValueError('Road exposure matrix must cover all directed legs')
        exposures=road_exposures
    else:
        points={name:d.location for name,d in lookup.items()}
        from ..scenario import DEPOT
        points['DEPOT']=DEPOT
        exposures={}
        for a in matrix.stop_ids:
            for b in matrix.stop_ids:
                exposures[(a,b)] = (() if a==b else tuple(i for i in incidents if
                    point_segment_km(i.location,points[a],points[b])<=i.radius_m/1000))
    severity={'low':1.8,'medium':4.0,'high':7.0}
    def cost_of_route(order:list[str], include_risk:bool) -> tuple[float,float,float,float,int]:
        elapsed=0.0;km=0.0;risk=0.0;late=0.0;legs=0;previous='DEPOT'
        for stop_id in [*order,'DEPOT']:
            a,b=offsets[previous],offsets[stop_id]
            leg_min=matrix.minutes[a][b]
            elapsed+=leg_min;km+=matrix.kilometres[a][b]
            if include_risk:
                hazards=exposures[(previous,stop_id)]
                risk+=sum(severity[i.severity] for i in hazards)
                legs+=bool(hazards)
            if stop_id!='DEPOT':
                delivery=lookup[stop_id]
                lateness=max(0.0,elapsed-delivery.scheduled_minutes)
                late+=lateness * (1.5 if delivery.priority=='standard' else 2.5)
                elapsed+=delivery.service_minutes
            previous=stop_id
        # Travel time dominates, distance is a secondary term; lateness and
        # expected incident penalty are only *scenario* weights.
        score=(elapsed-sum(lookup[x].service_minutes for x in order)) + km*0.32 + late*0.9 + (risk_weight*risk if include_risk else 0.0)
        return score,elapsed,km,risk,legs

    def score(assignment:dict[str,list[str]],include_risk:bool):
        return sum(cost_of_route(order,include_risk)[0] for order in assignment.values())

    def optimize(include_risk:bool)->dict[str,list[str]]:
        current={k:v.copy() for k,v in baseline.items()}
        best_score=score(current,include_risk)
        for _ in range(24):
            best=current;value=best_score
            for va in vehicles:
                for ia,delivery in enumerate(current[va.id]):
                    for vb in vehicles:
                        if va.id!=vb.id and sum(lookup[x].load_units for x in current[vb.id])+lookup[delivery].load_units>capacity[vb.id]:
                            continue
                        for target in range(len(current[vb.id])+1):
                            if va.id==vb.id and target in (ia,ia+1):continue
                            candidate={k:list(v) for k,v in current.items()}
                            candidate[va.id].pop(ia)
                            insert=target-(1 if va.id==vb.id and target>ia else 0)
                            candidate[vb.id].insert(insert,delivery)
                            candidate_score=score(candidate,include_risk)
                            if candidate_score<value-1e-7:
                                best,value=candidate,candidate_score
            if value>=best_score-1e-7:break
            current,best_score=best,value
        return current

    no_risk=optimize(False)
    if risk_candidate_assignments is not None and (not incidents or not any(exposures.values())):
        with_risk={k:list(v) for k,v in no_risk.items()}
    elif risk_candidate_assignments is not None:
        # Only compare FULLY evaluated scenario candidates. This avoids assuming
        # that unobserved hypothetical street legs carry no risk. Candidate
        # generation is heuristic and does NOT certify a global optimum.
        candidate_pool=[no_risk,*risk_candidate_assignments]
        for assignment in candidate_pool:
            ids=[sid for order in assignment.values() for sid in order]
            if set(ids)!=set(lookup) or len(ids)!=len(lookup) or set(assignment)!=set(capacity):
                raise ValueError('Candidate delivery inventory mismatch')
            if any(sum(lookup[sid].load_units for sid in assignment[v.id])>v.capacity for v in vehicles):
                raise ValueError('Risk candidate violates vehicle capacity')
        # A high incident penalty must not force an unreasonable city-wide detour.
        # Cap extra base travel (not synthetic risk points): +20% or 6 minutes,
        # whichever is larger. When no safe alternative satisfies it, B remains.
        b_base_minutes=sum(cost_of_route(order,False)[1]-sum(lookup[x].service_minutes for x in order)
                           for order in no_risk.values())
        def travel_minutes(assignment):
            return sum(cost_of_route(order,False)[1]-sum(lookup[x].service_minutes for x in order)
                       for order in assignment.values())
        max_detour=max(6.0,b_base_minutes*.20)
        reasonable=[assignment for assignment in candidate_pool
                    if travel_minutes(assignment)<=b_base_minutes+max_detour+1e-7]
        with_risk={k:list(v) for k,v in min(reasonable or [no_risk],key=lambda item:score(item,True)).items()}
    else:
        with_risk=optimize(True) if incidents and risk_weight else {k:list(v) for k,v in no_risk.items()}
    def details(assignment):
        travel=sum(cost_of_route(order,False)[1]-sum(lookup[x].service_minutes for x in order) for order in assignment.values())
        km=sum(cost_of_route(order,False)[2] for order in assignment.values())
        risk=sum(cost_of_route(order,True)[3] for order in assignment.values())
        return {'base_travel_minutes':round(travel,1),'road_km':round(km,2),'approx_risk_points':round(risk,1),
                'weighted_objective':round(score(assignment,True),2)}
    def breakdown_for(assignment:dict[str,list[str]], with_risk:bool) -> dict:
        result={}
        for vehicle_id, order in assignment.items():
            elapsed=0.0
            road_min=road_km=raw_late=risk_points=0.0
            legs=[]; previous='DEPOT'
            for sid in [*order,'DEPOT']:
                a,b=offsets[previous],offsets[sid]
                minutes=matrix.minutes[a][b]
                distance=matrix.kilometres[a][b]
                road_min+=minutes;road_km+=distance;elapsed+=minutes
                current=exposures[(previous,sid)]
                incident_items=[{'id':i.id,'severity':i.severity,
                                 'origin':i.provenance.origin,
                                 'exposure_method':'road_polyline' if road_exposures is not None else 'point_to_chord_proxy',
                                 'verified_road_closure':False}
                                for i in current]
                if with_risk:risk_points+=sum(severity[i.severity] for i in current)*risk_weight
                late=0.0
                if sid!='DEPOT':
                    d=lookup[sid]
                    late=max(0.0,elapsed-d.scheduled_minutes)
                    raw_late+=late*(1.5 if d.priority=='standard' else 2.5)
                    elapsed+=d.service_minutes
                legs.append({'from_stop_id':previous,'to_stop_id':sid,
                             'road_km':round(distance,3),'base_minutes':round(minutes,2),
                             'modeled_late_minutes':round(late,2),
                             'incidents':incident_items,
                             'risk_proxy': bool(current),
                             'risk_applied':bool(with_risk and current)})
                previous=sid
            result[vehicle_id]={
                'road_km':round(road_km,3),'base_travel_minutes':round(road_min,2),
                'modeled_weighted_lateness':round(raw_late,2),
                'risk_score_internal':round(risk_points,3),
                'total_score_internal':round(road_min+road_km*.32+raw_late*.9+risk_points,3),
                'stop_ids':list(order),'legs':legs}
        return result
    relevant={}
    for order in [*no_risk.values(),*with_risk.values()]:
        prev='DEPOT'
        for stop in [*order,'DEPOT']:
            for incident in exposures[(prev,stop)]:relevant[incident.id]=relevant.get(incident.id,0)+1
            prev=stop
    return OptimizationResult(
        risk_adjusted=with_risk,
        no_incident_counterfactual=no_risk,
        incident_affected_optimization=with_risk!=no_risk,
        risk_adjusted_objective=details(with_risk),
        no_incident_objective=details(no_risk),
        approximate_incident_ids=sorted(relevant,key=lambda key:(-relevant[key],key))[:10],
        estimated_affected_legs=sum(cost_of_route(order,True)[4] for order in with_risk.values()),
        breakdown={'B':breakdown_for(no_risk,False), 'C':breakdown_for(with_risk,True)}
    )
