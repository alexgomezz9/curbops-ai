"""Geographic context for Madrid incidents. Proximity is NOT traffic causality."""
from __future__ import annotations
from math import radians,sin,cos,asin,sqrt
from ..store import DemoStore


def distance_m(a: tuple[float,float], b: tuple[float,float]) -> float:
    """Great-circle distance, accepts GeoJSON [longitude,latitude]."""
    lon1,lat1=map(radians,a);lon2,lat2=map(radians,b)
    dlat=lat2-lat1;dlon=lon2-lon1
    h=sin(dlat/2)**2+cos(lat1)*cos(lat2)*sin(dlon/2)**2
    return 12742000*asin(min(1,sqrt(h)))


def incident_evidence(store:DemoStore, incident_id:str, radius_m:int=800, limit:int=6)->dict|None:
    """Snapshot-based proximity analysis; neither routing nor causal inference.

    Municipal traffic points may be sampled by the upstream ingestion for UI.
    A zero count only means none were found IN THAT LOADED SUBSET.
    """
    with store.lock:
        incidents=list(store.incidents)
        sensors=list(store.traffic_points)
        cameras=list(store.cameras)
        zones=list(store.zones)
        fetched=store.traffic_fetched_at
        observed=store.traffic_observed_at
        total=store.traffic_total_valid
    incident=next((item for item in incidents if item.id==incident_id),None)
    if incident is None:return None
    def enrich(items):
        return sorted(((distance_m(incident.location,x.location),x) for x in items),key=lambda p:p[0])
    def inside(items): return [(d,x) for d,x in enrich(items) if d<=radius_m]
    nearby_sensors=inside(sensors)
    nearby_cameras=inside(cameras)
    nearby_zones=inside(zones)
    return {
        'incident':incident.model_dump(mode='json'),
        'radius_m':radius_m,
        'calculation':'haversine_proximity',
        'sensor_records_loaded':len(sensors),
        'sensor_records_total_reported':total,
        'fetched_at':fetched,
        'observed_at':observed,
        'sensor_count_nearby':len(nearby_sensors),
        'congested_sensor_count':sum(1 for _,s in nearby_sensors if s.service_level==3),
        'camera_count_nearby':len(nearby_cameras),
        'loading_zone_count_nearby':len(nearby_zones),
        'sensors':[{'distance_m':round(d),**s.model_dump(mode='json')} for d,s in nearby_sensors[:limit]],
        'cameras':[{'distance_m':round(d),**c.model_dump(mode='json')} for d,c in nearby_cameras[:limit]],
        'loading_zones':[{'distance_m':round(d),**z.model_dump(mode='json')} for d,z in nearby_zones[:limit]],
        'note':('Distances are geometric proximity, not connectivity or evidence of a road closure. '
                'Sensors and cameras need not measure the same road segment. '
                'Sensor observations may be sampled; timestamps may be unavailable. '
                'No real-time ETA is computed.'),
    }
