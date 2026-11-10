'use client';
import {useMemo,useState} from 'react';
import {Activity,ArrowRight,AlertTriangle,BarChart3,CheckCircle2,Clock3,Database,ExternalLink,Filter,LoaderCircle,MapPinned,Radio,RefreshCw,Search,ShieldCheck,SlidersHorizontal,TrafficCone,Camera as CameraIcon,VideoOff} from 'lucide-react';
import type {CitySignals as Signals, MissionSnapshot,TrafficSensor,CityChanges} from '@/lib/types';
import type {ReactNode} from 'react';

const LEVELS=[
  {key:0,name:'Free flowing',color:'#29bd92'},
  {key:1,name:'Slow',color:'#e8bd52'},
  {key:2,name:'Queues',color:'#f78a4c'},
  {key:3,name:'Congested',color:'#ee6268'},
] as const;

type Props={signals:Signals|null;changes:CityChanges|null;autoRefresh:boolean;onAutoRefresh:(on:boolean)=>void;mission:MissionSnapshot;loading:boolean;refresh:()=>void;onMap:()=>void;map:ReactNode;report:Record<string,{ok:boolean;count?:number;error?:string}>|null;onCameraFocus:(id:string)=>void;onCameras:()=>void;onSensorFocus:(id:string)=>void};
const n=(x:number)=>x.toLocaleString('en-GB',{maximumFractionDigits:1});
export default function CitySignals({signals,changes,autoRefresh,onAutoRefresh,mission,loading,refresh,onMap,map,report,onCameraFocus,onCameras,onSensorFocus}:Props){
  const [filter,setFilter]=useState<'all'|'congested'|'delayed'>('all');
  const [query,setQuery]=useState('');
  const [cameraSearch,setCameraSearch]=useState('');
  const hasMeasurements=signals?.status==='municipal_open_data'&&Boolean(signals.points.length);
  const observations=signals?.points||[];
  const filtered=useMemo(()=>observations.filter(point=>{
    if(filter==='congested'&&point.service_level!==3)return false;
    if(filter==='delayed'&&!(point.service_level===2||point.service_level===3))return false;
    return !query||`${point.id} ${point.road_name||''}`.toLowerCase().includes(query.toLowerCase());
  }).sort((a,b)=>(b.service_level??-1)-(a.service_level??-1)).slice(0,30),[observations,filter,query]);
  const cameras=mission.cameras.filter(c=>c.provenance.origin==='municipal_open_data');
  const supportedCameras=cameras.filter(c=>Boolean(c.image_url));
  const visibleCameras=cameras.filter(c=>`${c.id} ${c.label}`.toLowerCase().includes(cameraSearch.toLowerCase())).slice(0,5);
  const withLevel=observations.filter(x=>x.service_level!==null);
  const speeds=observations.filter(x=>x.speed_kmh!==null).map(x=>x.speed_kmh!);
  const meanSpeed=speeds.length?speeds.reduce((a,b)=>a+b,0)/speeds.length:null;
  const count=(level:number)=>observations.filter(x=>x.service_level===level).length;
  const labelFor=(s:TrafficSensor)=>LEVELS.find(x=>x.key===s.service_level)||{name:'Not classified',color:'#839eaa'};
  const updated=signals?.fetched_at?new Date(signals.fetched_at).toLocaleString('es-ES',{dateStyle:'medium',timeStyle:'short',timeZone:'Europe/Madrid'}):null;
  return <div className="v5SignalsPage">
    <div className="v2PageIntro v2CompactIntro v5SignalIntro">
      <div><div className="v2Kicker"><span className="v5Beacon"/> CITY INTELLIGENCE / MADRID</div><h1>Madrid traffic readings</h1><p>Inspect the latest downloaded measurements and compare readings across two snapshots.</p></div>
      <div className="v5SignalActions"><span className={`v5DataBadge ${hasMeasurements?'online':'pending'}`}><span className="v5DataDot"/>{hasMeasurements?'MUNICIPAL DATA LOADED':'NO SENSOR SNAPSHOT'}</span><label className="v9AutoRefresh" title="Fetch city sources once every five minutes while this page is open, shared by the API backend"><input type="checkbox" checked={autoRefresh} onChange={e=>onAutoRefresh(e.target.checked)}/><span>Auto · 5 min</span></label><button className="v2Primary" onClick={refresh} disabled={loading}><RefreshCw className={loading?'v2Spin':''} size={16}/>{loading?'Fetching sources':'Fetch city sources'}</button></div>
    </div>
    <div className="v5SignalMetrics">
      <div className="v5SignalMetric"><div><Database size={17}/> MUNICIPAL SENSORS</div><strong>{hasMeasurements?n(signals!.total_valid):'—'}</strong><span>{hasMeasurements?`${n(observations.length)} displayed (sampled)`: 'Not loaded'}</span></div>
      <div className="v5SignalMetric"><div><TrafficCone size={17}/> CONGESTION POINTS</div><strong className="v5WarmNumber">{hasMeasurements?n(count(3)):'—'}</strong><span>Level 3 · among mapped sensors</span></div>
      <div className="v5SignalMetric"><div><Activity size={17}/> OBSERVED SPEED</div><strong>{meanSpeed!==null?`${n(meanSpeed)} km/h`:'—'}</strong><span>Average of valid point readings</span></div>
      <div className="v5SignalMetric"><div><Clock3 size={17}/> LAST DOWNLOAD</div><strong className="v5SmallValue">{updated||'Not available'}</strong><span>Madrid time · observation times may differ</span></div>
    </div>
    <div className="v5SignalsGrid">
      <section className="v2Panel v5SignalMapPanel">
        <div className="v2PanelHeading"><div><span className="v2Eyebrow">OBSERVATION LAYER / WGS84</span><h2>Madrid sensor network</h2></div><span className="v5MapLegend"><i/> Actual points only</span></div>
        <div className="v5SignalMapStage">{map}{!hasMeasurements&&<div className="v5SignalMapEmpty"><Radio size={22}/><strong>Awaiting municipal data</strong><span>Fetch the municipal feed to see measured traffic at individual sensors.</span><button onClick={refresh} disabled={loading}>Fetch sensor data <ArrowRight size={14}/></button></div>}</div>
        <div className="v5SignalMapFooter"><span><ShieldCheck size={14}/> Ayuntamiento de Madrid · CC BY 4.0</span><button className="v2TextLink" onClick={onMap}>Fleet operations map <ArrowRight size={14}/></button></div>
      </section>
      <aside className="v5SignalsSide">
        <section className="v2Panel v5DensityPanel"><div className="v2PanelHeading"><div><span className="v2Eyebrow">TRAFFIC HEALTH</span><h2>Service-level distribution</h2></div><BarChart3 size={17}/></div>
          {hasMeasurements&&withLevel.length? <div className="v5Distribution">{LEVELS.map(level=><div className="v5DistributionRow" key={level.key}><div><span><i style={{background:level.color}}/>{level.name}</span><strong>{count(level.key)}</strong></div><div className="v5DistributionTrack"><div style={{width:`${Math.max(0,count(level.key)/withLevel.length*100)}%`,background:level.color}}/></div></div>)}<p>Categories reported by the municipal sensors. Percentages exclude unknown readings.</p></div>:<div className="v5EmptyChart"><Activity size={26}/><p>Real distributions appear after a successful feed download.</p></div>}
        </section>
        <section className="v2Panel v9CityChangeCard">
          <div className="v2PanelHeading"><div><span className="v2Eyebrow">TWO-SNAPSHOT COMPARISON</span><h2>Changes between downloads</h2></div><Activity size={17}/></div>
          {changes?.available?<>
            <div className="v9ChangeCounters"><div><span>WORSENED</span><strong className="worse">{changes.worsened}</strong></div><div><span>IMPROVED</span><strong className="better">{changes.improved}</strong></div><div><span>COMPARED</span><strong>{changes.compared_sensor_count}</strong></div></div>
            <div className="v9ChangeRows">{changes.changed.slice(0,5).map(c=><button key={c.id} onClick={()=>onSensorFocus(c.id)} title={`Locate observed sensor ${c.id}`}><span className={c.delta>0?'worse':'better'}>{c.delta>0?'↑':'↓'}</span><span><strong>Sensor {c.id}</strong><small>{c.road_name||'Madrid road measurement'}</small></span><em>{c.previous_level} → {c.current_level}</em><ArrowRight size={13}/></button>)}</div>
            {!changes.changed.length&&<p className="v9ChangeHint">No service-level changes among matching sampled sensors.</p>}
            <p className="v9ChangeHint">Between {changes.previous_at?new Date(changes.previous_at).toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit'}):'—'} and {changes.current_at?new Date(changes.current_at).toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit'}):'—'} (download times). Not a prediction or a cause of delays.</p>
          </>:<div className="v9ChangesEmpty"><Activity size={19}/><strong>One more observation needed</strong><p>Load another official snapshot after five minutes to compare actual changes at the same sensor IDs. Nothing is simulated here.</p></div>}
        </section>
        <button className="v10CamerasCTA" onClick={onCameras}><CameraIcon size={21}/><span><strong>Explore municipal CCTV</strong><small>{cameras.length} real camera locations · latest still images on demand</small></span><ArrowRight size={17}/></button>
        <section className="v2Panel v5SourcesPanel"><div className="v2PanelHeading"><div><span className="v2Eyebrow">PROVENANCE / HEALTH</span><h2>Source diagnostics</h2></div><Database size={17}/></div>
          <div className="v5SourceRows">{mission.sources.map(s=><div key={s.id}><span className={`v5SourceLed ${s.connected?'is-on':''}`}/><div><strong>{s.name}</strong><small>{s.connected?`${n(s.count)} records · municipal`:'Unavailable or demo'}</small>{report?.[s.id]&&!report[s.id].ok&&<small className="v5Error">{report[s.id].error}</small>}</div>{s.connected?<CheckCircle2 size={15}/>:<Clock3 size={15}/>}</div>)}</div>
          <div className="v5SourceFooter"><span>{updated?`Last refresh: ${updated}`:'Source refresh is manual and rate-limited'}</span><a href="https://datos.madrid.es" target="_blank" rel="noreferrer">Official catalog <ExternalLink size={12}/></a></div>
        </section>
      </aside>
    </div>
    <section className="v2Panel v5SignalTable"><div className="v2PanelHeading"><div><span className="v2Eyebrow">OBSERVATION EXPLORER</span><h2>Traffic measurement points</h2></div><div className="v5TableTools"><label><Search size={15}/><input placeholder="Search sensor ID or road" aria-label="Search sensors" value={query} onChange={e=>setQuery(e.target.value)}/></label><select aria-label="Filter traffic sensors" value={filter} onChange={e=>setFilter(e.target.value as typeof filter)}><option value="all">All service levels</option><option value="delayed">Queues and congestion</option><option value="congested">Congested only</option></select></div></div>
      <div className="v5SensorScroll"><table><thead><tr><th>Sensor</th><th>Observed state</th><th>Intensity</th><th>Occupancy</th><th>Speed</th><th>Coordinates</th></tr></thead><tbody>{filtered.map(s=><tr key={s.id}><td><button className="v6SensorLocate" onClick={()=>onSensorFocus(s.id)} title={`Zoom to sensor ${s.id}`}><MapPinned size={13}/> #{s.id}</button><small>{s.road_name||'Municipal observation'}</small></td><td><span className="v5ServicePill"><i style={{background:labelFor(s).color}}/>{labelFor(s).name}</span></td><td>{s.intensity_vph!==null?`${n(s.intensity_vph)} veh/h`:'—'}</td><td>{s.occupancy_pct!==null?`${n(s.occupancy_pct)}%`:'—'}</td><td>{s.speed_kmh!==null?`${n(s.speed_kmh)} km/h`:'—'}</td><td className="v5Mono">{s.location.map(v=>v.toFixed(4)).join(', ')}</td></tr>)}{filtered.length===0&&<tr><td colSpan={6} className="v5NoRows">{hasMeasurements?'No sensors match these filters.':'No observed traffic measurements loaded. Click Fetch city sources above.'}</td></tr>}</tbody></table></div>
      <footer className="v5TableFoot"><span>{filtered.length} rows shown · {n(observations.length)} geolocated readings in view memory</span><span>No GPS tracking · No inferred driving times</span></footer>
    </section>
  </div>;
}
