"""Public-facing route explanation: physical measurements and provenance, no hidden weights.

Distance/time are road-network model values (not live ETAs). Incident indicators
are geometry-on-street proximity, never a verified closed edge.
"""
from __future__ import annotations
from ..store import DemoStore


def scenario_payload(store:DemoStore)->dict:
    with store.lock:
        a=store.road_baseline or store.original
        b=store.no_risk_plan
        c=store.approved or store.proposed
        context=store.decision_context or {}
        return {'plan_id':c.id if c else None,'generation':store.generation,
                'routing_provider':context.get('routing_provider'),
                'plan_stale': bool(c and store.planned_incident_signature is not None and
                                   store.planned_incident_signature != store.incident_signature()),
                'as_of':context.get('as_of'),
                'A':a.model_dump(), 'B':b.model_dump() if b else None,
                'C':c.model_dump() if c else None,
                'risk_evidence':context.get('road_risk_evidence'),
                'street_detours':context.get('street_detours',{}),
                'precautionary_avoidance':context.get('precautionary_avoidance'),
                'temporal_evidence':context.get('temporal_evidence',[]),
                'note':('B uses road-time and road-distance costs, modeled deadlines and capacity. '
                        'C normally adds time-filtered municipal/synthetic incident-point proximity; on explicit request C may be a road-provider-verified hypothetical avoidance '
                        'on road polylines for the selected candidate routes. Unchecked hypothetical legs remain unknown. '
                        'Neither uses real-time congestion in its optimization or verified blocked road edges. '
                        'A synthetic roadworks rehearsal or explicit preventive request may additionally test bounded provider-verified road detours after stop allocation.')}


def vehicle_explanation(store:DemoStore,vehicle_id:str)->dict:
    from ..scenario import VEHICLES
    if vehicle_id not in {v.id for v in VEHICLES}:
        raise ValueError('Unknown vehicle')
    payload=scenario_payload(store)
    with store.lock:
        context=store.decision_context or {}
        breakdown=context.get('breakdown',{})
        incidents={i.id:i for i in store.incidents}
    def summarize(label:str):
        plan=payload[label]
        if not plan:return None
        route=next((r for r in plan['routes'] if r['vehicle_id']==vehicle_id),None)
        if not route:return None
        # A preventive whole-route geometry has no verified per-leg breakdown.
        # Do not reuse the OLD optimizer matrix legs after a provider detour.
        internal=({} if label=='C' and context.get('precautionary_avoidance')
                  else (breakdown.get(label) or {}).get(vehicle_id, {}))
        legs=[]
        for leg in internal.get('legs',[]):
            near=[]
            for hit in leg.get('incidents',[]):
                i=incidents.get(hit['id'])
                near.append({'id':hit['id'],'title':i.title if i else hit['id'],
                             'severity':hit['severity'],'origin':hit['origin'],
                             'method':hit['exposure_method'],'verified_road_closure':False})
            legs.append({'from_stop_id':leg['from_stop_id'],'to_stop_id':leg['to_stop_id'],
                         'road_km':leg['road_km'],'base_minutes':leg['base_minutes'],
                         'modeled_late_minutes':leg['modeled_late_minutes'],
                         'nearby_incidents':near,'risk_applied':leg['risk_applied']})
        detour=(context.get('street_detours') or {}).get(vehicle_id) if label=='C' else None
        if label=='C' and context.get('precautionary_avoidance'):
            match=next((row for row in context['precautionary_avoidance']['vehicles']
                        if row['vehicle_id']==vehicle_id),None)
            if match:
                detour={'geometry_changed':match['verified'],'extra_km':match['extra_km'],
                    'extra_base_minutes':match['extra_base_minutes'],
                    'reason':match['reason'],'incident_id':','.join(match['incident_ids'])}
        return {'scenario':label,'stop_ids':route['stop_ids'],
                'detour':detour,
                'road_km':route['distance_km'],'base_minutes':route['estimated_minutes'],
                'incidents_near':route['incidents_near'],
                'legs':legs,'has_leg_detail':bool(internal)}
    result={label:summarize(label) for label in 'ABC'}
    a,b,c=result['A'],result['B'],result['C']
    result['interpretation']={
        'A_to_B':'Effect of road-based heuristic optimization with no incident penalties (if B exists).',
        'B_to_C':('Operator-requested preventative geometry exclusion, verified on street lines; NOT an official closure.' if context.get('precautionary_avoidance') else 'Effect of adding eligible incident proximity risk to the SAME road costs and solver (if C exists).'),
        'A_to_C':'Combined simulated change. Do not attribute total savings to individual incidents.',
        'road_restrictions':('Selected areas were operator-requested hypothetical exclusions, not certified road closures.' if context.get('precautionary_avoidance') else 'No road closures were applied as hard constraints to OSRM/ORS.'),
        'traffic':'Municipal sensor readings are evidence for inspection; they do not modify route ETAs or optimization costs.',
        'model_risk_changed_assignment':context.get('incidents_changed_optimizer_decision'),
        'geometry_changed_due_to_synthetic_rehearsal':(context.get('street_detours') or {}).get(vehicle_id,{}).get('geometry_changed',False),
        'evidence_method':(context.get('road_risk_evidence') or {}).get('method')}
    return {'plan_id':payload['plan_id'],'generation':payload['generation'],
            'vehicle_id':vehicle_id,'scenarios':result,'as_of':payload['as_of']}


def incident_impact(store:DemoStore,incident_id:str)->dict:
    """Per-event ablation within the previously verified candidate pool.

    This explains the simulated choice among tested candidates, not a real
    traffic effect or a globally optimal new route.
    """
    with store.lock:
        context=store.decision_context or {}
        item=next((x for x in store.incidents if x.id==incident_id),None)
        if item is None:raise ValueError('Unknown incident')
        affected=[]
        for vehicle_id,detail in context.get('breakdown',{}).get('C',{}).items():
            for leg in detail.get('legs',[]):
                if any(hit['id']==incident_id for hit in leg.get('incidents',[])):
                    affected.append({'vehicle_id':vehicle_id,
                        'from_stop_id':leg['from_stop_id'],'to_stop_id':leg['to_stop_id']})
        status=next((x['temporal_status'] for x in context.get('temporal_evidence',[]) if x['id']==incident_id),'unknown')
        # Fixed-candidate counterfactual: compare identical B/seeded C routes
        # with and without this individual event. No provider calls and no
        # newly imagined alternative route is introduced.
        ablation=None
        matrix=context.get('matrix_internal')
        exposures=context.get('road_exposures_internal')
        candidates=context.get('risk_candidate_assignments_internal')
        if matrix is not None and exposures is not None and candidates is not None:
            from .matrix_optimizer import optimize_road_matrix
            from ..scenario import VEHICLES,DELIVERIES
            from .incident_policy import eligible_incidents
            from datetime import datetime,timezone
            at=datetime.fromisoformat(context['as_of'])
            eligible,_=eligible_incidents(list(store.incidents),at)
            reference=optimize_road_matrix(VEHICLES,DELIVERIES,eligible,matrix,
                  road_exposures=exposures,risk_candidate_assignments=candidates)
            without=[i for i in eligible if i.id!=incident_id]
            reduced={leg:tuple(i for i in hits if i.id!=incident_id)
                     for leg,hits in exposures.items()}
            counter=optimize_road_matrix(VEHICLES,DELIVERIES,without,matrix,
                  road_exposures=reduced,risk_candidate_assignments=candidates)
            ablation={'method':'same_candidate_pool_with_one_event_removed',
                      'selection_changed':reference.risk_adjusted!=counter.risk_adjusted,
                      'before_stops':reference.risk_adjusted,
                      'without_event_stops':counter.risk_adjusted,
                      'note':'Change of simulated candidate selection, not an observed traffic cause. Effects from different incidents cannot be added.'}
        return {'incident_id':incident_id,'title':item.title,'severity':item.severity,
                'origin':item.provenance.origin,'temporal_status':status,
                'affected_legs':affected,'applied_to_optimizer':bool(affected),
                'causal_route_change_measured':False,'candidate_ablation':ablation,
                'restriction_verified':False,
                'note':('Nearby route segments indicate spatial risk, not road closures. ' + ('Synthetic rehearsal may include a separately verified via-point detour after allocation; the leg-risk matrix represents pre-detour candidates. ' if any(x.get('geometry_changed') for x in context.get('street_detours',{}).values()) else '') + ('Fixed-candidate single-event ablation is available; not real-world causality.' if ablation else 'Ablation unavailable; no causal effect inferred.'))}
