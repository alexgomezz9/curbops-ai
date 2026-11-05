'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import maplibregl, { Map as LibreMap, GeoJSONSource } from 'maplibre-gl';
import { LocateFixed, Play, Pause, RotateCcw, Camera as CameraIcon, RefreshCcw, X, Mountain, Layers, Building2 } from 'lucide-react';
import type {MissionSnapshot,DispatchPlan,LayerSelection,Incident,Position,CitySignals,Camera,IncidentEvidence,CityChanges} from '@/lib/types';
import {api} from '@/lib/api';

type Props={snapshot:MissionSnapshot;activePlan:DispatchPlan;referencePlan?:DispatchPlan|null;isolatedVehicle?:boolean;onIsolateVehicle?:(id:string)=>void;layers:LayerSelection;selectedIncident:string|null;onSelectIncident:(id:string)=>void;selectedVehicle:string|null;onSelectVehicle:(id:string|null)=>void;compare:boolean;theme:'light'|'dark';traffic?:CitySignals|null;signalMode?:boolean;cameraFocusId?:string|null;onCloseCamera?:()=>void;sensorFocusId?:string|null;routeFocusToken?:number;comparisonUi?:boolean;comparisonMix?:number;highlightIncidentIds?:string[];avoidedIncidentIds?:string[];focusSensorIds?:string[];evidence?:IncidentEvidence|null;intelMode?:boolean;changes?:CityChanges|null};
const styles={dark:'https://tiles.openfreemap.org/styles/dark',light:'https://tiles.openfreemap.org/styles/bright'} as const;
/** Linear interpolation across the schematic polyline, used ONLY for labelled demo playback. */
function alongRoute(points:Position[],fraction:number):Position{
 if(points.length===0)return [-3.7005,40.4206];
 if(points.length===1)return points[0];
 const lengths=points.slice(1).map((p,i)=>Math.hypot((p[0]-points[i][0])*.77,p[1]-points[i][1]));
 const total=lengths.reduce((sum,v)=>sum+v,0);
 if(total===0)return points[0];
 let remaining=Math.max(0,Math.min(1,fraction))*total;
 for(let i=0;i<lengths.length;i++){
  const distance=lengths[i];
  if(remaining<=distance||i===lengths.length-1){
   const t=distance>0?Math.max(0,Math.min(1,remaining/distance)):0;
   return [points[i][0]+(points[i+1][0]-points[i][0])*t,points[i][1]+(points[i+1][1]-points[i][1])*t];
  }
  remaining-=distance;
 }
 return points[points.length-1];
}

/** Approximate geodesic distance from a *point* to a local polyline segment.
 * Used solely to DRAW the vicinity of a municipal incident, not to mark a closure.
 */
function segmentNearIncident(a:Position,b:Position,point:Position,radiusM:number){
 const factor=Math.cos(point[1]*Math.PI/180)*111195;
 const dx=(b[0]-a[0])*factor,dy=(b[1]-a[1])*111195;
 const px=(point[0]-a[0])*factor,py=(point[1]-a[1])*111195;
 const den=dx*dx+dy*dy;
 const t=den===0?0:Math.max(0,Math.min(1,(px*dx+py*dy)/den));
 return Math.hypot(px-t*dx,py-t*dy)<=radiusM;
}
function pointFeature(point:Position,props:Record<string,unknown>):GeoJSON.Feature<GeoJSON.Point>{return {type:'Feature',geometry:{type:'Point',coordinates:point},properties:props};}
function fc(features:GeoJSON.Feature[]):GeoJSON.FeatureCollection{return {type:'FeatureCollection',features};}
const asPoints=(rows:{location:Position;id:string}[],custom:(v:typeof rows[number])=>Record<string,unknown>)=>fc(rows.map(x=>pointFeature(x.location,custom(x))));
function source(map:LibreMap,id:string,data:GeoJSON.FeatureCollection){if(!map.getSource(id))map.addSource(id,{type:'geojson',data});else (map.getSource(id) as GeoJSONSource).setData(data);}
function clusterSource(map:LibreMap,id:string,data:GeoJSON.FeatureCollection){if(!map.getSource(id))map.addSource(id,{type:'geojson',data,cluster:true,clusterRadius:43,clusterMaxZoom:13});else (map.getSource(id) as GeoJSONSource).setData(data);}
function checkLayer(map:LibreMap,id:string){return Boolean(map.getLayer(id));}
function ensureLayer(map:LibreMap,layer:Parameters<LibreMap['addLayer']>[0]){if(!checkLayer(map,layer.id))map.addLayer(layer);}
export default function MapPanel({snapshot,activePlan,referencePlan,isolatedVehicle=false,onIsolateVehicle,layers,selectedIncident,onSelectIncident,selectedVehicle,onSelectVehicle,compare,theme,traffic,signalMode=false,cameraFocusId,onCloseCamera,sensorFocusId,routeFocusToken=0,comparisonUi=false,comparisonMix=55,highlightIncidentIds=[],avoidedIncidentIds=[],focusSensorIds=[],evidence,intelMode=false,changes}:Props){
 const ref=useRef<HTMLDivElement>(null), mapRef=useRef<LibreMap|null>(null);const [ready,setReady]=useState(false),[error,setError]=useState(false);
 const [playing,setPlaying]=useState(false),[playbackProgress,setPlaybackProgress]=useState(0),progressRef=useRef(0);
 const [followReplay,setFollowReplay]=useState(false),lastFollowCameraAt=useRef(0);
 const [densityView,setDensityView]=useState(false);
 const [legendOpen,setLegendOpen]=useState(false);
 const [wheelZoom,setWheelZoom]=useState(true);
 const [changeHighlights,setChangeHighlights]=useState(true);
 const [buildings3D,setBuildings3D]=useState(false);
 const [buildingsError,setBuildingsError]=useState(false);
 const [inspectorOpen,setInspectorOpen]=useState(true);
 useEffect(()=>setInspectorOpen(true),[selectedVehicle]);
 const [chosenCamera,setChosenCamera]=useState<Camera|null>(null),[imageRefresh,setImageRefresh]=useState(0),[imageError,setImageError]=useState(false),[terrain,setTerrain]=useState(false);
 const camerasRef=useRef(snapshot.cameras);camerasRef.current=snapshot.cameras;
 const previousRouteFocus=useRef('');
 const hasFittedSensorGrid=useRef(false);
 const hasRoadGeometries=activePlan.routes.length>0&&activePlan.routes.every(r=>r.fidelity==='road_network');
 const baselineRoadGeometries=snapshot.original_plan.routes.every(r=>r.fidelity==='road_network');
 useEffect(()=>{
   if(!chosenCamera)return;
   const timer=window.setInterval(()=>{setImageError(false);setImageRefresh(Date.now());},300_000);
   return ()=>window.clearInterval(timer);
 },[chosenCamera]);
 const handlersRef=useRef({onSelectIncident,onSelectVehicle,onIsolateVehicle});handlersRef.current={onSelectIncident,onSelectVehicle,onIsolateVehicle};
 useEffect(()=>{
  if(!ref.current||mapRef.current)return;
  const map=new maplibregl.Map({container:ref.current,style:styles[theme],center:[-3.7005,40.4206],zoom:12.8,pitch:20,bearing:-12,attributionControl:false});
  map.addControl(new maplibregl.NavigationControl({showCompass:false}),'bottom-left');
  map.addControl(new maplibregl.AttributionControl({compact:true}),'bottom-right');
  mapRef.current=map;
  // Zoom is intentionally available again. The toggle lets operators protect
  // normal page scrolling when not working in the full-map view.
  map.scrollZoom.enable();
  map.on('styleimagemissing',(evt)=>{if(evt.id==='wood-pattern'&&!map.hasImage(evt.id)){map.addImage(evt.id,{width:1,height:1,data:new Uint8Array([0,0,0,0])});}});
  map.on('load',()=>{setReady(true);map.resize();});
  // The map can mount while a tab or column is changing width. Refit its canvas
  // whenever the actual container changes size, not only on window.resize.
  const observer=new ResizeObserver(()=>{map.resize();});
  observer.observe(ref.current);
  map.on('error',e=>{const msg=String(e?.error?.message||'');if(msg.toLowerCase().includes('style'))setError(true);});
  map.on('mousemove',e=>{const hits=map.queryRenderedFeatures(e.point,{layers:['incident-dot','incident-icon','camera-dot','camera-icon','traffic-sensors','vehicle-halos','route-active-stroke'].filter(id=>!!map.getLayer(id))});map.getCanvas().style.cursor=hits.length?'pointer':'';});
  map.on('dblclick',e=>{
    const matches=map.queryRenderedFeatures(e.point,{layers:['route-active-stroke','route-baseline-stroke','vehicle-halos'].filter(id=>!!map.getLayer(id))});
    const id=String(matches[0]?.properties?.id||'');
    if(id){e.preventDefault();handlersRef.current.onSelectVehicle(id);handlersRef.current.onIsolateVehicle?.(id);}
  });
  map.on('click',e=>{
    const cluster=map.queryRenderedFeatures(e.point,{layers:['camera-clusters','traffic-clusters'].filter(id=>!!map.getLayer(id))});
    if(cluster.length){map.easeTo({center:e.lngLat,zoom:Math.min(18,map.getZoom()+2),duration:650});return;}
    const cameraHits=map.queryRenderedFeatures(e.point,{layers:['camera-dot','camera-icon'].filter(id=>!!map.getLayer(id))});
    if(cameraHits.length){const id=String(cameraHits[0].properties?.id||'');const camera=camerasRef.current.find(c=>c.id===id);
      if(camera){setChosenCamera(camera);setImageError(false);setImageRefresh(Date.now());map.easeTo({center:camera.location,zoom:Math.max(14.4,map.getZoom()),duration:650});}
      return;
    }
    const feature=map.queryRenderedFeatures(e.point,{layers:['incident-dot','incident-icon','vehicle-halos','route-active-stroke'].filter(id=>!!map.getLayer(id))});
    if(!feature.length){
      const routes=map.queryRenderedFeatures(e.point,{layers:['route-active-stroke'].filter(id=>!!map.getLayer(id))});
      if(routes.length){const vehicleId=String(routes[0].properties?.id||'');if(vehicleId)handlersRef.current.onSelectVehicle(vehicleId);return;}
      const point=map.queryRenderedFeatures(e.point,{layers:['traffic-sensors'].filter(id=>!!map.getLayer(id))});
      if(point.length){
        const x=point[0];const el=document.createElement('div');el.className='v5SensorPopup';
        const title=document.createElement('strong');title.textContent=`Sensor #${String(x.properties?.id||'')}`;el.appendChild(title);
        const desc=document.createElement('span');desc.textContent=`Service level: ${String(x.properties?.level??'?')} · intensity: ${x.properties?.intensity>=0?x.properties?.intensity+' veh/h':'not reported'} · speed: ${x.properties?.speed>=0?x.properties?.speed+' km/h':'not reported'}`;el.appendChild(desc);
        new maplibregl.Popup({closeButton:true,maxWidth:'260px'}).setLngLat(e.lngLat).setDOMContent(el).addTo(map);
      }
      return;
    }
    const f=feature[0];const id=String(f.properties?.id||'');
    if(f.layer.id==='incident-dot'||f.layer.id==='incident-icon')handlersRef.current.onSelectIncident(id);
    if(f.layer.id==='vehicle-halos'||f.layer.id==='route-active-stroke')handlersRef.current.onSelectVehicle(id);
  });
  return ()=>{observer.disconnect();map.remove();mapRef.current=null;};
 },[]);
 useEffect(()=>{const map=mapRef.current;if(!map)return;if(wheelZoom)map.scrollZoom.enable();else map.scrollZoom.disable();},[wheelZoom]);
 // MapLibre official OpenFreeMap building extrusions; independent of logistics routing.
 useEffect(()=>{
   const map=mapRef.current;
   if(!ready||!map||!buildings3D){if(map?.getLayer('v8-buildings'))map.setLayoutProperty('v8-buildings','visibility','none');return;}
   try{
     if(!map.getSource('v8-building-vector'))map.addSource('v8-building-vector',{type:'vector',url:'https://tiles.openfreemap.org/planet'});
     if(!map.getLayer('v8-buildings')){
       const label=map.getStyle().layers.find(layer=>layer.type==='symbol')?.id;
       map.addLayer({id:'v8-buildings',type:'fill-extrusion',source:'v8-building-vector',
         'source-layer':'building',minzoom:15,
         filter:['!=',['get','hide_3d'],true],
         paint:{'fill-extrusion-color':theme==='dark'?'#3a8885':'#8abdb1',
           'fill-extrusion-opacity':0.72,
           'fill-extrusion-height':['interpolate',['linear'],['zoom'],15,0,16,['coalesce',['get','render_height'],12]],
           'fill-extrusion-base':['coalesce',['get','render_min_height'],0]}},label);
     }
     map.setLayoutProperty('v8-buildings','visibility','visible');
     map.easeTo({zoom:Math.max(15.2,map.getZoom()),pitch:58,bearing:-24,duration:900});setBuildingsError(false);
   }catch(err){console.warn('3D buildings unavailable',err);setBuildingsError(true);}
 },[ready,buildings3D,theme]);
 const fitPlan=useCallback((vehicleId?:string|null,duration=720)=>{
   const map=mapRef.current;if(!map||!ready||signalMode)return;
   const available=activePlan.routes.filter(r=>r.fidelity==='road_network');
   const routes=vehicleId?available.filter(r=>r.vehicle_id===vehicleId):
     [...available,...(compare?(referencePlan||snapshot.original_plan).routes.filter(r=>r.fidelity==='road_network'):[])];
   const coordinates=routes.flatMap(r=>r.coordinates).filter(([lon,lat])=>Number.isFinite(lon)&&Number.isFinite(lat));
   if(!coordinates.length)return;
   const bounds=new maplibregl.LngLatBounds();coordinates.forEach(p=>bounds.extend(p));
   // MapLibre fitBounds is geographic; the viewport is now based on ROUTES,
   // never the entire municipal incident set (which can span the whole region).
   map.resize();
   const height=map.getContainer().clientHeight;
   const width=map.getContainer().clientWidth;
   map.fitBounds(bounds,{padding:{top:Math.min(86,height*.12),bottom:Math.min(95,height*.16),
     left:Math.min(64,width*.08),right:Math.min(64,width*.08)},
     maxZoom:14.7,duration,essential:true});
 },[ready,signalMode,activePlan,compare,referencePlan,snapshot.original_plan]);
 useEffect(()=>{
   if(!ready||signalMode)return;
   // Refocus only for a plan/fleet selection or a deliberate Fit action.
   // Fresh municipal snapshots may change reference identity but must not hijack the map.
   const focusKey=[selectedVehicle||'all',routeFocusToken,activePlan.id,referencePlan?.id,compare?'compare':'single'].join(':');
   if(previousRouteFocus.current===focusKey)return;
   previousRouteFocus.current=focusKey;
   if(selectedVehicle){fitPlan(selectedVehicle,550);return;}
   if(!selectedIncident)fitPlan(null,650);
 },[ready,signalMode,routeFocusToken,fitPlan,selectedVehicle,selectedIncident,activePlan.id,referencePlan?.id,compare]);
 useEffect(()=>{
   if(!ready)return;
   mapRef.current?.resize();
 },[ready]);
 useEffect(()=>{
   const map=mapRef.current;if(!map||!ready)return;
  try{
    const base=(referencePlan||snapshot.original_plan).routes;
    const planned=activePlan.routes;
    const VISUAL_ROUTE_COLORS:Record<string,string>={'V-01':'#1A66D6','V-02':'#8F47C2','V-03':'#00856C'};
    const toRoutes=(routes:typeof base)=>fc(routes.map(r=>({type:'Feature' as const,geometry:{type:'LineString' as const,coordinates:r.coordinates},properties:{color:VISUAL_ROUTE_COLORS[r.vehicle_id]||r.color,id:r.vehicle_id,incidentHit:selectedIncident&&r.incidents_near.includes(selectedIncident)?1:0}})));
    source(map,'route-baseline',toRoutes(base.filter(r=>r.fidelity==='road_network')));source(map,'route-active',toRoutes(planned.filter(r=>r.fidelity==='road_network')));
    // Only render route SEGMENTS close to a selected incident, not the whole route.
    // These segments are proximity evidence, never automatically blocked streets.
    const focusedIncidents=snapshot.incidents.filter(i=>i.id===selectedIncident||highlightIncidentIds.includes(i.id));
    const nearRoadSegments:GeoJSON.Feature<GeoJSON.LineString>[]=[];
    if(focusedIncidents.length&&!signalMode){
      for(const route of planned.filter(r=>r.fidelity==='road_network')){
        if(selectedVehicle&&route.vehicle_id!==selectedVehicle)continue;
        for(let i=1;i<route.coordinates.length;i++){
          const a=route.coordinates[i-1],b=route.coordinates[i];
          if(focusedIncidents.some(incident=>segmentNearIncident(a,b,incident.location,incident.radius_m))){
            nearRoadSegments.push({type:'Feature',geometry:{type:'LineString',coordinates:[a,b]},
              properties:{id:route.vehicle_id,color:route.color}});
          }
        }
      }
    }
    source(map,'risk-leg-source',fc(nearRoadSegments));
    source(map,'incident-source',fc(snapshot.incidents.filter(x=>!signalMode||x.provenance.origin==='municipal_open_data').map(x=>pointFeature(x.location,{id:x.id,title:(avoidedIncidentIds.includes(x.id)?'OUTSIDE C · ':'')+x.title.slice(0,60),severity:x.severity,origin:x.provenance.origin,avoided:avoidedIncidentIds.includes(x.id)?1:0,selected:x.id===selectedIncident||highlightIncidentIds.includes(x.id)?1:0}))));
    const order=new Map(activePlan.routes.flatMap(r=>r.stop_ids.map((id,index)=>[id,{vehicle:r.vehicle_id,number:index+1}] as const)));
    source(map,'delivery-source',fc(snapshot.deliveries.map(x=>pointFeature(x.location,{id:x.id,priority:x.priority,vehicle:order.get(x.id)?.vehicle||'',seq:order.get(x.id)?.number||0}))));
    source(map,'zone-source',fc(snapshot.loading_zones.map(x=>pointFeature(x.location,{id:x.id}))));
    clusterSource(map,'camera-source',fc(snapshot.cameras.filter(x=>x.provenance.origin==='municipal_open_data').map(x=>pointFeature(x.location,{id:x.id}))));
    source(map,'vehicle-source',fc(snapshot.vehicles.map((v)=>pointFeature(v.location,{id:v.id,color:v.color,selected:v.id===selectedVehicle?1:0}))));
    source(map,'traffic-density-source',fc((traffic?.points||[]).map(x=>pointFeature(x.location,{level:x.service_level??-1}))));
    clusterSource(map,'traffic-source',fc((traffic?.points||[]).filter(x=>!focusSensorIds.length||focusSensorIds.includes(x.id)).map(x=>pointFeature(x.location,{id:x.id,level:x.service_level??-1,intensity:x.intensity_vph??-1,speed:x.speed_kmh??-1,occupancy:x.occupancy_pct??-1}))));
    source(map,'traffic-changes',fc(signalMode&&changeHighlights&&changes?.available?changes.changed.filter(x=>x.delta>0).map(x=>pointFeature(x.location,{id:x.id,delta:x.delta})):[]));
    if(evidence){
      const center=evidence.incident.location;
      const latScale=111195;const lonScale=latScale*Math.cos(center[1]*Math.PI/180);
      const coordinates=Array.from({length:49},(_,index)=>{
        const ang=2*Math.PI*index/48;return [center[0]+Math.cos(ang)*evidence.radius_m/lonScale,
          center[1]+Math.sin(ang)*evidence.radius_m/latScale];
      });
      source(map,'evidence-radius',fc([{type:'Feature',geometry:{type:'Polygon',coordinates:[coordinates]},properties:{}}]));
      const links=[...evidence.sensors.map(x=>({location:x.location,kind:'sensor'})),
                   ...evidence.cameras.map(x=>({location:x.location,kind:'camera'}))].map(x=>({
        type:'Feature' as const,geometry:{type:'LineString' as const,coordinates:[center,x.location]},
        properties:{kind:x.kind}
      }));
      source(map,'evidence-links',fc(links));
    }else{
      source(map,'evidence-radius',fc([]));source(map,'evidence-links',fc([]));
    }
    source(map,'playback-source',fc(activePlan.routes.filter(r=>r.fidelity==='road_network').map(r=>pointFeature(alongRoute(r.coordinates,progressRef.current),{id:r.vehicle_id,color:r.color}))));
    ensureLayer(map,{id:'route-shadow',type:'line',source:'route-active',layout:{'line-cap':'round','line-join':'round'},paint:{'line-color':'#ffffff','line-width':10,'line-opacity':0.78}});
    ensureLayer(map,{id:'route-baseline-ghost',type:'line',source:'route-baseline',layout:{'line-cap':'round','line-join':'round'},paint:{'line-color':'#8194a0','line-width':2.2,'line-opacity':0}});
    ensureLayer(map,{id:'route-baseline-stroke',type:'line',source:'route-baseline',layout:{'line-cap':'round','line-join':'round'},paint:{'line-color':['get','color'],'line-dasharray':[1.9,1.5],'line-offset':3,'line-width':5.4,'line-opacity':compare?0.96:0}});
    ensureLayer(map,{id:'route-active-stroke',type:'line',source:'route-active',layout:{'line-cap':'round','line-join':'round'},paint:{'line-color':['get','color'],'line-offset':compare?-2.5:0,'line-width':selectedVehicle?['case',['==',['get','id'],selectedVehicle],8.3,2.6]:7.2,'line-opacity':selectedVehicle?['case',['==',['get','id'],selectedVehicle],1,0.24]:0.96}});
    ensureLayer(map,{id:'route-incident-proximity',type:'line',source:'risk-leg-source',layout:{'line-cap':'round','line-join':'round'},paint:{'line-color':'#B33952','line-width':9,'line-blur':0.5,'line-opacity':0.72}});
    ensureLayer(map,{id:'v13-risk-segment-core',type:'line',source:'risk-leg-source',layout:{'line-cap':'round','line-join':'round'},paint:{'line-color':'#FFFFFF','line-width':1.6,'line-dasharray':[2,2],'line-opacity':0.88}});
    ensureLayer(map,{id:'route-focus-glow',type:'line',source:'route-active',layout:{'line-cap':'round','line-join':'round'},paint:{'line-color':['get','color'],'line-width':11,'line-blur':1.5,'line-opacity':0}});
    ensureLayer(map,{id:'traffic-change-ring',type:'circle',source:'traffic-changes',
      paint:{'circle-color':'#f17d51','circle-radius':['interpolate',['linear'],['zoom'],10,8,15,16],
        'circle-opacity':0.20,'circle-stroke-color':'#ee684f','circle-stroke-width':2.2,'circle-stroke-opacity':0.82}});
    ensureLayer(map,{id:'traffic-density',type:'heatmap',source:'traffic-density-source',paint:{
      'heatmap-weight':['match',['get','level'],3,1,2,0.7,1,0.35,0,0.15,0.1],
      'heatmap-intensity':['interpolate',['linear'],['zoom'],9,0.6,14,2.4],
      'heatmap-radius':['interpolate',['linear'],['zoom'],9,10,14,33],
      'heatmap-opacity':0.72,
      'heatmap-color':['interpolate',['linear'],['heatmap-density'],0,'rgba(0,0,0,0)',0.15,'#3bbbba',0.35,'#d5e77a',0.6,'#efad4e',0.83,'#ec6845',1,'#c83b5d']
    }});
    ensureLayer(map,{id:'traffic-clusters',type:'circle',source:'traffic-source',filter:['has','point_count'],paint:{'circle-color':theme==='light'?'#207f66':'#12584f','circle-radius':['step',['get','point_count'],16,20,20,70,25],'circle-stroke-color':theme==='light'?'#ffffff':'#78e8c4','circle-stroke-width':2,'circle-opacity':0.91}});
    ensureLayer(map,{id:'traffic-cluster-count',type:'symbol',source:'traffic-source',filter:['has','point_count'],layout:{'text-font':['Noto Sans Regular'],'text-field':['get','point_count_abbreviated'],'text-size':12},paint:{'text-color':'#ffffff'}});
    ensureLayer(map,{id:'camera-clusters',type:'circle',source:'camera-source',filter:['has','point_count'],paint:{'circle-color':'#0C8EBC','circle-radius':['step',['get','point_count'],16,20,20,60,26],'circle-stroke-color':'#e9f9ff','circle-stroke-width':2}});
    ensureLayer(map,{id:'camera-cluster-count',type:'symbol',source:'camera-source',filter:['has','point_count'],layout:{'text-font':['Noto Sans Regular'],'text-field':['get','point_count_abbreviated'],'text-size':12},paint:{'text-color':'#ffffff'}});
    ensureLayer(map,{id:'traffic-sensors-glow',type:'circle',source:'traffic-source',filter:['!', ['has','point_count']],paint:{'circle-color':['match',['get','level'],0,'#129869',1,'#6157D9',2,'#B000E6',3,'#E91D64','#657888'],'circle-radius':9,'circle-blur':0.85,'circle-opacity':0.21}});
    ensureLayer(map,{id:'traffic-sensors',type:'circle',source:'traffic-source',filter:['!', ['has','point_count']],paint:{'circle-color':['match',['get','level'],0,'#129869',1,'#6157D9',2,'#B000E6',3,'#E91D64','#657888'],'circle-radius':6.1,'circle-stroke-width':1.3,'circle-stroke-color':theme==='light'?'#ffffff':'#0d1b25','circle-opacity':0.89}});
    ensureLayer(map,{id:'evidence-fill',type:'fill',source:'evidence-radius',paint:{'fill-color':'#22aa8c','fill-opacity':0.085}});
    ensureLayer(map,{id:'evidence-boundary',type:'line',source:'evidence-radius',paint:{'line-color':'#1aab91','line-width':2,'line-dasharray':[3,2],'line-opacity':0.85}});
    ensureLayer(map,{id:'evidence-edges',type:'line',source:'evidence-links',paint:{'line-color':['match',['get','kind'],'camera','#35a8d8','#24bc92'],'line-width':1.9,'line-dasharray':[3,2],'line-opacity':0.8}});
    ensureLayer(map,{id:'incident-halo',type:'circle',source:'incident-source',paint:{'circle-radius':['case',['==',['get','selected'],1],17,11],'circle-color':'#AE3654','circle-opacity':0.2,'circle-stroke-width':1,'circle-stroke-color':'#AE3654','circle-stroke-opacity':0.38}});
    ensureLayer(map,{id:'incident-dot',type:'circle',source:'incident-source',paint:{'circle-radius':['case',['==',['get','selected'],1],9,7],'circle-color':['case',['==',['get','avoided'],1],'#207C65',['match',['get','origin'],'synthetic','#6E4CA0','#B43350']],'circle-stroke-color':'#321F1B','circle-stroke-width':2.5}});
    ensureLayer(map,{id:'incident-icon',type:'symbol',source:'incident-source',layout:{'text-font':['Noto Sans Regular'],'text-field':['case',['==',['get','avoided'],1],'✓',['==',['get','origin'],'synthetic'],'S','!'],'text-size':13,'text-allow-overlap':true,'text-ignore-placement':true},paint:{'text-color':'#ffffff'}});
    ensureLayer(map,{id:'delivery-dot',type:'circle',source:'delivery-source',paint:{'circle-radius':5,'circle-color':'#F3F6F9','circle-stroke-width':2,'circle-stroke-color':'#243B4B'}});
    ensureLayer(map,{id:'zone-dot',type:'circle',source:'zone-source',paint:{'circle-radius':5,'circle-color':'#128C4E','circle-stroke-width':2,'circle-stroke-color':'#142619'}});
    ensureLayer(map,{id:'delivery-order',type:'symbol',source:'delivery-source',layout:{'text-font':['Noto Sans Regular'],'text-field':['to-string',['get','seq']],'text-size':11,'text-offset':[0,1.65],'text-anchor':'top','text-allow-overlap':false},paint:{'text-color':theme==='light'?'#135342':'#E6FBE6','text-halo-color':theme==='light'?'#ffffff':'#07151d','text-halo-width':2}});
    ensureLayer(map,{id:'camera-dot',type:'circle',source:'camera-source',filter:['!', ['has','point_count']],paint:{'circle-radius':5,'circle-color':'#60C9FD','circle-stroke-width':2,'circle-stroke-color':'#123544'}});
    ensureLayer(map,{id:'camera-icon',type:'symbol',source:'camera-source',filter:['!', ['has','point_count']],layout:{'text-font':['Noto Sans Regular'],'text-field':'C','text-size':11,'text-allow-overlap':true},paint:{'text-color':'#ffffff'}});
    ensureLayer(map,{id:'loading-icon',type:'symbol',source:'zone-source',layout:{'text-font':['Noto Sans Regular'],'text-field':'P','text-size':11,'text-allow-overlap':true},paint:{'text-color':'#ffffff'}});
    ensureLayer(map,{id:'sensor-icon',type:'symbol',source:'traffic-source',filter:['!', ['has','point_count']],layout:{'text-font':['Noto Sans Regular'],'text-field':'T','text-size':11,'text-allow-overlap':true},paint:{'text-color':'#ffffff'}});
    ensureLayer(map,{id:'vehicle-halos',type:'circle',source:'vehicle-source',paint:{'circle-radius':['case',['==',['get','selected'],1],18,13],'circle-color':['get','color'],'circle-opacity':0.25,'circle-stroke-color':['get','color'],'circle-stroke-width':1.4}});
    ensureLayer(map,{id:'vehicle-centers',type:'circle',source:'vehicle-source',paint:{'circle-radius':6,'circle-color':['get','color'],'circle-stroke-color':'#101924','circle-stroke-width':1.6}});
    ensureLayer(map,{id:'playback-halo',type:'circle',source:'playback-source',paint:{'circle-radius':14,'circle-color':['get','color'],'circle-opacity':0.2,'circle-stroke-color':['get','color'],'circle-stroke-width':1.5}});
    ensureLayer(map,{id:'playback-vehicle',type:'circle',source:'playback-source',paint:{'circle-radius':6.5,'circle-color':['get','color'],'circle-stroke-color':theme==='light'?'#ffffff':'#0f1d26','circle-stroke-width':2.5}});
    ensureLayer(map,{id:'incident-label',type:'symbol',source:'incident-source',minzoom:11,filter:['==',['get','selected'],1],layout:{'text-font':['Noto Sans Regular'],'text-field':['get','title'],'text-size':10,'text-offset':[0,1.4],'text-anchor':'top','text-max-width':10,'text-allow-overlap':false,'text-optional':true},paint:{'text-color':theme==='light'?'#63392a':'#F4D9C9','text-halo-color':theme==='light'?'#ffffff':'#17232B','text-halo-width':2}});
    for(const [layerId,vis] of [['delivery-order',layers.deliveries&&Boolean(selectedVehicle)],['incident-dot',layers.incidents],['incident-icon',layers.incidents],['incident-halo',layers.incidents],['incident-label',layers.incidents],['delivery-dot',layers.deliveries],['zone-dot',layers.loading],['loading-icon',layers.loading],['camera-dot',layers.cameras],['camera-icon',layers.cameras],['sensor-icon',layers.traffic&&!densityView],['traffic-sensors',layers.traffic&&!densityView],['traffic-sensors-glow',layers.traffic&&!densityView],['traffic-clusters',layers.traffic&&!densityView],['traffic-cluster-count',layers.traffic&&!densityView],['traffic-density',layers.traffic&&densityView],['camera-clusters',layers.cameras],['camera-cluster-count',layers.cameras]] as [string,boolean][])map.setLayoutProperty(layerId,'visibility',vis?'visible':'none');
    const incidentSelection: any = layers.incidents ? null : ['==',['get','selected'],1];
    for(const incidentLayer of ['incident-dot','incident-halo','incident-icon'])map.setFilter(incidentLayer,incidentSelection);
    map.setFilter('incident-label',['==',['get','selected'],1]);
    map.setLayoutProperty('incident-dot','visibility',layers.incidents||!!selectedIncident||highlightIncidentIds.length>0?'visible':'none');
    map.setLayoutProperty('incident-icon','visibility',layers.incidents||!!selectedIncident||highlightIncidentIds.length>0?'visible':'none');
    map.setLayoutProperty('incident-halo','visibility',layers.incidents||!!selectedIncident||highlightIncidentIds.length>0?'visible':'none');
    map.setLayoutProperty('incident-label','visibility',!!selectedIncident||highlightIncidentIds.length>0?'visible':'none');
    map.setFilter('route-baseline-stroke',selectedVehicle?['==',['get','id'],selectedVehicle]:null);
    map.setFilter('route-shadow',isolatedVehicle&&selectedVehicle?['==',['get','id'],selectedVehicle]:null);
    map.setFilter('route-baseline-ghost',['==',['get','id'],'__none__']);
    map.setPaintProperty('route-baseline-ghost','line-opacity',0);
    map.setPaintProperty('route-baseline-stroke','line-opacity',signalMode?0:(compare?Math.min(1,2*(100-comparisonMix)/100):0));
    map.setFilter('playback-vehicle',selectedVehicle?['==',['get','id'],selectedVehicle]:null);
    map.setFilter('playback-halo',selectedVehicle?['==',['get','id'],selectedVehicle]:null);
    map.setPaintProperty('route-focus-glow','line-opacity',signalMode?0:(selectedVehicle?(compare?0.25*comparisonMix/100:0.25):0));
    map.setFilter('route-focus-glow',selectedVehicle?['==',['get','id'],selectedVehicle]:['==',['get','id'],'__none__']);
    for(const id of ['route-shadow','route-active-stroke','vehicle-halos','vehicle-centers','playback-halo','playback-vehicle','delivery-dot'])map.setLayoutProperty(id,'visibility',signalMode?'none':'visible');
    for(const id of ['vehicle-halos','vehicle-centers'])map.setFilter(id,isolatedVehicle&&selectedVehicle?['==',['get','id'],selectedVehicle]:null);
    map.setFilter('delivery-dot',isolatedVehicle&&selectedVehicle?['==',['get','vehicle'],selectedVehicle]:null);
    map.setPaintProperty('route-shadow','line-opacity',compare?0.24*Math.min(1,2*comparisonMix/100):(isolatedVehicle?0.38:(selectedVehicle?0.36:0.4)));
    map.setPaintProperty('route-active-stroke','line-opacity',
      selectedVehicle?['case',['==',['get','id'],selectedVehicle],compare?Math.min(1,2*comparisonMix/100):1,isolatedVehicle?0:0.07]:(compare?Math.min(1,2*comparisonMix/100):.97));
    for(const riskLayer of ['route-incident-proximity','v13-risk-segment-core'])map.setLayoutProperty(riskLayer,'visibility',!signalMode&&(!!selectedIncident||highlightIncidentIds.length>0)&&nearRoadSegments.length>0&&(!compare||comparisonMix>0)?'visible':'none');
    map.setPaintProperty('route-active-stroke','line-width',selectedVehicle?['case',['==',['get','id'],selectedVehicle],8,2]:6.7);
    map.setPaintProperty('route-active-stroke','line-offset',compare?-2.5:0);
    if(map.getLayer('delivery-order'))map.setFilter('delivery-order',selectedVehicle?['==',['get','vehicle'],selectedVehicle]:['==',['get','vehicle'],'__none__']);
  }catch(ex){console.warn('Map layer update failed',ex);}
 },[ready,snapshot,activePlan,layers,selectedIncident,selectedVehicle,compare,referencePlan,isolatedVehicle,traffic,signalMode,theme,densityView,evidence,changes,changeHighlights,comparisonMix,highlightIncidentIds,avoidedIncidentIds,focusSensorIds]);
 // This is a citywide sensor layer, not a route. Reframe the actual observed bounds.
 useEffect(()=>{
   const map=mapRef.current;
   if(!ready||!signalMode||!map||!traffic?.points.length||hasFittedSensorGrid.current)return;
   hasFittedSensorGrid.current=true;
   // Fit the dense urban core, not a handful of outlier sensors in the region.
   // Clipped bounds are only a camera viewport decision; all real points remain in data.
   const lons=traffic.points.map(p=>p.location[0]).sort((a,b)=>a-b);
   const lats=traffic.points.map(p=>p.location[1]).sort((a,b)=>a-b);
   const at=(items:number[],q:number)=>items[Math.min(items.length-1,Math.floor((items.length-1)*q))];
   const bounds=new maplibregl.LngLatBounds([at(lons,.04),at(lats,.04)],[at(lons,.96),at(lats,.96)]);
   map.fitBounds(bounds,{padding:{top:78,bottom:70,left:67,right:67},maxZoom:13.2,duration:750});
 },[ready,signalMode,traffic]);
 useEffect(()=>{
   if(!ready||!cameraFocusId){setChosenCamera(null);return;}
   const camera=snapshot.cameras.find(c=>c.id===cameraFocusId);
   if(!camera)return;
   setChosenCamera(camera);setImageError(false);setImageRefresh(Date.now());
   mapRef.current?.flyTo({center:camera.location,zoom:15.2,pitch:40,duration:850});
 },[cameraFocusId,ready,snapshot.cameras]);
 useEffect(()=>{
   if(!ready||!sensorFocusId)return;
   const sensor=traffic?.points.find(p=>p.id===sensorFocusId);
   if(!sensor)return;
   mapRef.current?.flyTo({center:sensor.location,zoom:16.4,pitch:40,duration:850});
   const div=document.createElement('div');div.className='v5SensorPopup';
   const name=document.createElement('strong');name.textContent=`Sensor #${sensor.id}`;
   const detail=document.createElement('span');detail.textContent=`Level ${sensor.service_level??'unknown'} · speed ${sensor.speed_kmh??'not reported'} km/h · occupancy ${sensor.occupancy_pct??'not reported'}%`;
   div.append(name,detail);new maplibregl.Popup({maxWidth:'270px'}).setLngLat(sensor.location).setDOMContent(div).addTo(mapRef.current!);
 },[sensorFocusId,ready,traffic]);
 const updatePlayback=useCallback((fraction:number)=>{
   progressRef.current=fraction;
   const map=mapRef.current;
   if(!map || !ready)return;
   const positions=activePlan.routes.filter(r=>r.fidelity==='road_network').map(r=>pointFeature(alongRoute(r.coordinates,fraction),{id:r.vehicle_id,color:r.color}));
   (map.getSource('playback-source') as GeoJSONSource|undefined)?.setData(fc(positions));
 },[ready,activePlan]);
 useEffect(()=>{
   if(!ready)return;
   updatePlayback(0);setPlaybackProgress(0);setPlaying(false);
 },[ready,activePlan.id,updatePlayback]);
 useEffect(()=>{
   if(!playing || !ready)return;
   let raf=0;let previous=0;
   const tick=(now:number)=>{
     if(previous===0)previous=now;
     const elapsed=Math.min(now-previous,100);previous=now;
     const fraction=Math.min(1,progressRef.current+elapsed/30000);
     updatePlayback(fraction);
     setPlaybackProgress(fraction);
     // Cinematic camera follow is a SIMULATION on road geometries, never GPS.
     if(followReplay && now-lastFollowCameraAt.current>550){
       const route=activePlan.routes.find(r=>r.vehicle_id===selectedVehicle)||activePlan.routes[0];
       if(route?.fidelity==='road_network'){
         const p=alongRoute(route.coordinates,fraction);
         mapRef.current?.easeTo({center:p,zoom:Math.max(14.6,mapRef.current?.getZoom()||14),pitch:48,duration:520,essential:false});
       }
       lastFollowCameraAt.current=now;
     }
     if(fraction<1)raf=requestAnimationFrame(tick);
     else setPlaying(false);
   };
   raf=requestAnimationFrame(tick);
   return ()=>cancelAnimationFrame(raf);
 },[playing,ready,updatePlayback]);
 const flyToIncident=(incident:Incident)=>mapRef.current?.flyTo({center:incident.location,zoom:14.7,duration:900});
 // The selection-aware effect above is the ONLY place that fits route geometry.
 // An identical plan object returned by polling must not recenter the map.
 const lastIncidentFocusRef=useRef<string|null>(null);
 useEffect(()=>{
   if(!ready || !selectedIncident){lastIncidentFocusRef.current=null;return;}
   if(lastIncidentFocusRef.current===selectedIncident)return;
   const incident=snapshot.incidents.find(x=>x.id===selectedIncident);
   if(incident){lastIncidentFocusRef.current=selectedIncident;flyToIncident(incident);}
 },[selectedIncident,ready,snapshot]);
 return <div className={`mapShell ${comparisonUi?'v15MapShellClean':''}`}>
  <div className="mapSurface" ref={ref}/>
  {error&&<div className="mapError">Map tiles could not load. Check your connection; mission data remains available.</div>}
  {!comparisonUi&&<div className="mapTopLeft"><span className="mapEyebrow"><span className="signalPing"/> MADRID METROPOLITAN</span><strong>{intelMode?'Incident evidence lens':signalMode?'Traffic measurement grid':'Operational footprint'}</strong><span className="mapCount">{intelMode?'Proximity only · no inferred travel times':signalMode?`${traffic?.points.length||0} verified sensor locations`:`${snapshot.incidents.length} mapped events · ${snapshot.deliveries.length} stops`}</span></div>}
  {!signalMode&&comparisonUi&&!hasRoadGeometries&&<div className="v12AwaitingRoads"><span>STREET-FIRST MODE</span><strong>Route geometry pending</strong><p>Stops are displayed without artificial straight-line connectors. Configure OSRM or ORS and generate a street plan to see both drivable geometries.</p></div>}

  {!comparisonUi&&<div className="mapTopRight">{signalMode&&changes?.available&&<button title="Toggle highlighted sensor deterioration between official downloads" className={`mapIconBtn v9DeltaToggle ${changeHighlights?'active':''}`} onClick={()=>setChangeHighlights(x=>!x)}><span aria-hidden="true">Δ</span> {changes.worsened} changed</button>}{signalMode&&layers.traffic&&<button title={densityView?'Show sensor markers':'Show observed point density'} className="mapIconBtn v6MapModeBtn" onClick={()=>setDensityView(x=>!x)}><Layers size={14}/>{densityView?'Density':'Points'}</button>}<span className="mapStatus"><span className="liveDot"/> {signalMode?(!layers.traffic&&layers.cameras?'MUNICIPAL CAMERAS':traffic?.status==='municipal_open_data'?'MUNICIPAL READINGS':'NO LIVE READINGS'):(snapshot.incidents.some(i=>i.provenance.origin==='municipal_open_data')?'MUNICIPAL INCIDENTS':'REPLAY / SYNTHETIC')}</span><button title={buildings3D?'Hide building extrusions':'Show 3D buildings (zoom 15+)'} className={`mapIconBtn v8BuildingToggle ${buildings3D?'active':''}`} onClick={()=>setBuildings3D(x=>!x)}><Building2 size={15}/></button><button title={terrain?'Flat map':'Tilt map / 3D view'} className="mapIconBtn" onClick={()=>{const newTilt=!terrain;setTerrain(newTilt);mapRef.current?.easeTo({pitch:newTilt?59:0,bearing:newTilt?-22:0,duration:800});}}><Mountain size={15}/></button><button title="Center Madrid" className="mapIconBtn" onClick={()=>mapRef.current?.flyTo({center:[-3.6995,40.4205],zoom:12.8,pitch:20,bearing:-12})}><LocateFixed size={15}/></button></div>}
  {!signalMode&&!comparisonUi&&inspectorOpen&&hasRoadGeometries&&selectedVehicle&&activePlan.routes.some(r=>r.vehicle_id===selectedVehicle)&&<div className="v12RouteInspector">
    {activePlan.routes.filter(r=>r.vehicle_id===selectedVehicle).map(route=><div key={route.vehicle_id}>
      <div className="v12RouteInspectorTop"><span style={{background:route.color}}/><strong>{route.vehicle_id} · STREET ROUTE</strong><button title="Close inspector (keep route selection)" onClick={()=>setInspectorOpen(false)}><X size={14}/></button></div>
      <div className="v12RouteInspectorStats"><div><b>{route.distance_km.toFixed(1)}</b><small>road km</small></div><div><b>{route.estimated_minutes.toFixed(0)}</b><small>base min</small></div><div><b>{route.stop_ids.length}</b><small>stops</small></div></div>
      <div className="v12RouteInspectorFooter"><span>{route.incidents_near.length?`${route.incidents_near.length} municipal incident(s) within indicative corridor`:'No mapped incidents within indicative corridor'}</span><small>Proximity ≠ verified closure · not live ETA</small></div>
    </div>)}
  </div>}
  {buildingsError&&<div className='v8BuildingNotice' role='status'>3D tiles unavailable; map remains usable.</div>}
  {chosenCamera&&<div className="v6CameraDock" role="region" aria-label="Municipal traffic camera snapshot">
    <div className="v6CameraDockTop"><div><span><CameraIcon size={14}/> MADRID OPEN DATA · STILL IMAGE</span><strong>{chosenCamera.label}</strong></div><button onClick={()=>{setChosenCamera(null);onCloseCamera?.();}} title="Close camera" aria-label="Close camera"><X size={17}/></button></div>
    <div className="v6CameraImage">
      {chosenCamera.image_url&&!imageError?<img key={`${chosenCamera.id}-${imageRefresh}`} src={api.cameraImageUrl(chosenCamera.id,imageRefresh)} alt={`Latest municipal still image: ${chosenCamera.label}`} onError={()=>setImageError(true)}/>:<div className="v6ImageUnavailable"><CameraIcon size={23}/><strong>Still image unavailable</strong><span>{chosenCamera.image_url?'The source did not return a valid JPEG/PNG.':'This KML record has no supported image link.'}</span></div>}
    </div><div className="v6CameraDockFooter"><span>Periodic still frame (auto refresh ~5 min). Not video. Timestamp is embedded by source when available.</span><button onClick={()=>{setImageError(false);setImageRefresh(Date.now());}}><RefreshCcw size={14}/> Refresh</button></div>
  </div>}
  {comparisonUi&&<div className="v17MapLegend" aria-label="Map symbols legend"><button type="button" aria-expanded={legendOpen} onClick={()=>setLegendOpen(v=>!v)}>{legendOpen?'Hide legend':'Map legend'} <span aria-hidden="true">{legendOpen?'−':'+'}</span></button>{legendOpen&&<div><span>▬ Routes</span><span>! Municipal notice</span><span>S Synthetic</span><span>C Camera</span><span>P Loading</span><span>T Sensor</span></div>}</div>}
  {comparisonUi&&<button type="button" className="v17WheelZoom" onClick={()=>setWheelZoom(v=>!v)} title="Alternar zoom con rueda" aria-pressed={wheelZoom}>{wheelZoom?'Rueda: zoom':'Rueda: desplazar'}</button>}
  {!signalMode&&hasRoadGeometries&&<div className={`v3PlaybackBar ${comparisonUi?'v15ReplayMinimal':''}`} aria-label="Simulated route playback">
    <button aria-label={playing?'Pause simulation':'Play simulation'} title={playing?'Pause':'Play simulated vehicles'} onClick={()=>{
      if(!playing&&progressRef.current>=1){updatePlayback(0);setPlaybackProgress(0);}
      setPlaying(v=>!v);
    }}>{playing?<Pause size={15}/>:<Play size={15}/>}</button>
    <div className="v3PlaybackBody"><strong>Fleet replay</strong><small>Simulation · not GPS live data</small></div>
    <button title={followReplay?'Stop following simulated route':'Follow the simulated van along real streets'} aria-pressed={followReplay} className={followReplay?'v12Following':''} onClick={()=>setFollowReplay(v=>!v)}><LocateFixed size={14}/></button>
    <input aria-label="Simulation timeline" type="range" min="0" max="100" step="1" value={Math.round(playbackProgress*100)} onChange={event=>{setPlaying(false);const fraction=Number(event.target.value)/100;updatePlayback(fraction);setPlaybackProgress(fraction);}}/>
    <button aria-label="Restart simulation" title="Restart simulation" onClick={()=>{setPlaying(false);updatePlayback(0);setPlaybackProgress(0);}}><RotateCcw size={14}/></button>
  </div>}
  {!comparisonUi&&<div className="mapBottomLeft"><span>WGS84 / MADRID · {theme.toUpperCase()} BASEMAP</span><span className="mapFidelity">{hasRoadGeometries?'STREET GEOMETRY':'AWAITING STREET ROUTES'}</span></div>}
  {selectedIncident&&!signalMode&&!comparisonUi&&<div className="v13MapRiskLegend"><span className="v13MapRiskDot"/> <strong>Proximity to selected notice</strong><small>Nearby geometry only · no verified blocked road</small></div>}
  {!comparisonUi&&<div className="mapKey">{signalMode&&!layers.traffic&&layers.cameras?<><span><i style={{background:'#60C9FD'}}/> Municipal camera</span></>:signalMode?<><span><i style={{background:'#2CBA86'}}/> Free</span><span><i style={{background:'#E7B444'}}/> Slow</span><span><i style={{background:'#EE8646'}}/> Queues</span><span><i style={{background:'#E75963'}}/> Congested</span></>:<><span><i style={{background:'#2ADBC2'}}/> Fleet routes</span><span><i style={{background:'#FF7B51'}}/> Traffic event</span><span><i style={{background:'#BFF178'}}/> Loading bay</span></>}</div>}
 </div>;
}
