"""Explicit and auditable what-if. A published notice is never promoted to a real closure."""
from datetime import datetime, timedelta, timezone
from ..models import Incident, DataProvenance
from ..scenario import VEHICLES
from ..store import DemoStore
from .geo import point_segment_km


def set_rehearsal(store: DemoStore, vehicle_id: str, *, clear: bool = False,
                  incident_id: str | None = None) -> Incident | None:
    if vehicle_id not in {*(v.id for v in VEHICLES), 'AUTO'}:
        raise ValueError('Unknown vehicle')
    with store.lock:
        if vehicle_id == 'AUTO':
            if not incident_id:
                vehicle_id='V-02'
            else:
                if not store.no_risk_plan:
                    raise ValueError('Calculate scenario B before simulating an incident.')
                match=next((i for i in store.incidents if i.id==incident_id),None)
                if not match:
                    raise ValueError('Unknown reference incident.')
                ranking=[]
                for route in store.no_risk_plan.routes:
                    if len(route.coordinates)<2:continue
                    closest=min(point_segment_km(match.location,a,b)*1000
                        for a,b in zip(route.coordinates[:-1],route.coordinates[1:]))
                    ranking.append((closest,route.vehicle_id))
                if not ranking or min(ranking)[0]>350:
                    raise ValueError('No route B passes sufficiently close to this notice for a rehearsal.')
                vehicle_id=min(ranking)[1]
        if clear:
            item = None
        else:
            if not store.no_risk_plan:
                raise ValueError('Calculate scenario B before simulating an incident.')
            route = next((r for r in store.no_risk_plan.routes if r.vehicle_id == vehicle_id), None)
            if not route or len(route.coordinates) < 5:
                raise ValueError('Selected vehicle has no usable street polyline in B.')
            if incident_id:
                referenced = next((i for i in store.incidents if i.id == incident_id and i.id != 'SIM-ROADWORKS'), None)
                if referenced is None:
                    raise ValueError('Unknown reference incident.')
                distance_m = min(point_segment_km(referenced.location, a, b) * 1000
                    for a,b in zip(route.coordinates[:-1],route.coordinates[1:]))
                if distance_m > 350:
                    raise ValueError('This notice is too far from selected route B for a meaningful rehearsal.')
                point=referenced.location
                title=f'SIMULATION · Notice {incident_id} treated as a hypothetical obstacle on {vehicle_id}'
                detail=(f'Hypothetical obstacle inspired by notice {incident_id}. The original source does NOT prove '
                        'this road is closed now. This rehearsal makes no claim about real traffic or route delays.')
            else:
                point=route.coordinates[int(len(route.coordinates)*.43)]
                title=f'SIMULATION · Roadworks on {vehicle_id} route'
                detail='Operator-created hypothetical roadworks on a routed street point; no municipal closure verified.'
            now=datetime.now(timezone.utc)
            item=Incident(id='SIM-ROADWORKS',title=title, location=point,
                          kind='roadworks',severity='high',radius_m=180,
                          detail=detail,starts_at=now.isoformat(),
                          ends_at=(now+timedelta(hours=2)).isoformat(),
                          provenance=DataProvenance(origin='synthetic',label='Explicit counterfactual rehearsal'))
        store.rehearsal_incident=item
        store.generation+=1
        store.proposed=None
        store.approved=None
        store.decision_context=None
        store.no_risk_plan=None
        store.road_baseline=None
        store.planned_incident_signature=None
        return item
