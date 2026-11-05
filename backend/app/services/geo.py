"""Small geometry utilities; approximate metric projection only for a local demo."""
from __future__ import annotations
import math
from ..models import Coordinate

KM_PER_DEG_LAT = 111.19

def to_xy(p: Coordinate) -> tuple[float,float]:
    lon,lat=p
    return (lon*KM_PER_DEG_LAT*math.cos(math.radians(40.42)),lat*KM_PER_DEG_LAT)

def distance_km(a: Coordinate,b: Coordinate) -> float:
    ax,ay=to_xy(a);bx,by=to_xy(b)
    return math.hypot(ax-bx,ay-by)

def point_segment_km(p: Coordinate,a: Coordinate,b: Coordinate) -> float:
    px,py=to_xy(p);ax,ay=to_xy(a);bx,by=to_xy(b)
    vx,vy=bx-ax,by-ay
    t=max(0.0,min(1.0,((px-ax)*vx+(py-ay)*vy)/(vx*vx+vy*vy+1e-12)))
    return math.hypot(px-(ax+t*vx),py-(ay+t*vy))

def offset_point_km(p:Coordinate,offset_x:float,offset_y:float) -> Coordinate:
    lon,lat=p
    return (lon+offset_x/(KM_PER_DEG_LAT*math.cos(math.radians(40.42))),lat+offset_y/KM_PER_DEG_LAT)
