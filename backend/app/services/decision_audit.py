"""Auditable BEFORE/AFTER arithmetic, not a causal explanation or road routing.

The optimizer is a deterministic local-search heuristic operating on fictional
orders and schematic distance estimates. This module states what the algorithm
changed, not why any real-world road would be better.
"""
from __future__ import annotations
from ..models import DispatchPlan,Incident


def audit_plan(original: DispatchPlan, proposed: DispatchPlan, *, decision_context: dict | None = None,
               incidents: list[Incident] | None = None) -> dict:
    before = {r.vehicle_id: r for r in original.routes}
    after = {r.vehicle_id: r for r in proposed.routes}
    if set(before) != set(after):
        raise ValueError('Cannot compare plans with different vehicle sets')
    comparable = len({route.fidelity for route in [*original.routes, *proposed.routes]}) == 1
    rows = []
    reassigned = set()
    for vehicle_id, next_route in after.items():
        old = before[vehicle_id]
        old_ids, new_ids = list(old.stop_ids), list(next_route.stop_ids)
        incoming = [sid for sid in new_ids if sid not in old_ids]
        outgoing = [sid for sid in old_ids if sid not in new_ids]
        reassigned.update(incoming)
        reassigned.update(outgoing)
        changed_order = [x for x in old_ids if x in new_ids] != [x for x in new_ids if x in old_ids]
        old_hazards, new_hazards = set(old.incidents_near), set(next_route.incidents_near)
        reasons = []
        if incoming or outgoing:
            reasons.append(f'Delivery reassignment: +{len(incoming)} / −{len(outgoing)}.')
        if changed_order:
            reasons.append('Order of shared stops changed.')
        if not incoming and not outgoing and not changed_order:
            reasons.append('Vehicle assignment and stop order are unchanged; street geometry may still differ.')
        if old_hazards != new_hazards:
            reasons.append('Nearby incident exposure changed; no road closure was verified.')
        rows.append({
            'vehicle_id': vehicle_id,
            'fidelity_before': old.fidelity,
            'fidelity_after': next_route.fidelity,
            'stop_count_before': len(old_ids),
            'stop_count_after': len(new_ids),
            'stops_before': old_ids,
            'stops_after': new_ids,
            'moved_in': incoming,
            'moved_out': outgoing,
            'order_changed': changed_order,
            'distance_before_km': old.distance_km,
            'distance_after_km': next_route.distance_km,
            'distance_delta_km': (round(next_route.distance_km-old.distance_km, 2) if comparable else None),
            'proximity_flags_before': sorted(old_hazards),
            'proximity_flags_after': sorted(new_hazards),
            'explanation': reasons,
        })
    context=decision_context or {}
    incident_index={i.id:i for i in (incidents or [])}
    counterfactual=context.get('no_incident_counterfactual') or {}
    changed=bool(context.get('incidents_changed_optimizer_decision',False))
    for row in rows:
        alternate=counterfactual.get(row['vehicle_id'])
        row['counterfactual_stops_no_risk']=alternate
        row['incident_risk_changed_vehicle']=bool(alternate is not None and alternate!=row['stops_after']) if context else None
        if row['incident_risk_changed_vehicle']:
            row['explanation'].append('The road-only counterfactual has a different stop sequence; geographic risk influenced the modeled assignment.')
        elif context:
            row['explanation'].append('Without incident risk, stop order is identical; the change cannot be attributed to incident weights.')
    incident_references=[{'id':key,'title':incident_index[key].title,
                          'source':incident_index[key].provenance.origin,
                          'severity':incident_index[key].severity}
                         for key in context.get('approximate_incident_ids',[]) if key in incident_index]
    return {
        'risk_attribution':({
            'method':context['method'],
            'changed_by_soft_incident_penalty':changed,
            'road_costs_compared':True,
            'no_incident_counterfactual':counterfactual,
            'risk_adjusted_objective':context.get('risk_adjusted_objective'),
            'no_incident_objective':context.get('no_incident_objective'),
            'referenced_incidents':incident_references,
            'estimated_affected_legs':context.get('estimated_affected_legs'),
            'interpretation':('Proximity-based incident risk changed the modeled assignment; no actual closure or measured traffic saving was established.' if changed else
                              ('Assignments are unchanged, but street-network geometry was rerouted around a SYNTHETIC event and verified by the routing provider.' if any(x.get('geometry_changed') for x in context.get('street_detours',{}).values()) else
                              'Incident risk did not alter assignments or yield a verified bypass; differences come from base-road costs and fictional constraints.')),
            'geometry_changed_for_synthetic_rehearsal':any(x.get('geometry_changed') for x in context.get('street_detours',{}).values()),
        } if context else None),
        'baseline_id': original.id,
        'proposal_id': proposed.id,
        'status': proposed.status,
        'comparable': comparable,
        'simulated': True,
        'algorithm': ('road-time matrix bounded local-search relocation with counterfactual' if context else 'schematic bounded local-search relocation'),
        'objective': ('OSRM/ORS road-time matrix + road kilometres + modeled lateness + SOFT incident point-proximity penalty, subject to vehicle capacity' if context else 'Schematic distance + approximate incident penalty; road geometry calculated after assignment'),
        'reassigned_delivery_count': len(reassigned),
        'distance_before_km': original.metrics.distance_km,
        'distance_after_km': proposed.metrics.distance_km,
        'distance_delta_km': (round(proposed.metrics.distance_km-original.metrics.distance_km,2) if comparable else None),
        'flags_before': original.metrics.exposures,
        'flags_after': proposed.metrics.exposures,
        'vehicles': rows,
        'limitations': [
            'The optimizer operates on fictional vehicles and delivery orders.',
            ('Road geometry and distance come from a street-network provider, not live-traffic ETA.' if comparable and proposed.routes and all(r.fidelity == 'road_network' for r in proposed.routes) else 'Schematic distances and times are NOT verified road navigation data.'),
            'Municipal event proximity is not a verified street-segment closure.',
            'A metric difference does not establish causality or actual financial savings.',
        ],
    }
