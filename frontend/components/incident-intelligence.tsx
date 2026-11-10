'use client';
import {useEffect,useMemo,useState} from 'react';
import type {ReactNode} from 'react';
import {Activity,ArrowRight,BrainCircuit,Camera,CheckCircle2,ChevronRight,Clock3,Database,Download,Layers3,LoaderCircle,Radio,RefreshCw,ScanSearch,Search,ShieldAlert,Signal,Target,Truck,ZoomIn} from 'lucide-react';
import {api} from '@/lib/api';
import type {CitySignals,Incident,IncidentEvidence,MissionSnapshot,TrafficSensor} from '@/lib/types';

type Props={mission:MissionSnapshot;signals:CitySignals|null;selectedIncident:string|null;
  onSelectIncident:(id:string)=>void;onCameraFocus:(id:string)=>void;onAskAgent:(id:string)=>void;
  map:ReactNode;refresh:()=>void;refreshing:boolean;onEvidence:(value:IncidentEvidence|null)=>void};
const nf=(n:number)=>n.toLocaleString('es-ES');
const severity=(i:Incident)=>i.provenance.origin==='municipal_open_data'?'MUNICIPAL EVENT':i.severity==='high'?'HIGH (DEMO)':i.severity==='medium'?'MEDIUM (DEMO)':'LOW (DEMO)';
const sensorLabel=(level:number|null)=>level===3?'Congested':level===2?'Queues':level===1?'Slow':level===0?'Free flowing':'Unknown';
const sensorColor=(level:number|null)=>level===3?'#ec6572':level===2?'#eb914b':level===1?'#e0b84f':level===0?'#28b993':'#8eabb7';
const km=(m:number)=>m<1000?`${nf(m)} m`:`${(m/1000).toLocaleString('es-ES',{maximumFractionDigits:1})} km`;
const asDate=(date:string|null|undefined)=>date?new Date(date).toLocaleString('es-ES',{dateStyle:'short',timeStyle:'short'}):'Unknown';

export default function IncidentIntelligence({mission,signals,selectedIncident,onSelectIncident,onCameraFocus,onAskAgent,map,refresh,refreshing,onEvidence}:Props){
  const [radius,setRadius]=useState(800);
  const [filter,setFilter]=useState<'all'|'high'|'official'>('all');
  const [search,setSearch]=useState('');
  const [evidence,setEvidence]=useState<IncidentEvidence|null>(null);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState<string|null>(null);
  const allIncidents=mission.incidents;
  const candidates=useMemo(()=>allIncidents.filter(i=>
    (filter!=='high'||i.severity==='high')&&(filter!=='official'||i.provenance.origin==='municipal_open_data')&&
    (!search||`${i.title} ${i.id} ${i.detail}`.toLowerCase().includes(search.toLowerCase()))
  ).sort((a,b)=>({high:3,medium:2,low:1}[b.severity]-{high:3,medium:2,low:1}[a.severity])).slice(0,75),[allIncidents,filter,search]);
  const activeId=selectedIncident&&allIncidents.some(x=>x.id===selectedIncident)?selectedIncident:allIncidents[0]?.id;
  useEffect(()=>{if(!selectedIncident&&activeId)onSelectIncident(activeId);},[selectedIncident,activeId,onSelectIncident]);
  useEffect(()=>{
    if(!activeId){setEvidence(null);onEvidence(null);return;}
    let ignore=false;setLoading(true);setError(null);setEvidence(null);onEvidence(null);
    api.incidentEvidence(activeId,radius).then(data=>{if(!ignore){setEvidence(data);onEvidence(data);}})
      .catch(e=>{if(!ignore)setError(String(e));}).finally(()=>{if(!ignore)setLoading(false);});
    return ()=>{ignore=true;};
  },[activeId,radius,mission.generated_at,onEvidence]);
  const liveIncidents=allIncidents.filter(x=>x.provenance.origin==='municipal_open_data').length;
  const realCameras=mission.cameras.filter(x=>x.provenance.origin==='municipal_open_data').length;
  const sourceFidelity=mission.source_mode==='live'?'Municipal context + simulated fleet':'Reproducible demo';
  const exportEvidence=()=>{
    if(!evidence)return;
    const blob=new Blob([JSON.stringify({exported_at:new Date().toISOString(),
      interpretation:'Geographic proximity only; no demonstrated traffic causality',...evidence},null,2)],{type:'application/json'});
    const url=URL.createObjectURL(blob);const link=document.createElement('a');
    link.href=url;link.download=`curbops-evidence-${evidence.incident.id.replace(/[^a-zA-Z0-9-]/g,'')}.json`;
    link.click();URL.revokeObjectURL(url);
  };
  return <div className="v8IntelRoot">
    <header className="v8IntelHero">
      <div><div className="v2Kicker"><span className="v8Beacon"/> MADRID / INCIDENT INTELLIGENCE</div>
        <h1>Road notices and nearby evidence</h1>
        <p>Select a notice to see nearby sensors, cameras and loading bays. Distance alone does not establish a closure.</p>
      </div>
      <div className="v8IntelHeroActions"><span className="v8Provenance"><span/>{sourceFidelity}</span>
        <button className="v2Secondary" onClick={refresh} disabled={refreshing}>{refreshing?<LoaderCircle className="v2Spin" size={16}/>:<RefreshCw size={16}/>} Refresh sources</button></div>
    </header>
    <div className="v8IntelMetrics">
      <div><span><ShieldAlert size={16}/> MUNICIPAL INCIDENTS</span><strong>{nf(liveIncidents)}</strong><small>In the active scene</small></div>
      <div><span><Radio size={16}/> SENSOR OBSERVATIONS</span><strong>{nf(signals?.points.length||0)}</strong><small>Loaded subset; not all sensors</small></div>
      <div><span><Camera size={16}/> CAMERA POSITIONS</span><strong>{nf(realCameras)}</strong><small>Images may be unavailable</small></div>
      <div><span><Layers3 size={16}/> LOADING RESERVES</span><strong>{nf(mission.loading_zones.filter(x=>x.provenance.origin==='municipal_open_data').length)}</strong><small>Locations only; no occupancy</small></div>
    </div>
    <section className="v8IntelStage">
      <aside className="v8IntelList v2Panel">
        <div className="v8IntelColumnHeader"><span className="v2Eyebrow">01 / SELECT TARGET</span><strong>Urban incidents</strong><small>{nf(candidates.length)} shown</small></div>
        <label className="v8IntelSearch"><Search size={16}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Street, tunnel, event…" aria-label="Search incidents"/></label>
        <div className="v8IntelFilter"><button onClick={()=>setFilter('all')} className={filter==='all'?'on':''}>All</button><button onClick={()=>setFilter('high')} className={filter==='high'?'on':''}>High</button><button onClick={()=>setFilter('official')} className={filter==='official'?'on':''}>Official</button></div>
        <div className="v8IntelItems">{candidates.map(i=><button key={i.id} className={activeId===i.id?'selected':''} onClick={()=>onSelectIncident(i.id)}>
          <i className={`v8SeverityPin ${i.severity}`}/><span><strong>{i.title}</strong><small>{severity(i)} · {i.provenance.origin==='municipal_open_data'?'Municipal record':'Synthetic scenario'}</small></span><ChevronRight size={15}/>
        </button>)}{!candidates.length&&<div className="v8EmptySearch">No incidents match these filters.</div>}</div>
        <div className="v8IntelListFooter"><Database size={14}/> Data source is shown on every record. Municipal timestamps are not guaranteed to reflect current road restrictions.</div>
      </aside>
      <div className="v8IntelMapBlock v2Panel">
        <div className="v8IntelMapHeader"><div><span className="v2Eyebrow">02 / GEOSPATIAL EVIDENCE</span><strong>Evidence map</strong></div><span className="v8MapLive"><Target size={13}/> Proximity lens</span></div>
        <div className="v8IntelMapCanvas">{map}</div>
        <div className="v8IntelMapBottom"><div className="v8LegendItem"><i style={{background:'#f17656'}}/> Incident</div><div className="v8LegendItem"><i style={{background:'#29b98c'}}/> Sensors</div><div className="v8LegendItem"><i style={{background:'#46b8e2'}}/> Cameras</div><span>Distance ≠ causality</span></div>
      </div>
      <aside className="v8IntelEvidence v2Panel">
        <div className="v8IntelColumnHeader"><span className="v2Eyebrow">03 / INVESTIGATE CONTEXT</span><strong>Evidence inspector</strong><small>Bounded, read-only analysis</small></div>
        <div className="v8RadiusPicker"><span>Investigation radius</span><div>{[400,800,1500].map(m=><button key={m} className={radius===m?'on':''} onClick={()=>setRadius(m)}>{m>=1000?'1.5 km':m+' m'}</button>)}</div></div>
        {loading?<div className="v8EvidenceLoading"><LoaderCircle className="v2Spin" size={20}/><strong>Finding nearby sensors and cameras…</strong><span>Results are grouped by distance from the notice.</span></div>:
        error?<div className="v8EvidenceError">Evidence API unavailable: {error}</div>:
        evidence?<div className="v8EvidenceContent">
          <div className="v8SelectedIncident"><span className="v2Eyebrow">SELECTED INCIDENT</span><h3>{evidence.incident.title}</h3><span className="v8OriginTag">{evidence.incident.provenance.origin==='municipal_open_data'?'Official Madrid record':'Synthetic event'}</span><p>{evidence.incident.detail}</p></div>
          <div className="v8EvidenceCounts">
            <div><Radio size={16}/><strong>{evidence.sensor_count_nearby}</strong><span>Sensors</span></div>
            <div><Camera size={16}/><strong>{evidence.camera_count_nearby}</strong><span>Cameras</span></div>
            <div><Truck size={16}/><strong>{evidence.loading_zone_count_nearby}</strong><span>Loading bays</span></div>
          </div>
          <div className="v8EvidenceGroup"><div className="v8EvidenceGroupHead"><strong><Activity size={15}/> Traffic observations</strong><span>{evidence.congested_sensor_count} congested</span></div>
            {evidence.sensors.slice(0,4).map(s=><div className="v8EvidenceRow" key={s.id}><i style={{background:sensorColor(s.service_level)}}/><div><strong>Sensor #{s.id}</strong><small>{sensorLabel(s.service_level)} · {s.speed_kmh===null?'No speed':`${s.speed_kmh} km/h at point`}</small></div><em>{km(s.distance_m)}</em></div>)}
            {!evidence.sensors.length&&<p className="v8NoEvidence">No sensors in the loaded subset within this radius.</p>}
          </div>
          <div className="v8EvidenceGroup"><div className="v8EvidenceGroupHead"><strong><Camera size={15}/> Closest cameras</strong><span>Periodic stills</span></div>
            {evidence.cameras.slice(0,3).map(c=><button className="v8EvidenceRow link" key={c.id} onClick={()=>onCameraFocus(c.id)}><i style={{background:'#46b8e2'}}/><div><strong>{c.label}</strong><small>{c.image_url?'Open latest available image':'Location only'}</small></div><em>{km(c.distance_m)}</em><ArrowRight size={13}/></button>)}
            {!evidence.cameras.length&&<p className="v8NoEvidence">No cameras found within this radius.</p>}
          </div>
          <div className="v8EvidenceStamp"><Clock3 size={14}/> Sensor fetch: {asDate(evidence.fetched_at)}. Observation: {asDate(evidence.observed_at)}.</div>
          <button className="v8ExportEvidence" onClick={exportEvidence}><Download size={15}/> Export evidence + provenance <ArrowRight size={13}/></button>
          <button className="v8AskAgent" onClick={()=>onAskAgent(evidence.incident.id)}><BrainCircuit size={17}/><span><strong>Analyze with AI agent</strong><small>Inspect proximity tools and provenance</small></span><ArrowRight size={17}/></button>
        </div>:<div className="v8EvidenceEmpty"><ScanSearch size={22}/><span>Choose a city event to inspect its context.</span></div>}
      </aside>
    </section>
    <div className="v8ReasoningRibbon"><span><CheckCircle2 size={15}/> Read-only official datasets</span><ChevronRight size={14}/><span><ZoomIn size={15}/> Geospatial joins</span><ChevronRight size={14}/><span><Signal size={15}/> Verifiable evidence</span><ChevronRight size={14}/><span><BrainCircuit size={15}/> Agent investigation</span></div>
  </div>;
}
