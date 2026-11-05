"""Differences between two actual municipal point measurements. No predictions."""
from __future__ import annotations
from ..models import TrafficSensor

def summarize_changes(before:list[TrafficSensor],after:list[TrafficSensor],
                      previous_at:str|None,current_at:str|None)->dict:
    old={s.id:s for s in before if s.service_level is not None}
    comparable=[]
    for sensor in after:
        prior=old.get(sensor.id)
        if prior is None or sensor.service_level is None:continue
        delta=sensor.service_level-prior.service_level
        if delta == 0:continue
        comparable.append({'id':sensor.id,'location':sensor.location,'road_name':sensor.road_name,
                           'previous_level':prior.service_level,'current_level':sensor.service_level,
                           'delta':delta,'speed_kmh':sensor.speed_kmh})
    # Keep strongest worsening first; list is limited to avoid big payloads.
    comparable.sort(key=lambda row:(-row['delta'],row['id']))
    available=bool(before and after and previous_at and current_at)
    return {'available':available, 'previous_at':previous_at,'current_at':current_at,
        'compared_sensor_count':sum(1 for s in after if s.id in old and s.service_level is not None),
        'worsened':sum(1 for row in comparable if row['delta']>0),
        'improved':sum(1 for row in comparable if row['delta']<0),
        'changed':comparable[:24] if available else [],
        'note':('Observed change between two downloaded samples; no causal attribution or route ETA.'
                if available else 'At least two successful municipal traffic downloads are needed.')}
