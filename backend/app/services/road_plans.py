"""Atomic, road-network-only route plan generation for both UI and AI tools.

No schematic geometry can be committed as an approved road plan. City incident
points are only proximity evidence; OSRM/ORS have not been given verified closures.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from ..models import DispatchPlan
from ..scenario import DEPOT, DELIVERIES, VEHICLES
from ..services.geo import point_segment_km
from ..services.planner import calculate_plan
from ..services.matrix_optimizer import RoadCostMatrix, optimize_road_matrix
from ..services.incident_policy import eligible_incidents
from ..services.road_risk import evaluate_selected_road_legs
from ..store import DemoStore

RouteFetcher = Callable[[list[tuple[float,float]]], Awaitable[tuple[list[tuple[float,float]], float, float]]]
Progress = Callable[[str, dict[str, Any]], None] | None
MatrixFetcher = Callable[[list[tuple[float,float]]], Awaitable[dict]]


async def build_road_network_plan(store: DemoStore, fetcher: RouteFetcher,
                                  progress: Progress = None, *, matrix_fetcher: MatrixFetcher | None = None, explainable: bool = False) -> DispatchPlan:
    """Build A/C and optionally B street routes before committing any plan.

    The optimization selects fictional orders using a heuristic; road routing
    calculates geometry/distance/base duration for the chosen visit sequences.
    A provider failure leaves no new proposal, instead of showing straight lines.
    """
    with store.lock:
        original = store.original.model_copy(deep=True)
        source_mode = store.source_mode
        generation = store.generation
        incidents = list(store.incidents)
        incident_token = tuple((i.id, i.location, i.radius_m) for i in incidents)
        existing_proposal = store.proposed
        previous_id = existing_proposal.id if existing_proposal else None
    candidate = (existing_proposal.model_copy(deep=True) if existing_proposal and
                 all(r.fidelity == 'illustrative' for r in existing_proposal.routes)
                 else calculate_plan(VEHICLES, DELIVERIES, incidents, True))
    lookup = {delivery.id: delivery for delivery in DELIVERIES}
    decision_context = None
    scenario_b = None
    planning_at = datetime.now(timezone.utc)
    eligible, temporal_evidence = eligible_incidents(incidents, planning_at)

    def report(kind: str, **data):
        if progress:
            progress(kind, data)

    # v1.3: optimize the fictional assignment using actual road-matrix times;
    # isolate the *model* incident effect by holding all else fixed and toggling
    # soft spatial-proximity penalties. A municipal point is NEVER a road block.
    if matrix_fetcher is not None:
        report('routing.matrix_started', points=len(DELIVERIES)+1)
        try:
            ordered_ids=('DEPOT', *(d.id for d in DELIVERIES))
            payload=await matrix_fetcher([DEPOT, *(d.location for d in DELIVERIES)])
            matrix=RoadCostMatrix(ordered_ids,
                tuple(tuple(float(v) for v in row) for row in payload['minutes']),
                tuple(tuple(float(v) for v in row) for row in payload['kilometres']))
            road_exposures=None
            risk_evidence={'method':'point_to_chord_proxy', 'provider_geometry_complete':False}
            risk_candidates=None
            if explainable:
                coordinates={'DEPOT':DEPOT,**{d.id:d.location for d in DELIVERIES}}
                report('routing.risk_started',active_incidents=len(eligible))
                # Candidate pool: B (no risk) and a soft-risk heuristic candidate.
                # Proxy geometry is used ONLY to generate an alternative, NEVER
                # as the final incident score. Both candidate routes are scored
                # against ACTUAL provider road-line proximity, with no other
                # unseen hypothetical legs implicitly labelled risk-free.
                b_seed=optimize_road_matrix(VEHICLES,DELIVERIES,[],matrix)
                # Diversify the bounded candidate pool. All candidates will be
                # checked on actual road polylines before ranking; higher weights
                # here only GENERATE candidates, never substitute road evidence.
                risk_candidates=[]
                for seed_weight in (1.0, 3.0, 7.0, 12.0):
                    proposed_seed=optimize_road_matrix(VEHICLES,DELIVERIES,eligible,matrix,risk_weight=seed_weight)
                    if proposed_seed.risk_adjusted not in [b_seed.no_incident_counterfactual,*risk_candidates]:
                        risk_candidates.append(proposed_seed.risk_adjusted)
                known,risk_evidence=await evaluate_selected_road_legs(
                    matrix,coordinates,eligible,fetcher,
                    [b_seed.no_incident_counterfactual,*risk_candidates])
                zero={(a,b):() for a in matrix.stop_ids for b in matrix.stop_ids}
                road_exposures={**zero,**known}
                risk_evidence.update({
                    'selection':'best_of_B_and_one_proxy_generated_candidate_re_scored_on_real_streets',
                    'known_street_legs':len(known),
                    'unverified_hypothetical_legs':len(zero)-len(known),
                    'candidate_space_complete':False,
                    'candidates_fully_checked':True,
                    'candidate_count':1+len(risk_candidates),
                    'incident_aware_choice':'bounded_real_street_risk_ranking_with_detour_guard',
                })
                report('routing.risk_completed',checked=len(known))
            solution=optimize_road_matrix(VEHICLES,DELIVERIES,eligible,matrix,
                risk_weight=3.5 if explainable else 1.0,
                road_exposures=road_exposures,
                risk_candidate_assignments=risk_candidates)
            if explainable:
                scenario_b=candidate.model_copy(deep=True)
                scenario_b.id=f'{candidate.id}-no-risk'
                scenario_b.explanation='B: road-matrix optimization without incident penalties; no live traffic or closures.'
                for route in scenario_b.routes:
                    route.stop_ids=solution.no_incident_counterfactual[route.vehicle_id]
            if explainable:
                selected=set()
                for order in solution.risk_adjusted.values():
                    prev='DEPOT'
                    for stop in [*order,'DEPOT']:
                        selected.add((prev,stop));prev=stop
                if not selected.issubset(set(known)):
                    raise ValueError('Incomplete street exposure for selected candidate; no route committed')
            for route in candidate.routes:
                route.stop_ids=solution.risk_adjusted[route.vehicle_id]
            decision_context={
                'method':('road_time_matrix_plus_bounded_street_geometry_candidate_ranking' if explainable else 'road_time_matrix_plus_approximate_incident_penalty'),
                'risk_adjusted_assignment':solution.risk_adjusted,
                'no_incident_counterfactual':solution.no_incident_counterfactual,
                'incidents_changed_optimizer_decision':solution.incident_affected_optimization,
                'risk_adjusted_objective':solution.risk_adjusted_objective,
                'no_incident_objective':solution.no_incident_objective,
                'approximate_incident_ids':solution.approximate_incident_ids,
                'estimated_affected_legs':solution.estimated_affected_legs,
                'evidence_scope':('Risk candidate selection using actual provider street polyline exposure, among B and one heuristic alternative; no blocked roads or measured delays' if explainable else 'Point-to-chord proxy, no blocked roads'),
                'breakdown':solution.breakdown,
                # Private, only used in deterministic per-incident candidate-ablation.
                'matrix_internal':matrix if explainable else None,
                'road_exposures_internal':road_exposures if explainable else None,
                'risk_candidate_assignments_internal':risk_candidates if explainable else None,
                'road_risk_evidence':risk_evidence,
                'temporal_evidence':temporal_evidence,
                'as_of':planning_at.isoformat(),
                'routing_provider':'OSRM/ORS base road network',
            }
            report('routing.matrix_completed', points=len(DELIVERIES)+1,
                   counterfactual_changed=solution.incident_affected_optimization)
        except Exception as exc:
            report('routing.failed', reason=f'Matrix optimization failed: {type(exc).__name__}')
            raise

    total_routes=9 if scenario_b else 6
    report('routing.started', total=total_routes, provider='road_network')
    completed = 0

    async def upgrade(plan: DispatchPlan, label: str) -> DispatchPlan:
        nonlocal completed
        routes = []
        for route in plan.routes:
            waypoints = [DEPOT] + [lookup[stop_id].location for stop_id in route.stop_ids] + [DEPOT]
            geom, km, minutes = await fetcher(waypoints)
            if len(geom) < 2 or km < 0 or minutes < 0:
                raise ValueError('Routing provider returned an invalid or incomplete road route')
            # Only proximity to municipal *points*, not a validated road closure.
            hits = sorted({item.id for item in incidents if any(
                point_segment_km(item.location, a, b) <= item.radius_m / 1000
                for a, b in zip(geom[:-1], geom[1:])
            )})
            routes.append(route.model_copy(update={
                'coordinates': geom, 'distance_km': round(km, 2),
                'estimated_minutes': round(minutes, 1), 'incidents_near': hits,
                'fidelity': 'road_network',
            }))
            completed += 1
            report('routing.route_completed', completed=completed, total=total_routes,
                   group=label, vehicle_id=route.vehicle_id,
                   km=round(km, 2), minutes=round(minutes, 1))
        metrics = plan.metrics.model_copy(update={
            'distance_km': round(sum(r.distance_km for r in routes), 2),
            'travel_minutes': round(sum(r.estimated_minutes for r in routes), 1),
            'exposures': sum(len(r.incidents_near) for r in routes),
            'score': round(sum(r.distance_km for r in routes), 2),
        })
        return plan.model_copy(update={'routes': routes, 'metrics': metrics,
            'limitations': [
                ('Fictional deliveries and vehicles; stop order chosen by a road-time matrix local-search heuristic with approximate risk penalties.' if matrix_fetcher else 'Fictional deliveries and vehicles; order chosen by a schematic-cost heuristic, NOT a road-time VRP.'),
                'Street geometry and base duration returned by a road network provider; NOT live traffic ETAs.',
                'Municipal incident points are proximity indicators; closures were NOT applied to road graph.',
                'No claim of real savings or validated delivery feasibility.',
            ]})

    try:
        baseline = await upgrade(original, 'baseline')
        proposal = await upgrade(candidate, 'proposed')
        b_plan = await upgrade(scenario_b, 'without_incident_risk') if scenario_b else None
    except Exception as exc:
        report('routing.failed', reason=f'{type(exc).__name__}: {str(exc)[:150]}')
        raise
    # An explicit, operator-created synthetic what-if may request bounded street
    # detours even when the no-risk and risk heuristics choose identical stops.
    # This never happens silently for official Madrid observations.
    synthetic_rehearsal=next((i for i in eligible if i.id=='SIM-ROADWORKS'),None)
    if synthetic_rehearsal:
        from .road_detours import attempt_rehearsal_detours
        report('routing.detour_started',incident_id=synthetic_rehearsal.id)
        proposal,detour_log=await attempt_rehearsal_detours(proposal,synthetic_rehearsal,fetcher)
        if decision_context is not None:
            decision_context['street_detours']=detour_log
            decision_context['road_risk_evidence']['rehearsal_detour_found']=any(row['geometry_changed'] for row in detour_log.values())
            decision_context['road_risk_evidence']['rehearsal_is_synthetic']=True
        report('routing.detour_completed',changed=sum(x['geometry_changed'] for x in detour_log.values()))

    with store.lock:
        if (store.source_mode != source_mode or store.generation != generation or
            tuple((i.id, i.location, i.radius_m) for i in store.incidents) != incident_token or
            (store.proposed.id if store.proposed else None) != previous_id):
            raise RuntimeError('Mission changed during road calculation; retry to avoid inconsistent plans')
        store.generation += 1
        store.road_baseline = baseline
        store.no_risk_plan = b_plan
        store.decision_context = decision_context
        store.proposed = proposal.model_copy(update={'explanation': (
            ('Road-time matrix local-search with a soft spatial-incident penalty; ' if matrix_fetcher else
             'Schematic local-search with a soft spatial-incident penalty; ') +
            'BOTH route shapes/distances/base durations from the street network. '
            'Municipal point locations are NOT validated closures.')})
        store.approved = None
        store.planned_incident_signature = store.incident_signature()
        result = store.proposed
    report('routing.completed', total=total_routes,
           original_km=baseline.metrics.distance_km,
           proposed_km=result.metrics.distance_km)
    return result

async def build_road_baseline(store: DemoStore, fetcher: RouteFetcher) -> DispatchPlan:
    """Load ONLY the original, unchanged fictional dispatch onto actual streets.

    This is a read-only operational reference. It must not generate a candidate
    dispatch or present any savings until a user explicitly runs the optimizer.
    """
    with store.lock:
        generation=store.generation
        source_mode=store.source_mode
        token=tuple((i.id,i.location,i.radius_m) for i in store.incidents)
        if store.road_baseline is not None:
            return store.road_baseline
        original=store.original.model_copy(deep=True)
        incidents=list(store.incidents)
    lookup={delivery.id:delivery for delivery in DELIVERIES}
    routes=[]
    for route in original.routes:
        points=[DEPOT]+[lookup[stop_id].location for stop_id in route.stop_ids]+[DEPOT]
        geom,km,minutes=await fetcher(points)
        if len(geom)<2 or km<0 or minutes<0:
            raise ValueError('Incomplete baseline road route; no schematic fallback')
        hits=sorted({incident.id for incident in incidents if any(
            point_segment_km(incident.location,a,b)<=incident.radius_m/1000
            for a,b in zip(geom[:-1],geom[1:]))})
        routes.append(route.model_copy(update={
            'coordinates':geom,'distance_km':round(km,2),'estimated_minutes':round(minutes,1),
            'incidents_near':hits,'fidelity':'road_network'}))
    m=original.metrics.model_copy(update={
        'distance_km':round(sum(r.distance_km for r in routes),2),
        'travel_minutes':round(sum(r.estimated_minutes for r in routes),1),
        'exposures':sum(len(r.incidents_near) for r in routes),
        'score':round(sum(r.distance_km for r in routes),2),
    })
    baseline=original.model_copy(update={'routes':routes,'metrics':m,
        'explanation':'Original fictional fleet order, routed on real streets; no alternative prepared.',
        'limitations':['No alternative plan has been generated.',
            'The original deliveries are fictional; road durations are base estimates, NOT real-time ETAs.',
            'Municipal incident geometry is only proximity evidence; no confirmed blocked road edges.']})
    with store.lock:
        if (store.generation!=generation or store.source_mode!=source_mode or
            tuple((i.id,i.location,i.radius_m) for i in store.incidents)!=token):
            raise RuntimeError('Mission changed during baseline routing')
        store.road_baseline=baseline
    return baseline
