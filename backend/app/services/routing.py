"""Opt-in road geometries using HeiGIT ORS or the public, noncommercial OSRM demo.

The public OSRM demonstration server is rate-limited and has NO uptime promise.
Do not treat either provider's base-traffic durations as current traffic ETAs.
"""
from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from typing import Any
import httpx
from ..models import Coordinate
from ..settings import get_settings

# Per-process limiter and bounded response cache; one worker only in this MVP.
_osrm_lock = asyncio.Lock()
_osrm_last_request = 0.0
_cache: OrderedDict[tuple, tuple[float, tuple[list[Coordinate], float, float]]] = OrderedDict()
_CACHE_MAX, _CACHE_TTL_S = 120, 900


def _validate_points(points: list[Coordinate]) -> None:
    if not 2 <= len(points) <= 10:
        raise ValueError('Road request requires between 2 and 10 waypoints')
    for lon, lat in points:
        if not (-4.05 < lon < -3.3 and 40.2 < lat < 40.7):
            raise ValueError('Route waypoints must be within the Madrid demonstration area')


def _cache_key(provider: str, points: list[Coordinate]) -> tuple:
    return (provider, tuple((round(lon, 6), round(lat, 6)) for lon, lat in points))


def _get_cached(key: tuple):
    entry = _cache.get(key)
    if entry is None:
        return None
    created, data = entry
    if time.monotonic() - created > _CACHE_TTL_S:
        _cache.pop(key, None)
        return None
    _cache.move_to_end(key)
    return data


def _put_cached(key: tuple, value: tuple[list[Coordinate], float, float]) -> None:
    _cache[key] = (time.monotonic(), value)
    _cache.move_to_end(key)
    while len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)


async def fetch_road_route(points: list[Coordinate], avoid_polygons: dict | None = None) -> tuple[list[Coordinate], float, float]:
    global _osrm_last_request
    settings = get_settings()
    provider = settings.routing_provider
    _validate_points(points)
    if provider == 'ors':
        if not settings.ors_api_key:
            raise RuntimeError('ORS_API_KEY is required when ROUTING_PROVIDER=ors')
        payload: dict[str, Any] = {'coordinates': [list(p) for p in points]}
        if avoid_polygons:
            payload['options'] = {'avoid_polygons': avoid_polygons}
        async with httpx.AsyncClient(timeout=35) as client:
            response = await client.post(f'{settings.ors_base_url.rstrip("/")}/v2/directions/driving-car/geojson',
                headers={'Authorization': settings.ors_api_key, 'Content-Type': 'application/json'}, json=payload)
            response.raise_for_status()
            feature = response.json()['features'][0]
            coords = feature['geometry']['coordinates']
            summary = feature['properties']['summary']
            return ([(float(x), float(y)) for x, y in coords], float(summary['distance']) / 1000,
                    float(summary['duration']) / 60)

    if provider != 'osrm_demo':
        raise RuntimeError('Road routing disabled. Choose ROUTING_PROVIDER=osrm_demo or ors.')
    if avoid_polygons is not None:
        raise ValueError('OSRM demo cannot apply arbitrary incident avoidance polygons')
    key = _cache_key(provider, points)
    cached = _get_cached(key)
    if cached is not None:
        return cached
    # Respect the public demo policy: at most one request per second. Serialize
    # all requests in this single-process portfolio backend.
    async with _osrm_lock:
        cached = _get_cached(key)
        if cached is not None:
            return cached
        wait = max(0.0, 1.15 - (time.monotonic() - _osrm_last_request))
        if wait:
            await asyncio.sleep(wait)
        _osrm_last_request = time.monotonic()
        coords = ';'.join(f'{lon:.6f},{lat:.6f}' for lon, lat in points)
        url = f'{settings.osrm_base_url.rstrip("/")}/route/v1/driving/{coords}'
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                response = await client.get(url, params={'overview': 'full', 'geometries': 'geojson', 'steps': 'false'})
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RuntimeError(f'OSRM demo unavailable ({type(exc).__name__}). Try again or use your own ORS key.') from exc
        if payload.get('code') != 'Ok' or not payload.get('routes'):
            raise RuntimeError(f'OSRM cannot route between these points: {str(payload.get("code"))[:40]}')
        first = payload['routes'][0]
        coordinates = first['geometry']['coordinates']
        if not coordinates or not isinstance(first.get('distance'), (int, float)):
            raise RuntimeError('OSRM returned an incomplete route')
        result = ([(float(x), float(y)) for x, y in coordinates], float(first['distance']) / 1000,
                  float(first['duration']) / 60)
        _put_cached(key, result)
        return result


# Single-road-matrix cache; routes and tables share the SAME OSRM demo rate limiter.
_matrix_cache: OrderedDict[tuple,tuple[float,dict]] = OrderedDict()

async def fetch_road_matrix(points: list[Coordinate]) -> dict:
    """Fetch an all-pairs road matrix (minutes, kilometres). No geometric fallback.

    OSRM Table returns base durations/distances of fastest road-network paths.
    ORS Matrix uses the same conceptual contract. Neither includes live traffic
    or applies Madrid incident closures.
    """
    global _osrm_last_request
    if not 2<=len(points)<=26:
        raise ValueError('Road matrix requires 2 to 26 Madrid-area waypoints')
    for lon,lat in points:
        if not (-4.05<lon<-3.3 and 40.2<lat<40.7):
            raise ValueError('Road matrix points must be in the Madrid demo area')
    cfg=get_settings()
    if cfg.routing_provider=='ors':
        if not cfg.ors_api_key:raise RuntimeError('ORS_API_KEY missing')
        async with httpx.AsyncClient(timeout=35) as client:
            response=await client.post(f'{cfg.ors_base_url.rstrip("/")}/v2/matrix/driving-car',
                headers={'Authorization':cfg.ors_api_key,'Content-Type':'application/json'},
                json={'locations':[list(p) for p in points],'metrics':['distance','duration']})
            response.raise_for_status()
            payload=response.json()
    elif cfg.routing_provider=='osrm_demo':
        key=('matrix',cfg.osrm_base_url,tuple((round(x,6),round(y,6)) for x,y in points))
        cached=_matrix_cache.get(key)
        if cached and time.monotonic()-cached[0]<900:return cached[1]
        async with _osrm_lock:
            cached=_matrix_cache.get(key)
            if cached and time.monotonic()-cached[0]<900:return cached[1]
            wait=max(0.0,1.15-(time.monotonic()-_osrm_last_request))
            if wait:await asyncio.sleep(wait)
            _osrm_last_request=time.monotonic()
            coords=';'.join(f'{lon:.6f},{lat:.6f}' for lon,lat in points)
            async with httpx.AsyncClient(timeout=35) as client:
                response=await client.get(f'{cfg.osrm_base_url.rstrip("/")}/table/v1/driving/{coords}',
                    params={'annotations':'duration,distance'})
                response.raise_for_status()
                payload=response.json()
            if payload.get('code')!='Ok':
                raise RuntimeError(f'OSRM road table error: {str(payload.get("code"))[:60]}')
            result=_validate_matrix_payload(payload,len(points))
            _matrix_cache[key]=(time.monotonic(),result)
            while len(_matrix_cache)>12:_matrix_cache.popitem(last=False)
            return result
    else:
        raise RuntimeError('Road matrix requires OSRM demo or ORS provider')
    return _validate_matrix_payload(payload,len(points))

def _validate_matrix_payload(payload:dict,n:int)->dict:
    durations=payload.get('durations');distances=payload.get('distances')
    if not isinstance(durations,list) or not isinstance(distances,list) or len(durations)!=n or len(distances)!=n:
        raise ValueError('Provider did not return a complete time + distance matrix')
    from math import isfinite
    for arr in (durations,distances):
        if any(not isinstance(row,list) or len(row)!=n for row in arr):
            raise ValueError('Incomplete road matrix rows')
        if any(not isinstance(x,(int,float)) or not isfinite(x) or x<0 for row in arr for x in row):
            raise ValueError('Unreachable matrix entry; cannot optimize using imaginary roads')
    return {'minutes':[[round(float(x)/60,5) for x in row] for row in durations],
            'kilometres':[[round(float(x)/1000,6) for x in row] for row in distances]}
