"""Defensive, rate-limited, opt-in Madrid Open Data connectors.

Read-only. Uses verified public download URLs. Schema changes cause explicit errors,
not silently fabricated observations. No claims of real-time DUM bay availability.
"""
from __future__ import annotations
import asyncio
from functools import lru_cache
from datetime import datetime,timezone
import re
import html
import csv
import io
import unicodedata
from urllib.parse import urlparse
import httpx
from defusedxml import ElementTree as ET
from ..models import Camera,Incident,LoadingZone,DataProvenance,TrafficSensor
from ..settings import get_settings

SOURCES={
    'traffic':{
      'url':'https://datos.madrid.es/dataset/202087-0-trafico-intensidad/resource/202087-0-trafico-intensidad/download/202087-0-trafico-intensidad.xml',
      'alternate_url':'https://informo.madrid.es/informo/tmadrid/pm.xml',
      'page':'https://datos.madrid.es/dataset/202087-0-trafico-intensidad','format':'XML','cadence':'~5 minutes',
    },
    'incidents':{
      'url':'https://datos.madrid.es/dataset/202062-0-trafico-incidencias-viapublica/resource/202062-0-trafico-incidencias-viapublica/download/202062-0-trafico-incidencias-viapublica.xml',
      'alternate_url':'https://informo.madrid.es/informo/tmadrid/incid_aytomadrid.xml',
      'page':'https://datos.madrid.es/dataset/202062-0-trafico-incidencias-viapublica',
      'format':'XML','cadence':'~5 minutes',
    },
    'cameras':{
      'url':'https://datos.madrid.es/dataset/202088-0-trafico-camaras/resource/202088-0-trafico-camaras/download/202088-0-trafico-camaras.kml',
      'alternate_url':'https://informo.madrid.es/informo/tmadrid/CCTV.kml',
      'page':'https://datos.madrid.es/dataset/202088-0-trafico-camaras','format':'KML','cadence':'~5 minutes',
    },
    'loading':{
      'url':'https://datos.madrid.es/dataset/208072-0-carga-descarga/resource/208072-0-carga-descarga-geo/download/208072-0-carga-descarga-geo.geo',
      'alternate_url':'https://datos.madrid.es/dataset/208072-0-carga-descarga/resource/208072-1-carga-descarga-csv/download/208072-1-carga-descarga-csv.csv',
      'page':'https://datos.madrid.es/dataset/208072-0-carga-descarga','format':'GeoJSON / CSV fallback','cadence':'monthly',
    },
}

def _tag(raw:str)->str:return raw.rsplit('}',1)[-1].lower().replace('_','').replace('-','').strip()

def _flatten(node:ET.Element)->dict[str,str]:
    out={}
    for element in node.iter():
        if element is node:continue
        txt=(element.text or '').strip()
        if txt and len(txt)<1000:out.setdefault(_tag(element.tag),txt)
    return out

def _pick(fields:dict[str,str],*names:str)->str|None:
    for name in names:
        if name in fields and fields[name]:return fields[name]
    return None

def _number(value:str|None)->float|None:
    if value is None:return None
    try:return float(value.strip().replace(',','.'))
    except (ValueError,AttributeError):return None

@lru_cache(maxsize=1)
def _utm_transformer():
    from pyproj import Transformer
    return Transformer.from_crs('EPSG:25830','EPSG:4326',always_xy=True)

def _location(fields:dict[str,str])->tuple[float,float]|None:
    lat=_number(_pick(fields,'latitud','lat','latitude'))
    lon=_number(_pick(fields,'longitud','lon','lng','longitude'))
    if lat is not None and lon is not None and 40.2<lat<40.7 and -4.0<lon<-3.3:return (lon,lat)
    # Many Madrid XML resources supply ETRS89 UTM zone 30N. This optional path
    # requires pyproj; otherwise unsupported coords are explicitly skipped.
    x=_number(_pick(fields,'coordenadax','stx','utm_x','utmx','x'))
    y=_number(_pick(fields,'coordenaday','sty','utm_y','utmy','y'))
    if x is not None and y is not None and 300000<x<600000 and 4300000<y<4700000:
        try:
            lon,lat=_utm_transformer().transform(x,y)
            if 40.2<lat<40.7 and -4.0<lon<-3.3:return lon,lat
        except ImportError:return None
    return None

def _provenance(kind:str)->DataProvenance:
    return DataProvenance(origin='municipal_open_data',label='Ayuntamiento de Madrid · Open Data CC BY 4.0',
        updated_at=datetime.now(timezone.utc).isoformat(),url=SOURCES[kind]['page'])

def parse_incidents_xml(content:bytes,limit:int=80)->list[Incident]:
    root=ET.fromstring(content)
    incidents=[]
    for node in root.iter():
        tag=_tag(node.tag)
        if tag not in {'incidencia','incidenciastr','incidenciadetalle','item','incidenciaactual'}:continue
        fields=_flatten(node);point=_location(fields)
        if not point:continue
        title=_pick(fields,'descripcion','titulo','nombre','tipoincidencia','localizacion') or 'Municipal traffic incident'
        kind_hint=(title+' '+str(_pick(fields,'tipo','tipoevento','subtipo') or '')).lower()
        kind='roadworks' if any(k in kind_hint for k in ['obra','asfalt','mantenim']) else ('accident' if 'accident' in kind_hint else ('closure' if any(k in kind_hint for k in ['corte','cerrado','cierre']) else ('event' if 'event' in kind_hint else 'other')))
        incidents.append(Incident(id=str(_pick(fields,'codigo','id','identificador') or f'M-{len(incidents):04}'),
             title=title[:100],location=point,kind=kind,severity='medium',radius_m=100,
             detail=(_pick(fields,'descripcion','observaciones') or title)[:500],
             starts_at=_pick(fields,'fechainicio','fecha'),ends_at=_pick(fields,'fechafin'),provenance=_provenance('incidents')))
        if len(incidents)>=limit:break
    return incidents

# Only public municipal camera hosts may be fetched by our image proxy.
CAMERA_HOSTS={'datos.madrid.es','informo.madrid.es','informo.munimadrid.es','www.madrid.es','www.mc30.es'}

def _safe_image(url:str|None)->str|None:
    if not url:return None
    url=html.unescape(url.strip().strip('\"').strip("'"))
    try:
        parsed=urlparse(url)
        if parsed.scheme not in {'https','http'} or parsed.hostname not in CAMERA_HOSTS:return None
        if parsed.port not in (None,80,443) or parsed.username or parsed.password:return None
        if not re.search(r'\.(?:jpg|jpeg|png)$',parsed.path,re.I):return None
        return url
    except (ValueError,AttributeError):return None

def _extract_camera_image(text:str)->str|None:
    # CDATA may contain HTML <img src=http://informo.munimadrid.es/cameras/Camara01301.jpg?v=..>
    decoded=html.unescape(text)
    for match in re.finditer(r'https?://[^\s\"\'<>]+\.(?:jpg|jpeg|png)(?:\?[^\s\"\'<>]*)?',decoded,re.I):
        candidate=_safe_image(match.group(0))
        if candidate:return candidate
    return None

def parse_camera_kml(content:bytes,limit:int=400)->list[Camera]:
    root=ET.fromstring(content)
    results=[]
    for node in root.iter():
        if _tag(node.tag)!='placemark':continue
        label='Traffic camera';coords=None;img=None
        for child in node.iter():
            tag=_tag(child.tag);txt=(child.text or '').strip()
            if tag=='name' and txt:label=txt[:90]
            if tag=='coordinates' and txt:
                parts=re.split(r'[,\s]+',txt)
                try:
                    lon=float(parts[0]);lat=float(parts[1])
                    if 40.2<lat<40.7 and -4.0<lon<-3.3:coords=(lon,lat)
                except (IndexError,ValueError):pass
            if tag in {'description','image','url','value'} and txt and not img:
                img=_extract_camera_image(txt)
        if coords:results.append(Camera(id=f'C-M{len(results)+1:03}',label=label,location=coords,image_url=img,provenance=_provenance('cameras')))
        if len(results)>=limit:break
    return results

def parse_loading_geojson(payload:dict,limit:int=350)->list[LoadingZone]:
    rows=[]
    for idx,feature in enumerate(payload.get('features',[])):
        geom=feature.get('geometry') or {}
        coords=geom.get('coordinates')
        if geom.get('type')!='Point' or not isinstance(coords,list) or len(coords)<2:continue
        lon,lat=float(coords[0]),float(coords[1])
        if not (40.2<lat<40.7 and -4.0<lon<-3.3):continue
        props={str(k).lower():str(v) for k,v in (feature.get('properties') or {}).items()}
        label=props.get('direccion') or props.get('situacion') or props.get('calle') or f'Loading zone {idx+1}'
        rows.append(LoadingZone(id=f'L-M{idx+1:05}',label=label[:90],location=(lon,lat),
            district=props.get('distrito','Madrid'),schedule=props.get('horario','Check municipal signage'),
            provenance=_provenance('loading')))
        if len(rows)>=limit:break
    return rows


def parse_loading_csv(content:bytes,limit:int=350)->list[LoadingZone]:
    """Fallback for the official 2026 CSV (Gis_X/Gis_Y coordinates use ETRS89 UTM30).

    Never assume that a loading bay is unoccupied; this file is just an inventory.
    """
    text=content.decode('utf-8-sig',errors='replace')
    first=text.splitlines()[0] if text.splitlines() else ''
    delimiter=';' if first.count(';')>=first.count(',') else ','
    rows=[]
    for index,record in enumerate(csv.DictReader(io.StringIO(text),delimiter=delimiter)):
        if not record:continue
        def norm(key:str)->str:
            key=unicodedata.normalize('NFKD',key)
            return ''.join(c for c in key if not unicodedata.combining(c)).lower().replace('_','').replace(' ','').replace('-','')
        row={norm(str(k)):str(v or '').strip() for k,v in record.items() if k is not None}
        point=_location(row)
        if point is None:
            x=_number(row.get('gisx')); y=_number(row.get('gisy'))
            if x is not None and y is not None and 300000<x<600000 and 4300000<y<4700000:
                lon,lat=_utm_transformer().transform(x,y)
                if 40.2<lat<40.7 and -4.0<lon<-3.3:point=(lon,lat)
        if not point:continue
        label=row.get('direccion') or row.get('situacion') or row.get('calle') or row.get('nombre') or f'Reserva {index+1}'
        schedule=row.get('horario') or row.get('limitacionhoraria') or 'Consultar señalización municipal'
        rows.append(LoadingZone(id=f'L-C{index+1:05}',label=label[:90],location=point,
            district=row.get('distrito') or 'Madrid',schedule=schedule,provenance=_provenance('loading')))
        if len(rows)>=limit:break
    return rows


def parse_traffic_xml(content:bytes, max_points:int=1800)->tuple[list[TrafficSensor],int,str|None]:
    """Current municipal pm.xml schema: pm/idelem/intensidad/ocupacion/velocidad/nivelServicio/st_x/st_y.

    Only physically valid readings with WGS84 coordinates are exposed. No ETAs are inferred.
    """
    root=ET.fromstring(content)
    rows:list[TrafficSensor]=[]
    observed_at=None
    for node in root.iter():
        if _tag(node.tag)!='pm':continue
        fields=_flatten(node)
        loc=_location(fields)
        if not loc:continue
        service=_number(_pick(fields,'nivelservicio'))
        level=int(service) if service is not None and service in (0,1,2,3) else None
        def valid_value(key:str, ceiling:float)->float|None:
            v=_number(_pick(fields,key))
            return v if v is not None and 0<=v<=ceiling else None
        intensity=valid_value('intensidad',30000)
        occupancy=valid_value('ocupacion',100)
        speed=valid_value('velocidad',200)
        if all(v is None for v in (intensity,occupancy,speed,level)):continue
        if observed_at is None:
            observed_at=_pick(fields,'fecha','fechahora','fechaactualizacion','hora')
        rows.append(TrafficSensor(id=str(_pick(fields,'idelem','id') or len(rows)+1),location=loc,
            intensity_vph=intensity,occupancy_pct=occupancy,speed_kmh=speed,service_level=level,
            road_name=_pick(fields,'descripcion','nombre')))
    total=len(rows)
    # Evenly sample valid sensor points; accurately disclose the total.
    if total>max_points:
        rows=[rows[min(total-1,int(i*total/max_points))] for i in range(max_points)]
    return rows,total,observed_at

async def fetch_source(kind:str):
    """Controlled download, not arbitrary user URLs (avoids SSRF)."""
    if kind not in SOURCES:raise ValueError('Unknown source')
    config=get_settings()
    # Fixed, audited URLs. Try the catalog resource, then the official Informo origin.
    candidates=[SOURCES[kind]['url']]
    if SOURCES[kind].get('alternate_url'):candidates.append(SOURCES[kind]['alternate_url'])
    errors=[]
    async with httpx.AsyncClient(timeout=config.request_timeout_seconds,follow_redirects=False) as client:
        for url in candidates:
            try:
                response=await client.get(url,headers={'User-Agent':'CurbOpsPortfolio/0.6 (educational; rate-limited)'})
                # Do not follow arbitrary redirects (SSRF prevention); the fallback is independently fixed.
                response.raise_for_status()
                if len(response.content)>12_000_000:raise ValueError('Open data response too large')
                if kind=='incidents':result=parse_incidents_xml(response.content,config.live_max_incidents)
                elif kind=='cameras':result=parse_camera_kml(response.content)
                elif kind=='traffic':result=parse_traffic_xml(response.content)
                else:
                    if url.lower().endswith('.csv'):
                        result=parse_loading_csv(response.content)
                    else:
                        try:
                            payload=response.json()
                        except ValueError as exc:
                            hint=response.text[:70].replace('\n',' ').replace('\r',' ')
                            raise ValueError(f'Expected 2026 GeoJSON file, got {response.headers.get("content-type", "unknown")}: {hint!r}') from exc
                        if not isinstance(payload,dict) or payload.get('type')!='FeatureCollection':
                            raise ValueError('Loading reserve document is not a GeoJSON FeatureCollection')
                        result=parse_loading_geojson(payload)
                count=len(result[0]) if kind=='traffic' else len(result)
                if count==0:raise ValueError(f'{kind}: zero valid records; source schema may have changed')
                return result
            except (httpx.HTTPError, ValueError, ET.ParseError) as exc:
                errors.append(f'{urlparse(url).hostname}: {type(exc).__name__} ({str(exc)[:120]})')
    raise RuntimeError('; '.join(errors))
