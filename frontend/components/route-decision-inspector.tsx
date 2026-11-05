'use client';
import {useEffect,useState} from 'react';
import {ArrowRight,Clock3,ExternalLink,Info,MapPin,ShieldAlert,Truck,X} from 'lucide-react';
import {api} from '@/lib/api';
import type {ScenarioId,VehicleExplanation,RouteLegExplanation,RouteIncidentImpact,RouteTrafficReading} from '@/lib/types';

type Props={vehicleId:string|null;scenario:ScenarioId;planId:string|null;
 onClose:()=>void;onVehicle:(id:string)=>void;onIncident:(id:string)=>void;onAll:()=>void};
function pretty(from:string){return from==='DEPOT'?'Depot':from;}
const dist=(n:number)=>n.toFixed(1);
export default function RouteDecisionInspector({vehicleId,scenario,planId,onClose,onIncident,onAll}:Props){
 const [detail,setDetail]=useState<VehicleExplanation|null>(null);
 const [expandedLeg,setExpandedLeg]=useState<string|null>(null);
 const [failure,setFailure]=useState<string|null>(null);
 const [impact,setImpact]=useState<RouteIncidentImpact|null>(null);
 const [traffic,setTraffic]=useState<RouteTrafficReading|null>(null);
 const [trafficLoading,setTrafficLoading]=useState(false);
 useEffect(()=>{
   let alive=true;setDetail(null);setFailure(null);setExpandedLeg(null);setImpact(null);setTraffic(null);
   if(!vehicleId||!planId)return;
   void api.vehicleExplanation(vehicleId).then(data=>{
     if(alive&&data.plan_id===planId)setDetail(data);
   }).catch(error=>{if(alive)setFailure(String(error));});
   return ()=>{alive=false;};
 },[vehicleId,planId]);
 if(!vehicleId)return <div className="v14InspectorEmpty"><Truck size={22}/><h3>Decision explorer</h3><p>Select a route to inspect A, B and C. Double-click a route to isolate it on the map.</p><button onClick={onAll}>Show full fleet</button></div>;
 const a=detail?.scenarios.A,b=detail?.scenarios.B,c=detail?.scenarios.C;
 const current=detail?.scenarios[scenario];
 const legs=current?.legs||[];
 const candidates=Array.from(new Map(legs.flatMap(l=>l.nearby_incidents).map(i=>[i.id,i])).values());
 return <section className="v14Inspector" aria-label="Route decision inspector">
   <div className="v14InspectorHead"><div><span className="v2Eyebrow">EXPLAINABLE DISPATCH</span><h3>{vehicleId} · Route detail</h3></div><button aria-label="Close inspector without clearing selection" title="Close detail" onClick={onClose}><X size={16}/></button></div>
   <p className="v14InspectorHint">Click to focus · Double-click to isolate · No live GPS</p>
   {failure&&<p className="v14InspectorHint">Unable to load explanation: {failure}</p>}
   {(!detail||detail.plan_id!==planId)&&!failure&&<p className="v14InspectorHint">Fetching route decision evidence…</p>}
   <div className="v14ABCCards">{(['A','B','C'] as const).map(key=>{const row=detail?.scenarios[key];return <div key={key} className={scenario===key?'current':''}><span>{key==='A'?'A · Original':key==='B'?'B · No risk':'C · Risk-aware'}</span><strong>{row?`${dist(row.road_km)} km`:'—'}</strong><small>{row?`${dist(row.base_minutes)} base min`:'Not calculated'}</small></div>;})}</div>
   <div className="v14Insight"><Info size={15}/><div><strong>Why does the route differ?</strong><p>A→B: road-time delivery optimization. B→C: risk-sensitive selection or operator-requested hypothetical avoidance. No certified closures.</p>{b&&c&&<p>Compared with B, C {c.stop_ids.join('|')===b.stop_ids.join('|')?'keeps the same stops and order.':'changes the stop assignment or order.'}</p>}</div></div>
   {scenario==='C'&&current?.detour?.geometry_changed&&<div className="v15DetourEvidence"><strong>Street-network detour verified</strong><span>The requested risk buffer was avoided: {current.detour.incident_id} · provider-verified geometry. Extra base travel: {current.detour.extra_km?.toFixed(1)} km and {current.detour.extra_base_minutes?.toFixed(1)} base min. This is not evidence of a municipal street closure.</span></div>}
   {scenario==='C'&&current?.detour?.geometry_changed&&<p className="v14InspectorHint">Leg-level matrix details precede any waypoint detour; C totals above include the newly routed geometry.</p>}
   {current&&<div className="v14RouteStats"><span><Clock3 size={14}/> {dist(current.base_minutes)} base min</span><span><Truck size={14}/> {current.stop_ids.length} deliveries</span></div>}
   {current&&<div className="v14Stops"><strong>Stop sequence · {scenario}</strong><p>Depot → {current.stop_ids.join(' → ')} → Depot</p></div>}
   <div className="v14Subheading"><strong>Road legs</strong><small>Road-matrix distance and base minutes</small></div>
   {legs.length?legs.map((leg,index)=>{const key=`${leg.from_stop_id}-${leg.to_stop_id}-${index}`;return <div className="v14Leg" key={key}>
     <button className="v14LegTrigger" onClick={()=>setExpandedLeg(expandedLeg===key?null:key)} aria-expanded={expandedLeg===key}>
       <span>{index+1}. {pretty(leg.from_stop_id)} <ArrowRight size={12}/> {pretty(leg.to_stop_id)}</span><b>{leg.road_km.toFixed(2)} km</b>
     </button>
     {expandedLeg===key&&<div className="v14LegBody"><p>{leg.base_minutes.toFixed(1)} base min · modeled delivery lateness: {leg.modeled_late_minutes.toFixed(1)} min</p>
       <p>{leg.nearby_incidents.length?`${leg.nearby_incidents.length} notices close to the inspected road geometry`: 'No notices identified near this inspected geometry'}</p>
       {leg.nearby_incidents.map(i=><button key={i.id} onClick={()=>onIncident(i.id)}><MapPin size={13}/> {i.title} <ExternalLink size={12}/></button>)}
       <small>{leg.risk_applied?'Spatial-risk evidence was considered.':'No active incident penalty on this leg.'} No road edge is certified blocked.</small>
     </div>}
   </div>;}):<p className="v14InspectorHint">Leg details require a verified OSRM/ORS street plan.</p>}
   <div className="v14Subheading"><strong>Relevant notices</strong><small>{candidates.length} associated with legs</small></div>
   {candidates.length?candidates.map(item=><button key={item.id} className="v14IncidentItem" onClick={()=>{
      onIncident(item.id);
      void api.incidentRouteImpact(item.id).then(setImpact).catch(()=>setImpact(null));
   }}><MapPin size={14}/><span>{item.title}<small>{item.origin==='municipal_open_data'?'Municipal':'Synthetic'} · Not proof of closure</small></span><ArrowRight size={13}/></button>):<p className="v14InspectorHint">No risk penalties were applied to these scenario legs.</p>}
   {impact&&<div className="v14Insight"><ShieldAlert size={15}/><p>{impact.title}: {impact.affected_legs.length} C-plan legs near this notice. {impact.temporal_status==='active'?'Notice time window appears applicable.':'Temporal status: '+impact.temporal_status}. {impact.note} {impact.candidate_ablation&&(impact.candidate_ablation.selection_changed?'Removing this notice changes selection among examined candidates.':'Removing the notice does not change selection among examined candidates.')}</p></div>}
   <div className="v14TrafficPanel">
     <strong>Nearby municipal observations</strong>
     <button disabled={trafficLoading||!detail||!current||!current.has_leg_detail} onClick={()=>{
       if(!vehicleId)return;
       setTrafficLoading(true);
       void api.vehicleTraffic(vehicleId,scenario).then(setTraffic).catch(error=>setFailure(String(error))).finally(()=>setTrafficLoading(false));
     }}>{trafficLoading?'Checking sensors…':'Inspect volume, occupancy and speed'}</button>
     {traffic&&<>
       <p className="v14InspectorHint">{traffic.sampled_nearby_count} points near the route. Observation time: {traffic.observed_at||traffic.downloaded_at||'observation time not provided'}; congestion duration: unknown.</p>
       {traffic.observations.slice(0,6).map(point=><div className="v14TrafficReading" key={point.id}>
         <strong>{point.road_name||`Sensor ${point.id}`} · {point.distance_m} m</strong>
         <span>Speed: {point.speed_kmh??'N/A'} km/h · Occupancy: {point.occupancy_pct??'N/A'} % · Volume: {point.intensity_vph??'N/A'} veh/h</span>
         <small>Nearby point observation, not the proven speed along this route</small>
       </div>)}
     </>}
   </div>
   <p className="v14Disclaimer"><ShieldAlert size={15}/> Base street times only; no live route ETA. Municipal sensors are separate point observations. Official notices are not hard blocked edges.</p>
 </section>;
}
