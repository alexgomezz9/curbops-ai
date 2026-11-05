'use client';
import {useMemo,useState} from 'react';
import type {ReactNode} from 'react';
import {Camera,ChevronRight,MapPin,Search,Clock3,RefreshCw,ShieldCheck,VideoOff} from 'lucide-react';
import type {MissionSnapshot} from '@/lib/types';

type Props={mission:MissionSnapshot;focusId:string|null;onFocus:(id:string)=>void;onClose:()=>void;map:ReactNode;onRefresh:()=>void;refreshing:boolean};
export default function CameraHub({mission,focusId,onFocus,onClose,map,onRefresh,refreshing}:Props){
  const [query,setQuery]=useState('');const [availableOnly,setAvailableOnly]=useState(true);
  const cameras=mission.cameras.filter(c=>c.provenance.origin==='municipal_open_data');
  const visible=useMemo(()=>cameras.filter(c=>(!availableOnly||Boolean(c.image_url))&&`${c.label} ${c.id} ${c.location.join(' ')}`.toLowerCase().includes(query.toLowerCase())).slice(0,100),[cameras,availableOnly,query]);
  const selected=cameras.find(c=>c.id===focusId);
  return <div className="v10CamerasPage">
    <header className="v10CamerasHero"><div><span className="v2Kicker">CITY INTELLIGENCE / MADRID CCTV</span><h1>Street-level <em>eyes on the city.</em></h1><p>Browse municipal camera positions and manually open the latest periodic still image. No continuous video or traffic inference.</p></div><button className="v2Secondary" onClick={onRefresh} disabled={refreshing}><RefreshCw size={15} className={refreshing?'v2Spin':''}/> Refresh municipal catalog</button></header>
    <div className="v10CamerasKpis"><div><Camera size={17}/><strong>{cameras.length}</strong><span>Municipal camera positions</span></div><div><ShieldCheck size={17}/><strong>{cameras.filter(c=>c.image_url).length}</strong><span>Images linked in catalog</span></div><div><Clock3 size={17}/><strong>~5 min</strong><span>Typical still-frame update; not guaranteed</span></div></div>
    <div className="v10CamerasWorkspace"><aside className="v2Panel v10CameraSidebar"><div className="v10CameraSidebarTop"><span className="v2Eyebrow">CAMERA EXPLORER</span><h2>Municipal network</h2><label><Search size={15}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search camera / street"/></label><label className="v10CameraCheckbox"><input type="checkbox" checked={availableOnly} onChange={e=>setAvailableOnly(e.target.checked)}/> With still-image URL</label><small>{visible.length} displayed · click to focus</small></div><div className="v10CameraResults">{visible.map(camera=><button className={focusId===camera.id?'active':''} key={camera.id} onClick={()=>onFocus(camera.id)}><Camera size={15}/><span><strong>{camera.label==='Traffic camera'?`Camera ${camera.id}`:camera.label}</strong><small>{camera.location[1].toFixed(4)}, {camera.location[0].toFixed(4)} · {camera.image_url?'Periodic still available':'Location only'}</small></span><ChevronRight size={15}/></button>)}{!visible.length&&<div className="v10NoCamera"><VideoOff size={21}/> No cameras match. Refresh city sources or change your filters.</div>}</div></aside><section className="v2Panel v10CameraMapPanel"><div className="v10CameraMapHeader"><div><span className="v2Eyebrow">SPATIAL EXPLORER</span><h2>{selected?(selected.label==='Traffic camera'?`Camera ${selected.id}`:selected.label):'Madrid CCTV map'}</h2></div>{selected&&<button className="v10CameraDeselect" onClick={onClose}>Clear selection</button>}</div><div className="v10CameraMap">{map}</div><footer><MapPin size={14}/> Select markers or a camera in the list to inspect a frame; close it to dismiss the selection.</footer></section></div>
  </div>;
}
