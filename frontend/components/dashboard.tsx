'use client';

import {useCallback,useEffect,useLayoutEffect,useRef,useState} from 'react';
import type {ReactNode} from 'react';
import {
  GitCompareArrows,Activity,ArrowRight,BrainCircuit,Check,CheckCircle2,ChevronRight,Clock3,
  Database,Download,ExternalLink,Layers3,LoaderCircle,MapPinned,Navigation2,Radio,BarChart3,
  RefreshCw,RotateCcw,Route,Send,ShieldCheck,Sparkles,Truck,X,Sun,Moon,PanelLeftClose,PanelLeftOpen,ScanSearch,Camera as CameraIcon,Maximize2,Minimize2,
} from 'lucide-react';
import MapPanel from './map-panel';
import BriefingMarkdown from './briefing-markdown';
import AgentRunVisual from './agent-run-visual';
import CitySignalsPage from './city-signals';
import IncidentIntelligence from './incident-intelligence';
import CameraHub from './camera-hub';
import DecisionAudit from './decision-audit';
import RouteDecisionInspector from './route-decision-inspector';
import {api} from '@/lib/api';
import type {DecisionAuditData,AgentEvent,AgentResponse,CitySignals,Incident,LayerSelection,MissionSnapshot,IncidentEvidence,CityChanges,ScenarioBundle,ScenarioId,ComparisonId,AgentMapAction,DispatchPlan,VehicleCorridor} from '@/lib/types';
import preview from '@/public/demo-snapshot.json';

const seeded=preview as unknown as MissionSnapshot;
type View='overview'|'map'|'agent'|'signals'|'intel'|'cameras';
type Theme='dark'|'light';
type ChatTurn={id:number;role:'user'|'assistant';content:string;mode?:string};
const SUGGESTIONS=[
  'Analyze incidents affecting our deliveries and prepare an alternative dispatch plan.',
  'Inspect all traffic incidents and explain their operational impact.',
  'Review available sources and explain the limitations of the current plan.',
  'Inspect municipal traffic sensor measurements and explain congestion without inventing delivery ETAs.',
];
const number=(value:number)=>value.toLocaleString('en-GB',{maximumFractionDigits:1,minimumFractionDigits:1});
function exportJSON(data:unknown){
  const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
  const url=URL.createObjectURL(blob);const link=document.createElement('a');
  link.href=url;link.download='curbops-briefing.json';link.click();URL.revokeObjectURL(url);
}
function CardMetric({label,value,unit,icon,detail}:{label:string;value:string;unit:string;icon:ReactNode;detail?:string}){
  return <div className="v2Metric"><div className="v2MetricHead"><span>{label}</span>{icon}</div><div className="v2MetricNumber">{value}<small>{unit}</small></div>{detail&&<div className="v2MetricHint">{detail}</div>}</div>;
}
function Comparison({base,current,comparable}:{base:MissionSnapshot['original_plan']['metrics'];current:MissionSnapshot['original_plan']['metrics'];comparable:boolean}){
  if(!comparable)return <div className="v3UnmatchedRoutes"><strong>Road-network preview</strong><p>The proposed geometry uses a road routing service, while the baseline is schematic. Comparing their totals would be misleading.</p><div><span>Proposed route length</span><strong>{number(current.distance_km)} km</strong></div><div><span>Proposed travel estimate</span><strong>{number(current.travel_minutes)} min</strong></div></div>;
  return <div className="v2CompareGrid">
    <div><span>Distance</span><strong>{number(base.distance_km)} <small>→</small> <em>{number(current.distance_km)} km</em></strong></div>
    <div><span>Modeled travel time</span><strong>{number(base.travel_minutes)} <small>→</small> <em>{number(current.travel_minutes)} min</em></strong></div>
    <div><span>Exposure flags</span><strong>{base.exposures} <small>→</small> <em>{current.exposures}</em></strong></div>
  </div>;
}

function PlanButtons({showProposal,hasProposal,onSelect}:{showProposal:boolean;hasProposal:boolean;onSelect:(v:boolean)=>void}){
  return <div className="v2PlanSwitch"><button className={!showProposal?'selected':''} onClick={()=>onSelect(false)}>Original</button><button className={showProposal?'selected':''} disabled={!hasProposal} onClick={()=>onSelect(true)}>Proposed</button></div>;
}
function MapCanvas({snapshot,plan,referencePlan,isolatedVehicle,onIsolateVehicle,layers,selectedIncident,onSelectIncident,selectedVehicle,onSelectVehicle,compare,theme,traffic,signalMode,cameraFocusId,onCloseCamera,sensorFocusId,onSelectSensor,routeFocusToken,comparisonUi,comparisonMix,highlightIncidentIds,avoidedIncidentIds,focusSensorIds,evidence,intelMode,changes}:{
  snapshot:MissionSnapshot;plan:MissionSnapshot['original_plan'];referencePlan?:DispatchPlan|null;isolatedVehicle?:boolean;onIsolateVehicle?:(id:string)=>void;layers:LayerSelection;
  selectedIncident:string|null;onSelectIncident:(id:string)=>void;selectedVehicle:string|null;
  onSelectVehicle:(id:string|null)=>void;compare:boolean;theme:Theme;traffic?:CitySignals|null;signalMode?:boolean;cameraFocusId?:string|null;onCloseCamera?:()=>void;sensorFocusId?:string|null;onSelectSensor?:(id:string|null)=>void;routeFocusToken?:number;comparisonUi?:boolean;comparisonMix?:number;highlightIncidentIds?:string[];avoidedIncidentIds?:string[];focusSensorIds?:string[];evidence?:IncidentEvidence|null;intelMode?:boolean;changes?:CityChanges|null;
}){
  return <div className="v2Map"><MapPanel key={theme} theme={theme} snapshot={snapshot} activePlan={plan} referencePlan={referencePlan} isolatedVehicle={isolatedVehicle} onIsolateVehicle={onIsolateVehicle} layers={layers} selectedIncident={selectedIncident} onSelectIncident={onSelectIncident} selectedVehicle={selectedVehicle} onSelectVehicle={onSelectVehicle} compare={compare} traffic={traffic} signalMode={signalMode} cameraFocusId={cameraFocusId} onCloseCamera={onCloseCamera} sensorFocusId={sensorFocusId} onSelectSensor={onSelectSensor} routeFocusToken={routeFocusToken} comparisonUi={comparisonUi} comparisonMix={comparisonMix} highlightIncidentIds={highlightIncidentIds} avoidedIncidentIds={avoidedIncidentIds} focusSensorIds={focusSensorIds} evidence={evidence} intelMode={intelMode} changes={changes}/></div>;
}
export default function Dashboard(){
  const [snapshot,setSnapshot]=useState<MissionSnapshot>(seeded);
  const [backendUp,setBackendUp]=useState(false);
  const [roadAvailable,setRoadAvailable]=useState(false);
  const [roadProvider,setRoadProvider]=useState('');
  const [busy,setBusy]=useState<'agent'|'replan'|'approve'|'refresh'|'reset'|null>(null);
  const [view,setView]=useState<View>('map');
  const [navCollapsed,setNavCollapsed]=useState(false);
  const [signals,setSignals]=useState<CitySignals|null>(null);
  const [changes,setChanges]=useState<CityChanges|null>(null);
  const [autoCityRefresh,setAutoCityRefresh]=useState(false);
  const [sourceBusy,setSourceBusy]=useState(false);
  const sourceRefreshLock=useRef(false);
  const [nowMs,setNowMs]=useState(0);
  const [refreshReport,setRefreshReport]=useState<Record<string,{ok:boolean;count?:number;error?:string}>|null>(null);
  const [theme,setTheme]=useState<Theme>('dark');
  const [fleetOpen,setFleetOpen]=useState(false);
  const [cameraFocusId,setCameraFocusId]=useState<string|null>(null);
  const [sensorFocusId,setSensorFocusId]=useState<string|null>(null);
  const [selectedIncident,setSelectedIncident]=useState<string|null>(null);
  const [selectedVehicle,setSelectedVehicle]=useState<string|null>(null);
  const selectedVehicleRef=useRef<string|null>(null);
  const [layers,setLayers]=useState<LayerSelection>({incidents:false,deliveries:true,loading:false,cameras:false,traffic:false});
  const [showProposal,setShowProposal]=useState(false);
  const [scenarioBundle,setScenarioBundle]=useState<ScenarioBundle|null>(null);
  const [scenario,setScenario]=useState<ScenarioId>('A');
  const [comparisonPair,setComparisonPair]=useState<ComparisonId>('AC');
  const [isolatedVehicle,setIsolatedVehicle]=useState(false);
  const [inspectorVisible,setInspectorVisible]=useState(true);
  const [mapExpanded,setMapExpanded]=useState(false);
  const [compare,setCompare]=useState(false);
  const [routeFocusToken,setRouteFocusToken]=useState(0);
  const [comparisonMix,setComparisonMix]=useState(55);
  const [mapAgentOpen,setMapAgentOpen]=useState(true);
  const [mapAgentAutoFollow,setMapAgentAutoFollow]=useState(true);
  const mapAgentAutoFollowRef=useRef(true);
  const [agentPhase,setAgentPhase]=useState('Ready to investigate');
  const [agentMapSteps,setAgentMapSteps]=useState<string[]>([]);
  const [highlightIncidentIds,setHighlightIncidentIds]=useState<string[]>([]);
  const [corridorContext,setCorridorContext]=useState<VehicleCorridor|null>(null);
  const [routeRiskDifference,setRouteRiskDifference]=useState<{vehicle:string;avoided:{id:string;title:string}[];stillNear:{id:string;title:string}[]}|null>(null);
  const [focusSensorIds,setFocusSensorIds]=useState<string[]>([]);
  const [agentToolHistory,setAgentToolHistory]=useState<string[]>([]);
  const mapActionQueue=useRef<Promise<void>>(Promise.resolve());
  const streamedActionCount=useRef(0);
  const [prompt,setPrompt]=useState('');
  const [chatTurns,setChatTurns]=useState<ChatTurn[]>([]);
  const chatSequence=useRef(0);
  const chatScrollRef=useRef<HTMLDivElement|null>(null);
  const [modelTier,setModelTier]=useState<'efficient'|'advanced'>('efficient');
  const [agentResult,setAgentResult]=useState<AgentResponse|null>(null);
  const [agentEvents,setAgentEvents]=useState<AgentEvent[]>([]);
  const [newProposalId,setNewProposalId]=useState<string|null>(null);
  const [directAvoidance,setDirectAvoidance]=useState<import('@/lib/types').PrecautionaryOutcome|null>(null);
  const [riskSummary,setRiskSummary]=useState<DecisionAuditData['risk_attribution']|null>(null);
  const [notice,setNotice]=useState<string|null>(null);
  const [showSources,setShowSources]=useState(false);
  const [intelEvidence,setIntelEvidence]=useState<IncidentEvidence|null>(null);
  const [mapEvidenceVisible,setMapEvidenceVisible]=useState(false);
  const [detourSummaryVisible,setDetourSummaryVisible]=useState(false);
  const evidenceRevision=useRef(0);

  const reload=useCallback(async()=>{
    try{
      const mission=await api.mission();setSnapshot(mission);setBackendUp(true);
      const next=await api.scenarios();setScenarioBundle(next);
    }catch{setBackendUp(false);}
  },[]);
  useEffect(()=>{
    void reload();
    void api.signals().then(setSignals).catch(()=>setSignals(null));
    void api.changes().then(setChanges).catch(()=>setChanges(null));
    void api.routingAvailability().then(r=>{setRoadAvailable(r.enabled);setRoadProvider(r.provider);}).catch(()=>setRoadAvailable(false));
    setNowMs(Date.now());
    const tick=window.setInterval(()=>setNowMs(Date.now()),30_000);
    return ()=>window.clearInterval(tick);
  },[reload]);
  // Poll the OWN backend cache, not the Madrid service, to update the operator's view.
  useEffect(()=>{
    if(!backendUp)return;
    const timer=window.setInterval(()=>{
      void reload();
      void api.signals().then(setSignals).catch(()=>{});
      void api.changes().then(setChanges).catch(()=>{});
    },60_000);
    return ()=>window.clearInterval(timer);
  },[backendUp,reload]);
  useEffect(()=>{const saved=window.localStorage.getItem('curbops-theme');if(saved==='light'||saved==='dark')setTheme(saved);},[]);
  useEffect(()=>{window.localStorage.setItem('curbops-theme',theme);},[theme]);
  useEffect(()=>{mapAgentAutoFollowRef.current=mapAgentAutoFollow;},[mapAgentAutoFollow]);
  useEffect(()=>{selectedVehicleRef.current=selectedVehicle;},[selectedVehicle]);
  useLayoutEffect(()=>{
    const area=chatScrollRef.current;if(!area)return;
    area.scrollTop=area.scrollHeight;
    const frame=requestAnimationFrame(()=>{if(chatScrollRef.current)chatScrollRef.current.scrollTop=chatScrollRef.current.scrollHeight;});
    return ()=>cancelAnimationFrame(frame);
  },[chatTurns,busy,agentPhase,agentMapSteps]);
  useEffect(()=>{if(!notice)return;const timer=window.setTimeout(()=>setNotice(null),notice.toLowerCase().includes('error')?10000:5600);return ()=>window.clearTimeout(timer);},[notice]);
  useEffect(()=>{setAutoCityRefresh(window.localStorage.getItem('curbops-auto-city-refresh')==='true');},[]);
  useEffect(()=>{window.localStorage.setItem('curbops-auto-city-refresh',String(autoCityRefresh));},[autoCityRefresh]);
  // A route comparison opened from the bottom of the agent must land at the TOP
  // of the Operations Map, not inherit the previous document scroll position.
  useEffect(()=>{window.scrollTo({top:0,behavior:'auto'});},[view]);
  useEffect(()=>{setCameraFocusId(null);},[view]);
  useEffect(()=>{if(!mapExpanded)return;const onKey=(e:KeyboardEvent)=>{if(e.key==='Escape')setMapExpanded(false);};window.addEventListener('keydown',onKey);return()=>window.removeEventListener('keydown',onKey);},[mapExpanded]);

  const proposed=snapshot.proposed_plan||snapshot.approved_plan;
  const mapScenarioPlan=(key:ScenarioId):DispatchPlan|null=>
    (key==='A'?scenarioBundle?.A||snapshot.original_plan:key==='B'?scenarioBundle?.B||null:scenarioBundle?.C||proposed||null);
  const activeScenario:ScenarioId=compare?(comparisonPair==='AB'?'B':'C'):scenario;
  const mapPlan=mapScenarioPlan(activeScenario)||snapshot.original_plan;
  // Comparison identity is invariant, independent of whichever tab was previously active.
  const referenceScenario:ScenarioId=comparisonPair==='BC'?'B':'A';
  const referencePlan=compare?mapScenarioPlan(referenceScenario):null;
  const current=view==='map'?mapPlan:(showProposal&&proposed?proposed:snapshot.original_plan);
  const comparisonLabel=comparisonPair==='AB'?'A ↔ B · optimization effect':comparisonPair==='BC'?'B ↔ C · risk effect':'A ↔ C · overall result';
  const bcIdentical=Boolean(scenarioBundle?.B&&scenarioBundle?.C&&scenarioBundle.B.routes.every(br=>{const cr=scenarioBundle.C?.routes.find(r=>r.vehicle_id===br.vehicle_id);return cr&&cr.stop_ids.join('|')===br.stop_ids.join('|')&&Math.abs(cr.distance_km-br.distance_km)<0.05;}));
  const rehearsal=snapshot.incidents.find(i=>i.id==='SIM-ROADWORKS')||null;
  const eligibleEventCount=(scenarioBundle?.temporal_evidence||[]).filter(i=>['active','synthetic_scenario'].includes(i.temporal_status)).length;
  const incident=snapshot.incidents.find(x=>x.id===selectedIncident)||null;
  const activeMode=snapshot.source_mode==='live'?'Live sources + synthetic fleet':'Synthetic demonstration';
  const baselineReady=snapshot.original_plan.routes.length>0&&snapshot.original_plan.routes.every(r=>r.fidelity==='road_network');
  const roadReady=baselineReady&&Boolean(proposed?.routes.length)&&proposed!.routes.every(r=>r.fidelity==='road_network');
  useEffect(()=>{
    let active=true;
    if(!roadReady||!proposed){setRiskSummary(null);return;}
    void api.decisionAudit().then(d=>{if(active&&d.proposal_id===proposed.id)setRiskSummary(d.risk_attribution||null);}).catch(()=>{if(active)setRiskSummary(null);});
    return ()=>{active=false;};
  },[roadReady,proposed?.id]);
  const routeComparable=roadReady&&current.routes.every(r=>r.fidelity==='road_network');
  const delta=routeComparable?snapshot.original_plan.metrics.distance_km-current.metrics.distance_km:0;
  const fetchAgeMinutes=signals?.fetched_at&&nowMs?Math.max(0,Math.floor((nowMs-new Date(signals.fetched_at).getTime())/60_000)):null;
  const cityState=!signals?.fetched_at?'No municipal snapshot':fetchAgeMinutes!==null&&fetchAgeMinutes<=10?'Recently fetched':'Cached / older snapshot';

  function chooseScenario(id:ScenarioId){
    // Choosing an isolated scenario closes the overlay; no implicit A↔C inversion.
    setCompare(false);
    setCorridorContext(null);setRouteRiskDifference(null);setHighlightIncidentIds([]);
    setScenario(id);setFocusSensorIds([]);setShowProposal(id!=='A');
    if(!comparisonPair.includes(id))setComparisonPair(id==='A'?'AC':'BC');
    setRouteFocusToken(x=>x+1);
  }

  async function replan(){
    if(!backendUp)return setNotice('Backend unavailable. Start Docker Compose first.');
    await roadRoutes();
  }
  async function loadOriginalRoads(){
    if(!roadAvailable){setNotice('Configure ROUTING_PROVIDER=osrm_demo to view baseline streets.');return;}
    setBusy('replan');
    try{await api.roadBaseline();await reload();setShowProposal(false);setCompare(false);setScenario('A');setIsolatedVehicle(false);setSelectedVehicle(null);setRouteFocusToken(x=>x+1);setNotice('Initial fleet routes loaded from road network. No new plan was proposed.');}
    catch(error){setNotice(`Could not load baseline: ${String(error)}`);}finally{setBusy(null);}
  }
  async function avoidHazards(incidentId?:string){
    if(!backendUp||busy)return;
    setBusy('replan');setAgentPhase('Checking street-network avoidance…');
    try{
      if(!scenarioBundle?.B)await api.roadNetworkPlan();
      // Fleet-wide by default. Only scope to one van when an explicitly selected
      // incident is being investigated in the context of that vehicle.
      const targetVehicle=incidentId&&selectedVehicle?selectedVehicle:'ALL';
      const result=await api.precautionaryAvoidance(targetVehicle,incidentId?[incidentId]:undefined);
      setDirectAvoidance(result);
      setDetourSummaryVisible(true);
      setNewProposalId(result.plan_id);
      await reload();
      setScenario('C');setComparisonPair('BC');setCompare(true);setComparisonMix(50);
      setSelectedVehicle(null);setIsolatedVehicle(false);setSelectedIncident(null);
      setHighlightIncidentIds(result.avoided_incident_ids||[]);
      setRouteFocusToken(x=>x+1);
      if(result.verified_vehicle_detours){
        setNotice(`${result.verified_vehicle_detours} road-verified preventative detour(s). Hypothetical risk zones only.`);
      }else{setNotice('No provider-verified avoidance within detour limits. The plan has not fabricated a bypass.');}
      setView('map');
    }catch(error){setNotice(`Avoidance: ${String(error)}`);await reload();}
    finally{setBusy(null);}
  }
  async function roadRoutes(){
    if(!roadAvailable){setNotice('Street routing is disabled. Add ROUTING_PROVIDER=osrm_demo to .env, restart the API, then retry.');return;}setBusy('replan');
    try{const created=await api.roadNetworkPlan();setNewProposalId(created.id);setDirectAvoidance(null);await reload();setShowProposal(true);setScenario('C');setComparisonPair('BC');setCompare(true);setIsolatedVehicle(false);setSelectedIncident(null);setHighlightIncidentIds([]);setSelectedVehicle(null);setRouteFocusToken(x=>x+1);setView('map');setNotice('Both plans calculated on real streets. The stop-order heuristic and fleet are still simulated.');}
    catch(error){setNotice(String(error));}finally{setBusy(null);}
  }
  // The SSE stream carries real tool events and explicit map commands.
  // UI commands are rendered sequentially to make the operator's investigation
  // visible; presentation pacing is not reported as model/tool execution time.
  function onAgentEvent(event:AgentEvent){
    setAgentEvents(old=>[...old,event]);
    if(event.type==='model.call_started')setAgentPhase('The model is selecting a tool');
    if(event.type==='workflow.node_completed'&&event.node){setAgentPhase(`Fleet review: ${event.node.replaceAll('_',' ')}`);setAgentToolHistory(old=>[...old,`✓ ${event.node!.replaceAll('_',' ')}`].slice(-8));}
    if(event.type==='tool.started'){
      const name=event.tool?.replaceAll('_',' ')||'tool';
      setAgentPhase(`Running: ${name}…`);
      setAgentToolHistory(old=>[...old,`→ ${name}`].slice(-6));
    }
    if(event.type==='tool.completed'&&event.trace){
      setAgentPhase(`${event.trace.tool.replaceAll('_',' ')} · complete`);
      setAgentToolHistory(old=>[...old,`✓ ${event.trace!.tool.replaceAll('_',' ')}`].slice(-6));
    }
    if(event.type==='session.failed')setAgentPhase(`The provider did not finish: ${event.reason||'error'}`);
    if(event.type==='routing.route_completed')setAgentPhase(`Routing street plans ${event.completed||0}/${event.total||9}`);
    if(event.type==='avoidance.route_started')setAgentPhase(`Checking alternative roads for ${event.vehicle_id||'fleet'}…`);
    if(event.type==='avoidance.route_completed'){
      setAgentPhase(`${event.vehicle_id||'Fleet'} · ${event.verified?'road detour verified':'no verified bypass found'}`);
      // This is progress telemetry, not a map-selection instruction.
      // In particular, the last completed van must not hijack a whole-fleet request.
    }
    if(event.type==='map.action'&&event.action){
      streamedActionCount.current+=1;
      const action=event.action;
      mapActionQueue.current=mapActionQueue.current.then(async()=>{
        // Re-fetch because a plan-building tool can change the generation mid-run.
        const [mission,bundle]=await Promise.all([api.mission(),api.scenarios()]);
        if((action.generation!==null&&action.generation!==bundle.generation)||
           (action.plan_id!==null&&action.plan_id!==bundle.plan_id))return;
        setSnapshot(mission);setScenarioBundle(bundle);
        applyMapActions([action],mission,bundle);
        setAgentMapSteps(old=>[...old,describeMapAction(action)].slice(-8));
        setAgentPhase(describeMapAction(action));
        if(mapAgentAutoFollowRef.current)setView('map');
        await new Promise<void>(resolve=>window.setTimeout(resolve,550));
      }).catch(()=>{});
    }
  }
  function describeMapAction(action:AgentMapAction){
    const labels:Record<string,string>={select_vehicle:`Vehicle ${action.value} focused`,select_incident:`Notice ${action.value} focused`,select_scenario:`Scenario ${action.value} selected`,show_comparison:`Comparison ${action.value} active`,show_traffic:'Municipal sensors shown',fit_routes:'Full fleet view',open_map:'Map opened',highlight_route_incidents:`Nearby notices along ${action.value?.split(':')[0]} · inspecting geometry`,highlight_route_sensors:`Nearby sensors along ${action.value?.split(':')[0]} · inspecting readings`,highlight_avoidance_results:`Verified zone bypass · ${action.value}`};
    return labels[action.type]||action.type;
  }
  async function runAgent(message?:string){
    const text=(message||prompt).trim();if(!text)return;
    const fleetWide=/(\bfleet\b|\b(?:all|entire|whole)\s+(?:three\s+|3\s+)?(?:fleet|vehicles|vans|routes)\b|\b(?:every|each)\s+(?:van|vehicle|route)\b|toda la flota|todos los veh[ií]culos)/i.test(text);
    if(!backendUp)return setNotice('Backend unavailable. Start Docker Compose first.');
    if(busy)return;
    const previousPlanId=proposed?.id;
    setChatTurns(old=>[...old,{id:++chatSequence.current,role:'user',content:text}]);
    setPrompt(''); // Sent input is no longer part of the composer.
    setNewProposalId(null);setDirectAvoidance(null);setDetourSummaryVisible(false);
    ++evidenceRevision.current; // Cancel results of older asynchronous corridor reads.
    setMapEvidenceVisible(false);setCorridorContext(null);setRouteRiskDifference(null);
    setHighlightIncidentIds([]);setFocusSensorIds([]);
    if(fleetWide){setSelectedVehicle(null);selectedVehicleRef.current=null;setSelectedIncident(null);setIsolatedVehicle(false);setRouteFocusToken(x=>x+1);}
    setBusy('agent');streamedActionCount.current=0;setAgentResult(null);setAgentEvents([]);setAgentMapSteps([]);setAgentToolHistory([]);setAgentPhase('Starting investigation…');setMapAgentOpen(true);
    try{
      const result=await api.agentStream(text,modelTier,onAgentEvent,
        chatTurns.slice(-10).map(t=>({role:t.role,content:t.content.slice(0,1800)})),
        {scenario,selected_vehicle:fleetWide?null:selectedVehicle,selected_incident:fleetWide?null:selectedIncident});
      setAgentResult(result);
      setDetourSummaryVisible(result.mode!=='agent_error'&&result.traces.some(t=>t.tool==='prepare_precautionary_avoidance'));
      setChatTurns(old=>[...old,{id:++chatSequence.current,role:'assistant',content:result.summary,mode:result.mode}]);
      if(result.mode==='agent_error'){setAgentPhase('Execution incomplete; inspect the tool trace');setNotice(result.summary);}
      await mapActionQueue.current;
      const [mission,nextBundle]=await Promise.all([api.mission(),api.scenarios()]);
      setSnapshot(mission);setScenarioBundle(nextBundle);
      const newProposal=Boolean(result.proposed_plan && result.proposed_plan.id!==previousPlanId);
      if(newProposal){setNewProposalId(result.proposed_plan!.id);setShowProposal(true);setScenario('C');setComparisonPair('BC');setComparisonMix(50);setCompare(Boolean(nextBundle.B));if(!streamedActionCount.current){setSelectedIncident(null);setHighlightIncidentIds([]);}setIsolatedVehicle(false);}
      // Fallback non-streaming providers return their commands only in result.
      if(!streamedActionCount.current && (result.map_actions||[]).length){
        const valid=(result.map_actions||[]).filter(action=>(action.generation===null||action.generation===nextBundle.generation)&&
          (action.plan_id===null||action.plan_id===nextBundle.plan_id));
        if(valid.length)applyMapActions(valid,mission,nextBundle);
      }
      // Final view scope follows the operator's request, not the last tool's
      // progress event or a previous selected vehicle/incident.
      if(fleetWide&&result.mode!=='agent_error'&&result.traces.some(t=>t.tool==='prepare_precautionary_avoidance')){
        setSelectedVehicle(null);selectedVehicleRef.current=null;setIsolatedVehicle(false);
        setSelectedIncident(null);setCorridorContext(null);setRouteRiskDifference(null);
        setFocusSensorIds([]);setHighlightIncidentIds(nextBundle.precautionary_avoidance?.avoided_incident_ids||[]);
        setScenario('C');setComparisonPair('BC');setCompare(Boolean(nextBundle.B));setComparisonMix(50);
        setRouteFocusToken(x=>x+1);
      }
      if(result.mode!=='agent_error')setAgentPhase('Investigation complete · full trace available in AI Agent');
    }catch(error){setAgentPhase('Execution error');setNotice(String(error));setChatTurns(old=>[...old,{id:++chatSequence.current,role:'assistant',content:`Investigation did not finish: ${String(error)}`,mode:'agent_error'}]);}finally{setBusy(null);}
  }
  function applyMapActions(actions:AgentMapAction[],mission:MissionSnapshot,bundle:ScenarioBundle){
    let open=false;
    for(const action of actions){
      if(action.type==='open_map'){open=true;}
      if(action.type==='select_vehicle'&&mission.vehicles.some(v=>v.id===action.value)){
        if(selectedVehicleRef.current!==action.value){setCorridorContext(null);setRouteRiskDifference(null);setHighlightIncidentIds([]);setFocusSensorIds([]);}
        selectedVehicleRef.current=action.value;
        setSelectedVehicle(action.value);setInspectorVisible(true);setIsolatedVehicle(false);open=true;
      }
      if(action.type==='select_incident'&&mission.incidents.some(i=>i.id===action.value)){
        ++evidenceRevision.current;
        setCorridorContext(null);setRouteRiskDifference(null);setFocusSensorIds([]);
        setSelectedVehicle(null);selectedVehicleRef.current=null;setIsolatedVehicle(false);
        setSelectedIncident(action.value);setHighlightIncidentIds([action.value!]);open=true;
      }
      if(action.type==='select_scenario'&&['A','B','C'].includes(action.value||'')&&
        (action.value==='A'||(action.value==='B'&&bundle.B)||(action.value==='C'&&bundle.C))){
        chooseScenario(action.value as ScenarioId);open=true;
      }
      if(action.type==='highlight_avoidance_results'){
        const outcome=bundle.precautionary_avoidance;
        if(outcome&&outcome.verified_vehicle_detours>0){
          const fleetWide=action.value==='ALL';
          const targets=fleetWide?outcome.vehicles:outcome.vehicles.filter(v=>v.vehicle_id===action.value);
          if(targets.some(v=>v.verified)){
            setSelectedVehicle(fleetWide?null:targets[0].vehicle_id);
            selectedVehicleRef.current=fleetWide?null:targets[0].vehicle_id;
            setSelectedIncident(null);setIsolatedVehicle(false);
            setComparisonPair('BC');setCompare(Boolean(bundle.B));setComparisonMix(50);
            setScenario('C');setLayers(prev=>({...prev,incidents:false,traffic:false}));
            setHighlightIncidentIds([...new Set(targets.flatMap(v=>[...v.avoided_ids,...v.still_near_ids]))]);
            if(fleetWide)setRouteFocusToken(x=>x+1);
            open=true;
          }
        }
      }
      if(action.type==='show_comparison'&&['AB','BC','AC'].includes(action.value||'')){
        const pair=action.value as ComparisonId;
        if(pair.includes('B')&&!bundle.B||pair.includes('C')&&!bundle.C)continue;
        setComparisonPair(pair);setCompare(true);setScenario(pair.endsWith('C')?'C':'B');setShowProposal(true);open=true;
      }
      if(action.type==='highlight_route_incidents'&&action.value){
        const [vehicle,scenarioName]=action.value.split(':');
        const plan=(scenarioName==='B'?bundle.B:bundle.C);
        const route=plan?.routes.find(r=>r.vehicle_id===vehicle);
        if(!route)continue;
        setSelectedVehicle(vehicle);setSelectedIncident(null);setIsolatedVehicle(false);setFocusSensorIds([]);
        setScenario(scenarioName==='B'?'B':'C');
        if(scenarioName==='B')setCompare(false);
        setLayers(prev=>({...prev,incidents:false,traffic:false}));open=true;
        // Read the SAME road-polyline inspection as the agent; not route.incidents_near,
        // which omits unknown or temporally inactive geographic context.
        setCorridorContext(null);setRouteRiskDifference(null);setHighlightIncidentIds([]);
        const revision=++evidenceRevision.current;
        void Promise.all([api.vehicleCorridor(vehicle,scenarioName==='B'?'B':'C'),
          ...(bundle.B&&bundle.C?[api.vehicleCorridor(vehicle,'B'),api.vehicleCorridor(vehicle,'C')]:[])]).then(reports=>{
          const report=reports[0];
          if(revision!==evidenceRevision.current||report.generation!==bundle.generation||report.plan_id!==bundle.plan_id)return;
          setCorridorContext(report);
          if(reports.length===3){
            const onB=reports[1].nearby_incidents, onC=reports[2].nearby_incidents;
            const cIds=new Set(onC.map(i=>i.id));
            setRouteRiskDifference({vehicle,avoided:onB.filter(i=>!cIds.has(i.id)).map(i=>({id:i.id,title:i.title})),
              stillNear:onC.map(i=>({id:i.id,title:i.title}))});
            setHighlightIncidentIds([...new Set([...onB,...onC].map(i=>i.id))]);
          }else setHighlightIncidentIds(report.nearby_incidents.map(i=>i.id));
        }).catch(()=>setNotice('Unable to inspect route proximity.'));
      }
      if(action.type==='highlight_route_sensors'&&action.value){
        const [vehicle,scenarioName]=action.value.split(':');
        if(!mission.vehicles.some(v=>v.id===vehicle))continue;
        setSelectedVehicle(vehicle);setScenario(scenarioName==='A'?'A':scenarioName==='B'?'B':'C');
        if(scenarioName==='B'||scenarioName==='A')setCompare(false);
        setLayers(prev=>({...prev,traffic:true}));open=true;
        void api.vehicleTraffic(vehicle,(scenarioName==='A'?'A':scenarioName==='B'?'B':'C')).then(report=>{
          setFocusSensorIds(report.observations.map(o=>o.id));
        }).catch(()=>setNotice('Unable to locate sensors near the route.'));
      }
      if(action.type==='show_traffic'){setFocusSensorIds([]);setLayers(prev=>({...prev,traffic:true}));open=true;}
      if(action.type==='fit_routes'){++evidenceRevision.current;setCorridorContext(null);setRouteRiskDifference(null);setHighlightIncidentIds([]);setFocusSensorIds([]);setSelectedIncident(null);setSelectedVehicle(null);selectedVehicleRef.current=null;setIsolatedVehicle(false);setRouteFocusToken(x=>x+1);open=true;}
    }
    if(open && mapAgentAutoFollow)setView('map');
  }

  async function runRehearsal(clear=false){
    if(busy)return;
    setBusy('replan');setAgentPhase(clear?'Removing simulation…':'Creating a hypothetical obstacle along B…');
    try{
      await api.rehearsal(selectedVehicle||(selectedIncident?'AUTO':'V-02'),clear,!clear&&selectedIncident&&selectedIncident!=='SIM-ROADWORKS'?selectedIncident:null);
      const created=await api.roadNetworkPlan();setNewProposalId(created.id);setDirectAvoidance(null);
      await reload();
      setScenario('C');setComparisonPair('BC');setComparisonMix(55);setCompare(true);setShowProposal(true);
      setSelectedIncident(clear?null:'SIM-ROADWORKS');setCorridorContext(null);setHighlightIncidentIds(clear?[]:['SIM-ROADWORKS']);
      setView('map');
      setNotice(clear?'Simulation removed and routes recalculated.':'Synthetic scenario recalculated. Compare B/C; a feasible detour is not guaranteed.');
    }catch(error){setNotice(`Rehearsal: ${String(error)}`);await reload();}
    finally{setBusy(null);}
  }
  async function approve(){
    if(!snapshot.proposed_plan)return;
    setBusy('approve');try{await api.approve(snapshot.proposed_plan.id);await reload();setShowProposal(true);setNotice('Plan approved locally. No real vehicles dispatched.');}
    catch(error){setNotice(String(error));}finally{setBusy(null);}
  }
  async function reset(){
    setBusy('reset');try{if(backendUp){await api.reset();await reload();}else setSnapshot(seeded);
      setShowProposal(false);setCompare(false);setScenario('A');setIsolatedVehicle(false);setScenarioBundle(null);setAgentResult(null);setAgentEvents([]);setSelectedIncident(null);setHighlightIncidentIds([]);setAgentMapSteps([]);setAgentToolHistory([]);setCorridorContext(null);setFocusSensorIds([]);setChatTurns([]);setDirectAvoidance(null);setNewProposalId(null);setNotice('Demo reset.');
    }catch(error){setNotice(String(error));}finally{setBusy(null);}
  }
  async function syncSources(silent=false){
    if(!backendUp || sourceRefreshLock.current)return;
    sourceRefreshLock.current=true;setSourceBusy(true);
    try{
      const result=await api.refresh();setRefreshReport(result.results);
      const count=Object.values(result.results).filter(x=>x.ok).length;
      const [nextSignals,nextChanges]=await Promise.all([api.signals(),api.changes()]);
      setSignals(nextSignals);setChanges(nextChanges);
      if(!silent&&nextSignals.points.length)setLayers(old=>({...old,traffic:true}));
      if(count){
        setSnapshot(silent?await api.mission():await api.mode('live'));
        const updated=await api.scenarios();setScenarioBundle(updated);
        if(!silent)setNotice(updated.plan_stale?'Incident data changed: the current C plan is stale. Request replanning to use the updated evidence.':`${count} sources refreshed. Routes were not automatically recalculated.`);
      }
      else if(!silent)setNotice('No sources downloaded. Inspect source diagnostics.');
    }catch(error){if(!silent)setNotice(`Municipal refresh failed: ${String(error)}`);}
    finally{sourceRefreshLock.current=false;setSourceBusy(false);}
  }
  // Opt-in, minimum 5 minutes. Do not run one Madrid request per visitor on every render.
  useEffect(()=>{
    if(!autoCityRefresh||!backendUp)return;
    const timer=window.setInterval(()=>{void syncSources(true);},300_000);
    return ()=>window.clearInterval(timer);
  // Active refresh is intentionally controlled by this switch, not arbitrary state changes.
  },[autoCityRefresh,backendUp]);
  async function demoMode(){try{setSnapshot(await api.mode('demo'));setSelectedIncident(null);setNotice('Back in reproducible demo mode.');}catch(error){setNotice(String(error));}}

  function viewRouteChanges(vehicleId?:string){
    if(!roadReady){
      setNotice('Street routes are not ready. Calculating the original and proposed road plans first.');
      if(roadAvailable){void roadRoutes();return;}
    }
    setShowProposal(true);setScenario('C');setComparisonPair('AC');setCompare(true);setSelectedIncident(null);setSelectedVehicle(vehicleId||snapshot.vehicles[0]?.id||null);setInspectorVisible(true);
    setFleetOpen(Boolean(vehicleId));setRouteFocusToken(x=>x+1);setView('map');
  }

  function showIncident(id:string){setSelectedIncident(id);setView('intel');}
  function highlightIncidentEvidence(id:string){
    setSelectedIncident(id);setSelectedVehicle(null);setLayers(prev=>({...prev,incidents:false}));
    setView('map');setRouteFocusToken(x=>x+1);
  }


  return <div className="v2Shell v5Shell" data-theme={theme}>
    <div className={`v5Workspace ${navCollapsed?'nav-collapsed':''}`}>
      <aside className="v5Sidebar" aria-label="Workspace navigation">
        <div className="v5SidebarBrand"><span className="v2LogoMark">C.</span><div className="v5BrandText"><strong>CURB<span>OPS</span></strong><small>OPERATIONS INTELLIGENCE</small></div></div>
        <div className="v5SidebarDivider"/>
        <span className="v5SidebarLabel">WORKSPACE</span>
        <nav className="v5SideNav" aria-label="Main views">
          <button title="Overview" className={view==='overview'?'active':''} onClick={()=>setView('overview')}><Activity size={18}/><span>Overview</span></button>
          <button title="Operations Map" className={view==='map'?'active':''} onClick={()=>{setView('map');setRouteFocusToken(x=>x+1);}}><MapPinned size={18}/><span>Operations Map</span></button>
          <button title="City Signals" className={view==='signals'?'active':''} onClick={()=>setView('signals')}><Radio size={18}/><span>City Signals</span>{signals?.status==='municipal_open_data'&&<i className="v5NavDot"/>}</button>
          <button title="Incident Intelligence" className={view==='intel'?'active':''} onClick={()=>setView('intel')}><ScanSearch size={18}/><span>Incident Intelligence</span>{snapshot.source_mode==='live'&&<i className="v5NavDot"/>}</button>
          <button title="Municipal Cameras" className={view==='cameras'?'active':''} onClick={()=>setView('cameras')}><CameraIcon size={18}/><span>Cameras</span>{snapshot.cameras.some(c=>c.provenance.origin==='municipal_open_data')&&<i className="v5NavDot"/>}</button>
          <button title="AI Agent" className={view==='agent'?'active':''} onClick={()=>setView('agent')}><BrainCircuit size={18}/><span>AI Agent</span>{agentResult&&<i className="v5NavDot"/>}</button>
        </nav>
        <span className="v5SidebarLabel v5NavSecondLabel">MISSION STATUS</span>
        <div className="v5SidebarStatus"><span className="v5SidebarPulse"/><div><strong>{snapshot.source_mode==='live'?'Municipal signals':'Scenario / Replay'}</strong><small>{snapshot.source_mode==='live'?'Real observations + simulated fleet':'Fictional vehicles and deliveries'}</small></div></div>
        <div className="v5SidebarBottom"><button title="Collapse sidebar" className="v5Collapse" onClick={()=>setNavCollapsed(x=>!x)}>{navCollapsed?<PanelLeftOpen size={18}/>:<PanelLeftClose size={18}/>}<span>{navCollapsed?'':'Collapse sidebar'}</span></button><div className="v5SideFoot">v2.2 · MAP COPILOT<br/>MADRID / ES</div></div>
      </aside>
      <div className="v5ContentArea">
    <header className="v2Topbar">
      <div className="v2Logo"><span className="v2LogoMark">C.</span><div><strong>CURB<span>OPS</span></strong><small>OPERATIONS INTELLIGENCE</small></div></div>
      <div className="v5TopContext"><span className="v5TopContextOverline">OPERATIONS WORKSPACE</span><strong>{view==='overview'?'Mission overview':view==='map'?'Dispatch network':view==='signals'?'Municipal intelligence':view==='intel'?'Incident Intelligence':view==='cameras'?'Camera network':'Agent execution'}</strong></div>
      <div className="v2TopRight"><button className="v2IconBtn v2ThemeToggle" onClick={()=>setTheme(t=>t==='dark'?'light':'dark')} title={theme==='dark'?'Switch to light mode':'Switch to dark mode'} aria-label={theme==='dark'?'Switch to light mode':'Switch to dark mode'}>{theme==='dark'?<Sun size={18}/>:<Moon size={18}/>}</button><span className={`v2Connection ${backendUp?'connected':''}`}><i/>{backendUp?'API connected':'Offline preview'}</span><button className="v2IconBtn" onClick={()=>exportJSON({snapshot,agent_run:agentResult,generated_at:new Date().toISOString()})} title="Export JSON briefing"><Download size={17}/></button></div>
    </header>
    <main className="v2Main">
      {view==='overview'&&<>
        <div className="v2PageIntro"><div><div className="v2Kicker">MADRID, SPAIN <span>·</span> FLEET CONTROL</div><h1>Your city. <em>Under control.</em></h1><p>Investigate disruptions, compare routes and prepare a dispatch decision with an AI agent.</p></div><span className="v2ModeBadge"><ShieldCheck size={14}/> {activeMode}</span></div>
        <div className="v2Metrics"><CardMetric label="ACTIVE VEHICLES" value={String(snapshot.vehicles.length).padStart(2,'0')} unit="vans" icon={<Truck size={18}/>} detail="Fictional fleet"/><CardMetric label="DELIVERIES" value={String(snapshot.deliveries.length).padStart(2,'0')} unit="stops" icon={<MapPinned size={18}/>} detail="Scheduled in scenario"/><CardMetric label="TRAFFIC EVENTS" value={String(snapshot.incidents.length).padStart(2,'0')} unit="events" icon={<Activity size={18}/>} detail={snapshot.incidents.some(item=>item.provenance.origin==='municipal_open_data')?'Municipal incident feed':'Synthetic events'}/><CardMetric label="PLANNED DISTANCE" value={number(current.metrics.distance_km)} unit="km" icon={<Route size={18}/>} detail={delta>0?`${number(delta)} km below modeled baseline`:'Illustrative baseline'}/></div>
        <div className="v9LiveRibbon" role="status">
          <div className="v9LiveIcon"><Radio size={17}/></div>
          <div className="v9LiveDescription"><strong>Madrid Urban Pulse</strong><span>{cityState}{fetchAgeMinutes!==null?` · downloaded ${fetchAgeMinutes} min ago`:''} · municipal data, not live fleet tracking</span></div>
          <div className="v9LiveCounts"><strong>{signals?.status==='municipal_open_data'?signals.total_valid.toLocaleString('en-GB'):'—'}<small> sensors</small></strong><strong>{snapshot.incidents.filter(x=>x.provenance.origin==='municipal_open_data').length}<small> official events</small></strong></div>
          <button disabled={sourceBusy||busy!==null||!backendUp} onClick={()=>signals?.status==='municipal_open_data'?setView('signals'):void syncSources()}>{sourceBusy?<LoaderCircle className="v2Spin" size={14}/>:<RefreshCw size={14}/>} {signals?.status==='municipal_open_data'?'Explore readings':'Fetch Madrid data'}</button>
        </div>
        <div className="v2OverviewGrid"><section className="v2Panel v2OverviewMap"><div className="v2PanelHeading"><div><span className="v2Eyebrow">LIVE WORKSPACE</span><h2>Madrid operations</h2></div><button className="v2TextLink" onClick={()=>setView('map')}>Expand map <ArrowRight size={16}/></button></div><MapCanvas snapshot={snapshot} plan={current} layers={layers} selectedIncident={selectedIncident} onSelectIncident={setSelectedIncident} selectedVehicle={selectedVehicle} onSelectVehicle={setSelectedVehicle} compare={compare} theme={theme} traffic={signals}/></section>
          <aside className="v2OverviewSide"><section className="v2Spotlight"><span className="v2Eyebrow"><Sparkles size={13}/> NEXT ACTION</span><h2>One decision, all the context.</h2><p>Run a disruption analysis for your fictional fleet. The agent can inspect incidents, call tools and propose a new plan.</p><button className="v2Primary" onClick={()=>{setView('agent');void runAgent(SUGGESTIONS[0]);}} disabled={busy!==null}><BrainCircuit size={17}/> {busy==='agent'?'Running...':'Run AI investigation'} <ArrowRight size={17}/></button><div className="v2SmallPrint">Needs API connection. LLM key optional; offline deterministic workflow clearly labelled.</div></section>
          <section className="v2Panel v2Shortlist"><div className="v2PanelHeading"><div><span className="v2Eyebrow">PRIORITY SIGNALS</span><h2>Events to inspect</h2></div><button className="v2TextLink" onClick={()=>setView('intel')}>Evidence lab <ArrowRight size={14}/></button></div><div className="v2Events">{snapshot.incidents.slice(0,3).map(item=><button key={item.id} onClick={()=>showIncident(item.id)}><span className={`v2Severity ${item.severity}`}/><span><strong>{item.title}</strong><small>{item.provenance.origin==='synthetic'?'Synthetic scenario':'Madrid Open Data'} · {item.kind}</small></span><ChevronRight size={15}/></button>)}</div></section></aside></div>
      </>}
      {view==='map'&&<>
        <div className={`v17Workspace ${mapExpanded?'v17Focus':''}`} role="region" aria-label="Madrid AI Map Workspace">
          <section className="v17MapColumn" aria-label="Mapa operativo de Madrid">
            <header className="v17MapHeader">
              <div className="v17MapIdentity"><span className="v17LiveDot"/><div><strong>Madrid · Operations Map</strong><small>Simulated fleet and deliveries · {snapshot.source_mode==='live'?'municipal observations':'municipal data optional'}</small></div></div>
              <div className="v17MapActions">
                <div className="v18FleetColors" title="Vehicle route colors"><span><i className="v18V1"/> V-01</span><span><i className="v18V2"/> V-02</span><span><i className="v18V3"/> V-03</span></div>
                <div className="v17ScenarioSwitch" role="group" aria-label="Route scenarios">
                  {(['A','B','C'] as const).map(id=><button key={id} className={scenario===id?'active':''} disabled={id!=='A'&&!mapScenarioPlan(id)} onClick={()=>chooseScenario(id)} title={id==='A'?'Original plan':id==='B'?'Road-time optimization':'Indicative risk proposal'}>{id}<span>{id==='A'?'Original':id==='B'?'No risk':'Risk-aware'}</span></button>)}
                </div>
                <button className={`v17ToolBtn ${compare?'selected':''}`} aria-pressed={compare} disabled={!scenarioBundle?.C} onClick={()=>{setCompare(v=>!v);if(!compare){setComparisonPair('BC');setScenario('C');setComparisonMix(50);}}} title="Compare scenarios"> <GitCompareArrows size={16}/><span>Compare</span></button>
                <button className="v17ToolBtn" onClick={()=>{setSelectedIncident(null);setHighlightIncidentIds([]);setSelectedVehicle(null);setIsolatedVehicle(false);setRouteFocusToken(x=>x+1);}} title="Fit entire fleet"><MapPinned size={16}/><span>Fit</span></button>
                <button className="v17ToolBtn" onClick={()=>setMapExpanded(x=>!x)} title={mapExpanded?'Exit focus mode':'Fullscreen map + copilot'}>{mapExpanded?<Minimize2 size={17}/>:<Maximize2 size={17}/>}</button>
              </div>
            </header>
            {compare&&referencePlan&&<div className="v17CompareRail">
              <select value={comparisonPair} aria-label="Compared scenarios" onChange={e=>{const pair=e.target.value as ComparisonId;setComparisonPair(pair);setScenario(pair.endsWith('C')?'C':'B');}}>
                <option value="AB">A vs B · Optimization</option>
                <option value="BC">B vs C · Risk</option>
                <option value="AC">A vs C · Total</option>
              </select>
              <span>{referenceScenario}</span><input type="range" min="0" max="100" value={comparisonMix} aria-label="Route comparison visibility" onChange={e=>setComparisonMix(Number(e.target.value))}/><span>{activeScenario}</span>
              <button onClick={()=>setComparisonMix(0)} className={comparisonMix===0?'active':''}>Reference</button><button onClick={()=>setComparisonMix(50)} className={comparisonMix===50?'active':''}>Both</button><button onClick={()=>setComparisonMix(100)} className={comparisonMix===100?'active':''}>Proposal</button>
            </div>}
            <div className="v17MapViewport">{busy==='agent'&&<div className="v21LiveAction" role="status"><LoaderCircle size={14} className="v2Spin"/><span>{agentPhase}</span></div>}<MapCanvas snapshot={snapshot} plan={mapPlan} referencePlan={referencePlan} isolatedVehicle={isolatedVehicle} onIsolateVehicle={id=>{setSelectedVehicle(id);setIsolatedVehicle(true);setInspectorVisible(true);}} layers={layers} selectedIncident={selectedIncident} onSelectIncident={setSelectedIncident} selectedVehicle={selectedVehicle} onSelectVehicle={id=>{setSelectedVehicle(id);setCorridorContext(null);setRouteRiskDifference(null);setHighlightIncidentIds([]);}} compare={compare} theme={theme} traffic={signals} sensorFocusId={sensorFocusId} onSelectSensor={setSensorFocusId} routeFocusToken={routeFocusToken} comparisonMix={comparisonMix} highlightIncidentIds={highlightIncidentIds} avoidedIncidentIds={[...(routeRiskDifference?.avoided.map(i=>i.id)||[]),...(scenarioBundle?.precautionary_avoidance?.avoided_incident_ids||[])]} focusSensorIds={focusSensorIds} comparisonUi={baselineReady}/>{!baselineReady&&<div className="v17InitialRoutes"><Route size={21}/><strong>Initial street routes not loaded</strong><p>The fleet is fictional. Load street routes to explore the scenario before creating a proposal.</p><button disabled={busy!==null||!roadAvailable} onClick={()=>void loadOriginalRoads()}>{roadAvailable?'Load original routes': 'Configure OSRM/ORS to route'}</button></div>}</div>
            <footer className="v17MapFoot">
              <span>{roadReady?`${activeScenario}: ${number(mapPlan.metrics.distance_km)} km · ${number(mapPlan.metrics.travel_minutes)} min base`:'Street routes not loaded'} <small>· base road estimates · {signals?.status==='municipal_open_data'?`${signals.points.length} sensor points available (advisory only)`:'no current sensor cost model'} {scenarioBundle?.plan_stale?'· Replan: incident inputs changed':''}{scenarioBundle?.precautionary_avoidance?` · ${scenarioBundle.precautionary_avoidance.verified_vehicle_detours} provider-verified preventative detour(s)`:''}</small></span>
              <div className="v17FootRight">
                <button className="v17ToolBtn v21SourceButton" disabled={sourceBusy||busy!==null||!backendUp} onClick={()=>void syncSources()} title="Fetch the latest permitted Madrid municipal notices, cameras and traffic sensor snapshot">
                  {sourceBusy?<LoaderCircle className="v2Spin" size={15}/>:<RefreshCw size={15}/>}<span>{sourceBusy?'Loading…':signals?.status==='municipal_open_data'?`Update data · ${signals.points.length} sensors`:'Load city data'}</span>
                </button>
                {selectedVehicle&&<button onClick={()=>{setSelectedVehicle(null);setIsolatedVehicle(false);setRouteFocusToken(x=>x+1);}}>Show full fleet</button>}
                <details className="v17Layers"><summary><Layers3 size={14}/> Layers</summary><div>{([['incidents','Incidents'],['deliveries','Deliveries'],['loading','Loading'],['cameras','Cameras'],['traffic','Sensors']] as const).map(([key,title])=><label key={key}><input type="checkbox" checked={layers[key]} onChange={e=>setLayers(old=>({...old,[key]:e.target.checked}))}/>{title}</label>)}</div></details>
              </div>
            </footer>
          </section>
          <aside className="v17ChatColumn" aria-label="AI Map Copilot conversation">
            <header className="v17ChatHeader"><div className="v17ChatBrand"><BrainCircuit size={20}/><div><strong>AI Map Copilot</strong><small>{busy==='agent'?'Investigating · live tool actions':backendUp?'Connected · Madrid':'API disconnected'}</small></div></div><button onClick={()=>setView('agent')} title="Open complete tool trace"><Activity size={16}/><span>Trace</span></button></header>
            {!busy&&agentToolHistory.length>0&&<div className="v19ObservedTools"><Activity size={13}/><span>{agentToolHistory.filter(x=>x.startsWith('✓')).length} tools observed in last run</span><button onClick={()=>setView('agent')}>Inspect trace <ArrowRight size={12}/></button></div>}
            {detourSummaryVisible&&scenarioBundle?.precautionary_avoidance&&<div className="v20DetourSummary" role="status">
              <div><Route size={16}/><strong>{scenarioBundle.precautionary_avoidance.verified_vehicle_detours
                ?`${scenarioBundle.precautionary_avoidance.verified_vehicle_detours} provider-verified detour(s)`
                :'No verified detour found'}</strong>
                <button className="v22DismissSummary" aria-label="Dismiss routing result" title="Dismiss" onClick={()=>setDetourSummaryVisible(false)}><X size={14}/></button></div>
              <span>{scenarioBundle.precautionary_avoidance.verified_vehicle_detours
                ?`B ${number(scenarioBundle.precautionary_avoidance.comparison.B_km)} km → C ${number(scenarioBundle.precautionary_avoidance.comparison.C_km)} km · ${scenarioBundle.precautionary_avoidance.avoided_incident_ids?.length||0} zones avoided`
                :'The road provider returned no viable bypass within the configured limits. No route was changed.'}</span>
              <div className="v22FleetOutcomes">{scenarioBundle.precautionary_avoidance.vehicles.map(item=><div key={item.vehicle_id}><strong>{item.vehicle_id}</strong><span>{item.verified?`✓ avoided ${item.avoided_ids.length} zone(s)`:(item.incident_ids.length?'No verified bypass':'No nearby selected zone')}</span></div>)}</div>
              {scenarioBundle.precautionary_avoidance.verified_vehicle_detours>0&&<button onClick={()=>{setComparisonPair('BC');setCompare(true);setComparisonMix(50);setScenario('C');setView('map');}}>Show verified B/C changes <ArrowRight size={13}/></button>}
            </div>}
            <div className="v17Conversation" ref={chatScrollRef} aria-live="polite">
              {!chatTurns.length&&<div className="v17Welcome"><Sparkles size={22}/><h2>Ask the map.</h2><p>Inspect routes, municipal events and sensors. The copilot uses tools and controls the map as it works.</p><div><button disabled={busy!==null} onClick={()=>void runAgent('Inspect all fleet street routes. Identify nearby notices and municipal sensors, focus the most relevant vehicle, and distinguish observed data from geographic proximity. Do not replan.')}>Inspect fleet risks <ArrowRight size={14}/></button><button disabled={busy!==null} onClick={()=>void runAgent('Inspect V-02 and highlight all nearby notices along C. Separate applied risks from geographic context; focus the vehicle and notices on the map.')}>Inspect V-02 <ArrowRight size={14}/></button></div></div>}
              {chatTurns.map(turn=><div key={turn.id} className={`v17ChatBubble ${turn.role==='user'?'fromOperator':'fromAgent'}`}><div className="v17BubbleLabel">{turn.role==='user'?'OPERATOR':turn.mode==='agent_error'?'AGENT · INCOMPLETE':turn.mode==='deterministic_demo'?'LOCAL ENGINE · NO LLM':'COPILOT'}</div>{turn.role==='assistant'?<BriefingMarkdown text={turn.content}/>:<p>{turn.content}</p>}</div>)}
              {busy==='agent'&&<div className="v17Working"><div className="v17WorkingTitle"><LoaderCircle className="v2Spin" size={16}/><strong>{agentPhase}</strong></div>{agentToolHistory.slice(-4).map((step,index)=><span key={index}>{step}</span>)}{agentMapSteps.slice(-4).map((step,index)=><span key={`map-${index}`}><Check size={12}/>{step}</span>)}<small>Observed tool events, not private model reasoning.</small></div>}
            </div>
            <div className="v17ComposerDock">
              {(incident||corridorContext||routeRiskDifference||selectedVehicle||scenarioBundle?.plan_stale)&&!mapEvidenceVisible&&<button className="v21ReopenEvidence" onClick={()=>setMapEvidenceVisible(true)}><ScanSearch size={14}/> Open map evidence <ChevronRight size={13}/></button>}
              {(incident||corridorContext||routeRiskDifference||selectedVehicle||scenarioBundle?.plan_stale)&&mapEvidenceVisible&&<div className="v21EvidenceWrap"><button type="button" className="v21EvidenceClose" aria-label="Dismiss map evidence" onClick={()=>setMapEvidenceVisible(false)}><X size={14}/></button><details className="v19ContextDrawer" aria-label="Selected map evidence"><summary><ScanSearch size={14}/> Map evidence <span>{incident?.id||selectedVehicle||'Current scenario'}</span><ChevronRight size={13}/></summary><div className="v19ContextContent">
              {incident&&<div className="v17IncidentCard"><div><strong>{incident.provenance.origin==='synthetic'?'SIMULATED SCENARIO':'MUNICIPAL NOTICE'}</strong><button aria-label="Deselect incident" onClick={()=>setSelectedIncident(null)}><X size={14}/></button></div><h3>{incident.title}</h3><p>{incident.detail || 'No additional description published.'}</p><small>{incident.starts_at?`From: ${incident.starts_at}`:'Start time unverified'} · {incident.ends_at?`Until: ${incident.ends_at}`:'End time unverified'} · Not a confirmed closure</small><button className="v17IncidentAsk" disabled={busy!==null} onClick={()=>void runAgent(`Inspect incident ${incident.id}: which vehicles pass nearby, what municipal sensors or cameras exist, and whether its time window is supported by evidence. Focus it on the map. Do not replan.`)}>Investigate notice <ArrowRight size={13}/></button></div>}
              {corridorContext&&selectedVehicle===corridorContext.vehicle_id&&<div className="v17Evidence"><strong><ScanSearch size={15}/> Findings · {selectedVehicle}</strong><p>{corridorContext.nearby_count} nearby notices · {corridorContext.applied_count} applied in C</p>{corridorContext.nearby_incidents.slice(0,5).map(item=><button key={item.id} onClick={()=>{setSelectedIncident(item.id);setHighlightIncidentIds(corridorContext.nearby_incidents.map(i=>i.id));}}><span className={item.origin==='synthetic'?'synthetic':'municipal'}>{item.origin==='synthetic'?'S':'!'}</span><div><strong>{item.title}</strong><small>{item.applied_to_optimizer?'Used in C evaluation':item.temporal_status==='outside_window'?'Outside stated schedule':'Geographic context, not penalized'}</small></div></button>)}<small>Road proximity ≠ confirmed closure or measured delay.</small></div>}
              {routeRiskDifference&&routeRiskDifference.vehicle===selectedVehicle&&<div className="v17DeltaCard">
                <strong><GitCompareArrows size={14}/> Corridor B → C</strong>
                <p><b>{routeRiskDifference.avoided.length}</b> nearby notice(s) in B but outside the buffer in C. <b>{routeRiskDifference.stillNear.length}</b> still near C.</p>
                {routeRiskDifference.avoided.slice(0,3).map(i=><button key={i.id} onClick={()=>setSelectedIncident(i.id)}><Check size={12}/> Outside C buffer: {i.title}</button>)}
                <small>Geometric distance does not prove a confirmed closure or real-world causation.</small>
              </div>}
              {roadReady&&scenarioBundle?.B&&scenarioBundle?.C&&<div className="v18ScenarioInsight">
  <strong>{scenarioBundle.plan_stale?'New incidents: plan is stale':scenarioBundle.precautionary_avoidance?`${scenarioBundle.precautionary_avoidance.verified_vehicle_detours} verified preventative detour(s)`:rehearsal?'Hypothetical scenario · no confirmed closure':bcIdentical?'B and C share the same stops':'B and C differ'}</strong>
  <p>{scenarioBundle.plan_stale?'Incident inputs changed after planning. Refreshing sources does not automatically recalculate routes.':scenarioBundle.precautionary_avoidance?scenarioBundle.precautionary_avoidance.disclaimer:rehearsal?'Compare B and C: the obstacle is hypothetical, not measured Madrid traffic.':bcIdentical?'Risk-weighting did not change the route. Test an explicit hypothetical avoidance scenario.':'Inspect actual road geometries; municipal notices are not verified street closures.'}</p>
  <button disabled={busy!==null||!roadAvailable} onClick={()=>scenarioBundle.plan_stale?void roadRoutes():void runRehearsal(Boolean(rehearsal))}>{scenarioBundle.plan_stale?'Replan with updated notices':rehearsal?'Remove simulation':'Test simulated incident'}</button>
</div>}
{selectedVehicle&&inspectorVisible&&<details className="v17RouteDetails"><summary><Route size={15}/> {selectedVehicle} · route details</summary><RouteDecisionInspector vehicleId={selectedVehicle} scenario={scenario} planId={scenarioBundle?.plan_id||null} onClose={()=>setInspectorVisible(false)} onVehicle={setSelectedVehicle} onIncident={id=>{setSelectedIncident(id);setHighlightIncidentIds([id]);}} onAll={()=>{setSelectedVehicle(null);setIsolatedVehicle(false);setRouteFocusToken(x=>x+1);}}/></details>}
              </div></details></div>}
              <div className="v17QuickPrompts"><button disabled={busy!==null} onClick={()=>void runAgent('Inspect the whole fleet using municipal notices and nearby sensors. Focus the most relevant vehicle and show the evidence on the map. Do not replan.')}>Analyze fleet</button><button disabled={busy!==null||!roadAvailable} onClick={()=>void runAgent('Find safer alternative street routes for the whole fleet around nearby roadworks and potential disruption zones. Compare B with C on the map, verify any bypass with the road provider, and explain the trade-offs and unresolved risks.')}>Find safer routes</button></div>
              <form onSubmit={e=>{e.preventDefault();void runAgent();}} className="v17ChatForm"><textarea aria-label="Message the copilot" rows={2} maxLength={1200} placeholder="Ask about Madrid routes, incidents, sensors, or preventative alternatives…" value={prompt} onChange={e=>setPrompt(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();void runAgent();}}}/><button disabled={busy!==null||!prompt.trim()} aria-label="Send message">{busy==='agent'?<LoaderCircle className="v2Spin" size={18}/>:<Send size={18}/>}</button></form>
              <div className="v17ComposerMeta"><span>{backendUp?'Madrid municipal data and simulated fleet':'Backend offline'} </span><button onClick={()=>setView('agent')}>View execution trace <ArrowRight size={12}/></button></div>
              <details className="v17MoreControls"><summary>Advanced actions</summary><div>{!baselineReady&&<button disabled={busy!==null||!roadAvailable} onClick={()=>void loadOriginalRoads()}>Load original road routes</button>}<button disabled={busy!==null||!roadAvailable} onClick={()=>void roadRoutes()}>Recalculate with road engine (no LLM)</button><button disabled={busy!==null||!roadAvailable} onClick={()=>void avoidHazards()}>Verify preventative bypasses (routing engine)</button><button disabled={busy!==null} onClick={()=>void syncSources()}>Refresh city sources</button>{scenarioBundle?.B&&<button disabled={busy!==null} onClick={()=>void runRehearsal(Boolean(rehearsal))}>{rehearsal?'Remove simulated obstacle':selectedIncident?'Treat selected notice as hypothetical obstacle':'Simulate roadworks on B'}</button>}<button disabled={busy!==null} onClick={()=>void reset()}>Reset scenario</button></div></details>
            </div>
          </aside>
        </div>
      </>}
      {view==='agent'&&<>
        <div className="v2PageIntro v2CompactIntro"><div><div className="v2Kicker">OPERATIONS / AI AGENT</div><h1>AI Dispatch Copilot</h1><p>Ask for an operational analysis. Inspect every tool call before approving a simulated decision.</p></div><span className="v2ModeBadge"><BrainCircuit size={14}/>{agentResult?.mode==='llm_tool_agent'?`LLM: ${agentResult.provider}`:'Demo workflow · API optional'}</span></div>
        <div className="v15AgentMapNav"><button onClick={()=>{setMapAgentOpen(true);setView('map');}}>View on map <ArrowRight size={14}/></button><span>Map actions are applied during execution. This page audits all observed tool calls.</span></div><div className="v2AgentLayout"><section className="v2Panel v2AgentMain"><div className="v2PanelHeading"><div><span className="v2Eyebrow">AGENT WORKSPACE</span><h2>What should we investigate?</h2></div><span className="v2ModeBadge">HUMAN IN THE LOOP</span></div>
          <div className="v2AgentBody">{!agentResult && busy!=='agent'?<div className="v2AgentWelcome"><span className="v2AgentBigIcon"><BrainCircuit size={30}/></span><h2>An operator's copilot, not a chatbot.</h2><p>Ask CurbOps to inspect the scenario, retrieve evidence and prepare a plan you can review.</p><div className="v2AgentSuggested">{SUGGESTIONS.map((text,i)=><button key={text} disabled={busy!==null} onClick={()=>{setPrompt(text);void runAgent(text);}}><span>0{i+1}</span>{text}<ArrowRight size={15}/></button>)}</div></div>:<AgentRunVisual events={agentEvents} result={agentResult} loading={busy==='agent'} snapshot={snapshot} onMap={viewRouteChanges} onIncident={highlightIncidentEvidence}/>}</div>
          <form className="v2AgentComposer v10AgentComposer" onSubmit={event=>{event.preventDefault();void runAgent();}}><div className="v10ComposerIntro"><label htmlFor="v2Prompt">YOUR OWN REQUEST · FREE FORM</label><span>Editable · Ctrl + Enter to run</span></div><textarea id="v2Prompt" rows={3} maxLength={1200} placeholder="Ask about an incident, route choice, sensor reading, or operational decision…" value={prompt} onChange={event=>setPrompt(event.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();void runAgent();}}}/><div className="v10PromptTemplates"><button type="button" onClick={()=>setPrompt('Inspect municipal notices near Plaza de Castilla and nearby sensors and cameras.')} disabled={busy!==null}>Investigate zone</button><button type="button" onClick={()=>setPrompt('Prepare a street-route proposal and explain exactly what changed.')} disabled={busy!==null}>Explain routing</button><button type="button" onClick={()=>setPrompt('Compare two municipal sensor snapshots, separating observations from hypotheses.')} disabled={busy!==null}>Traffic changes</button></div><div className="v4ModelSelectorRow"><label htmlFor="v4ModelTier">LLM quality</label><select id="v4ModelTier" value={modelTier} disabled={busy!==null} onChange={event=>setModelTier(event.target.value as 'efficient'|'advanced')}><option value="efficient">Efficient · Flash-Lite (500 RPD*)</option><option value="advanced">Advanced · Flash (20 RPD*)</option></select><small>*Example Google quotas shown by your project; may change. Advanced mode is opt-in. <a href="https://aistudio.google.com/rate-limit" target="_blank" rel="noopener noreferrer">View your quota ↗</a></small></div><div><span>{backendUp?'Backend ready':'Backend offline'} · {agentResult?.mode==='llm_tool_agent'?'LLM verified':agentResult?'Demo mode':'Not run yet'}</span><button className="v2Primary" disabled={busy!==null||!prompt.trim()} type="submit">{busy==='agent'?<LoaderCircle className="v2Spin" size={15}/>:<Send size={15}/>} Run investigation</button></div></form>
        </section>
        <aside className="v2AgentAside">{newProposalId&&proposed?.id===newProposalId&&<section className="v2Panel v2Proposal"><span className="v2Eyebrow">DISPATCH DECISION</span><h2>{showProposal&&roadReady&&snapshot.approved_plan?'Approved locally':showProposal&&roadReady&&proposed?'Street proposal ready':'No new proposal displayed'}</h2><p>{showProposal&&roadReady&&proposed?`${proposed.routes.length} vehicles · ${proposed.metrics.total_stops} simulated deliveries · road-network estimates`:'Open an investigation to propose changes; baseline street routes can be loaded without any optimization.'}</p>{!roadReady&&roadAvailable&&<button className="v11RoadPrimary v2Full" disabled={busy!==null} onClick={()=>void runAgent('Inspect the current fictional fleet and mapped incidents. Prepare a proposal using road matrix costs and audit the counterfactual effect of approximate incident risk. Do not approve.') }><BrainCircuit size={15}/> Request AI proposal</button>}{roadReady&&proposed&&showProposal&&<>{riskSummary&&<div className={`v13ImpactPill ${riskSummary.changed_by_soft_incident_penalty?'warn':''}`}><GitCompareArrows size={16}/><span><strong>{riskSummary.changed_by_soft_incident_penalty?'Incident proximity influenced the model':'Road-cost-driven route changes'}</strong><small>Counterfactual on identical base-road costs; no certified blocked edges.</small></span></div>}<Comparison base={snapshot.original_plan.metrics} current={proposed.metrics} comparable={roadReady}/><button className="v2Primary v2Full" disabled={busy!==null||!!snapshot.approved_plan||!!scenarioBundle?.plan_stale} onClick={approve}>{snapshot.approved_plan?<><CheckCircle2 size={15}/> Approved locally</>:<><Check size={15}/> Approve simulated plan</>}</button><button className="v2TextLink v2Full" onClick={()=>viewRouteChanges()}>Compare routes on map <ArrowRight size={15}/></button></>}</section>}{!newProposalId&&<section className="v2Panel v2Proposal"><span className="v2Eyebrow">READ-ONLY INVESTIGATION</span><h2>No plan changes in this request</h2><p>This investigation did not create a new proposal. There is nothing to approve or dispatch.</p></section>}<section className="v2Panel v2DataBox"><span className="v2Eyebrow">DATA TRANSPARENCY</span><h2>Understand the inputs</h2><p>The three vans and deliveries are fictional. Municipal feeds are opt-in and labeled by provenance.</p><button className="v2Secondary v2Full" onClick={()=>setShowSources(v=>!v)}><Database size={15}/> {showSources?'Hide data sources':'Inspect data sources'}</button>{showSources&&<div className="v2Sources">{snapshot.sources.map(source=><div key={source.id}><span>{source.name}</span><strong>{source.connected?'Connected':'Demo'}</strong></div>)}<button className="v2Secondary v2Full" disabled={busy!==null||sourceBusy} onClick={()=>void syncSources()}>{sourceBusy?<LoaderCircle className="v2Spin" size={14}/>:<RefreshCw size={14}/>} Fetch Madrid open data</button>{snapshot.source_mode==='live'&&<button className="v2TextLink" onClick={demoMode}>Back to demo</button>}</div>}</section></aside></div>
      </>}
      {view==='intel'&&<IncidentIntelligence mission={snapshot} signals={signals} selectedIncident={selectedIncident} onSelectIncident={setSelectedIncident} onCameraFocus={setCameraFocusId} onAskAgent={id=>{const item=snapshot.incidents.find(x=>x.id===id);const question=`Investigate incident ${id}: ${item?.title||'selected event'}. First inspect nearby municipal evidence with inspect_incident_evidence, examine source provenance, then summarize observed sensor and camera context. Do not infer road closures or travel delays from proximity alone.`;setPrompt(question);void runAgent(question);}} refresh={()=>void syncSources()} refreshing={sourceBusy} onEvidence={setIntelEvidence} map={<MapCanvas snapshot={snapshot} plan={current} layers={{incidents:true,deliveries:false,loading:true,cameras:true,traffic:true}} selectedIncident={selectedIncident} onSelectIncident={setSelectedIncident} selectedVehicle={null} onSelectVehicle={()=>{}} compare={false} theme={theme} traffic={signals} signalMode intelMode evidence={intelEvidence} cameraFocusId={cameraFocusId} onCloseCamera={()=>setCameraFocusId(null)}/>}/>}
      {view==='cameras'&&<CameraHub mission={snapshot} focusId={cameraFocusId} onFocus={setCameraFocusId} onClose={()=>setCameraFocusId(null)} onRefresh={()=>void syncSources()} refreshing={sourceBusy} map={<MapCanvas snapshot={snapshot} plan={current} layers={{incidents:false,deliveries:false,loading:false,cameras:true,traffic:false}} selectedIncident={null} onSelectIncident={()=>{}} selectedVehicle={null} onSelectVehicle={()=>{}} compare={false} theme={theme} cameraFocusId={cameraFocusId} onCloseCamera={()=>setCameraFocusId(null)} signalMode/>}/>}
      {view==='signals'&&<CitySignalsPage signals={signals} changes={changes} autoRefresh={autoCityRefresh} onAutoRefresh={setAutoCityRefresh} mission={snapshot} loading={sourceBusy} refresh={()=>void syncSources()} onMap={()=>setView('map')} report={refreshReport} onCameraFocus={setCameraFocusId} onCameras={()=>{setCameraFocusId(null);setView('cameras');}} onSensorFocus={setSensorFocusId} map={<MapCanvas snapshot={snapshot} plan={current} layers={{incidents:false,deliveries:false,loading:false,cameras:true,traffic:true}} cameraFocusId={cameraFocusId} onCloseCamera={()=>setCameraFocusId(null)} sensorFocusId={sensorFocusId} selectedIncident={selectedIncident} onSelectIncident={setSelectedIncident} selectedVehicle={null} onSelectVehicle={()=>{}} compare={false} theme={theme} traffic={signals} changes={changes} signalMode/>}/>}
    </main>
    <footer className="v2Footer"><span>CurbOps AI · Urban operations</span><span>Simulated fleet · Municipal data © Ayuntamiento de Madrid where connected</span></footer>
    {notice&&<div className="v2Toast" role="status"><span>{notice}</span><button onClick={()=>setNotice(null)} aria-label="Dismiss"><X size={16}/></button></div>}
      </div>
    </div>
  </div>;
}
