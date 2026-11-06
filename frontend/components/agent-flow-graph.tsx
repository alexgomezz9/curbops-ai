'use client';
import {useEffect,useMemo,useState} from 'react';
import {ArrowRight,BrainCircuit,Check,ChevronDown,Database,GitBranch,LoaderCircle,MousePointer2,Route,ShieldCheck,Sparkles,Terminal,Workflow,Maximize2,Minimize2} from 'lucide-react';
import type {AgentEvent,AgentResponse,TraceStep} from '@/lib/types';

type Execution='idle'|'running'|'done'|'failed';
type ToolNode={id:string;label:string;description:string};
const AVAILABLE:ToolNode[]=[
  {id:'inspect_fleet',label:'Fleet',description:'Vehicles, jobs and original plan'},
  {id:'get_active_incidents',label:'Incidents',description:'City events and provenance'},
  {id:'inspect_loading_reserves',label:'Loading bays',description:'Inventory; availability unknown'},
  {id:'inspect_traffic_measurements',label:'Traffic',description:'Verified sensor measurements'},
  {id:'inspect_incident_evidence',label:'Nearby evidence',description:'Geographic proximity to municipal observations'},
  {id:'prepare_dispatch_proposal',label:'Plan',description:'Draft routes; approval required'},
  {id:'prepare_precautionary_avoidance',label:'Preventative bypass',description:'Check hypothetical street detours; approval required'},
  {id:'rehearse_incident_response',label:'Incident rehearsal',description:'Prepare a synthetic incident-response proposal'},
  {id:'inspect_dispatch_decision',label:'Decision audit',description:'Inspect optimizer objective and stop reassignment'},
  {id:'inspect_data_provenance',label:'Evidence',description:'Inspect source integrity'},
  {id:'inspect_vehicle_decision',label:'Route explanation',description:'A/B/C allocation, legs and evidence'},
  {id:'inspect_incident_route_impact',label:'Incident impact',description:'Single-event counterfactual'},
  {id:'inspect_route_traffic_measurements',label:'Route sensors',description:'Municipal measurements near street geometry'},
  {id:'show_vehicle_on_map',label:'Focus vehicle',description:'Map selection action'},
  {id:'show_incident_on_map',label:'Focus incident',description:'Map selection action'},
  {id:'show_scenario_on_map',label:'Select scenario',description:'Switch A/B/C in map'},
  {id:'show_comparison_on_map',label:'Compare A/B/C',description:'Toggle scenario overlays'},
  {id:'compare_dispatch_scenarios',label:'Scenario metrics',description:'Compare compatible A/B/C road plans'},
  {id:'highlight_vehicle_incidents_on_map',label:'Highlight route notices',description:'All geographically nearby incidents, not only applied risk'},
  {id:'inspect_vehicle_corridor',label:'Route corridor',description:'Road-shape incident evidence and temporal status'},
  {id:'inspect_incident_fleet_corridor',label:'Incident fleet impact',description:'Vans near a chosen incident point'},
  {id:'investigate_fleet_disruptions',label:'Fleet impact scan',description:'Screen real road corridors and sensor observations without rerouting'},
];
const DEMO_TOOLS:Record<string,string>={inspect_operational_context:'inspect_fleet',query_incidents:'get_active_incidents',inspect_loading_zones:'inspect_loading_reserves'};
function norm(v:string){return DEMO_TOOLS[v]||v;}
function stageLabel(status:Execution){return status==='done'?'Completed':status==='running'?'Executing':status==='failed'?'Failed':'Available';}
function Signal({status}:{status:Execution}){return status==='running'?<LoaderCircle className="v2Spin" size={14}/>:status==='done'?<Check size={14}/>:status==='failed'?<span aria-hidden="true">!</span>:<span className="v6IdleDot"/>;}
export default function AgentFlowGraph({events,result,loading,approved}:{events:AgentEvent[];result:AgentResponse|null;loading:boolean;approved:boolean}){
  const [chosen,setChosen]=useState<string|null>(null);
  const [expanded,setExpanded]=useState(false);
  const [showAllTools,setShowAllTools]=useState(false);
  useEffect(()=>{if(!expanded)return;function handle(e:KeyboardEvent){if(e.key==='Escape')setExpanded(false);}window.addEventListener('keydown',handle);return()=>window.removeEventListener('keydown',handle);},[expanded]);
  const summary=useMemo(()=>{
    const calls=new Map<string,TraceStep[]>();const pending=new Set<string>();const started=new Set<string>();
    for(const e of events){
      if(e.type==='tool.started'&&e.tool){const id=norm(e.tool);pending.add(id);started.add(id);}
      if(e.type==='tool.completed'&&e.trace){const id=norm(e.trace.tool);pending.delete(id);calls.set(id,[...(calls.get(id)||[]),e.trace]);started.add(id);}
      if(e.type==='tool.failed'&&e.tool){const id=norm(e.tool);pending.delete(id);started.add(id);calls.set(id,[...(calls.get(id)||[]),{step:e.step||0,tool:e.tool,detail:e.detail||'Error',status:'error',duration_ms:0}]);}
    }
    if(!events.length&&result)for(const t of result.traces){const id=norm(t.tool);calls.set(id,[...(calls.get(id)||[]),t]);started.add(id);}
    const modelCalls=events.filter(e=>e.type==='model.call_started').length;
    const modelComplete=events.filter(e=>e.type==='model.call_completed').length;
    return {calls,pending,started,modelCalls,modelComplete};
  },[events,result]);
  const modelStatus:Execution=result?.mode==='agent_error'?'failed':loading?(summary.modelCalls>summary.modelComplete?'running':summary.modelCalls?'done':'idle'):result?.mode==='llm_tool_agent'?'done':events.some(e=>e.type==='session.fallback')?'failed':'idle';
  const finalStatus:Execution=result?.mode==='agent_error'?'failed':result?'done':loading&&summary.started.size?'running':'idle';
  const approvalStatus:Execution=approved?'done':'idle';
  // Every known callable tool is represented, including map actions.
  // Previously the fixed 8-node palette hid real executed tools.
  const runtimeNodes:ToolNode[]=[...AVAILABLE];
  const descriptions:Record<string,[string,string]>={
    inspect_vehicle_decision:['Route explanation','A/B/C allocation, legs and evidence'],
    inspect_incident_route_impact:['Incident impact','Single-event counterfactual'],
    inspect_route_traffic_measurements:['Route sensors','Municipal measurements near street geometry'],
    show_vehicle_on_map:['Focus vehicle','Map selection action'],
    show_incident_on_map:['Focus incident','Map selection action'],
    show_scenario_on_map:['Select scenario','Switch A/B/C in map'],
    show_comparison_on_map:['Compare A/B/C','Toggle scenario overlays'],
    highlight_vehicle_incidents_on_map:['Highlight risks','Affected incident points on route'],
  };
  for(const id of [...summary.started].sort()){
    if(runtimeNodes.some(item=>item.id===id))continue;
    const description=descriptions[id]||[id.replaceAll('_',' '),'Observed execution'];
    runtimeNodes.push({id,label:description[0],description:description[1]});
  }
  const visibleNodes=showAllTools?runtimeNodes:runtimeNodes.filter(t=>summary.started.has(t.id));
  const chosenNode=runtimeNodes.find(t=>t.id===chosen);
  const chosenCalls=chosen?summary.calls.get(chosen)||[]:[];
  return <section className={`v6FlowCard ${expanded?'v7FlowExpanded':''}`} aria-label="Live agent workflow graph">
    <div className="v6FlowHeader"><div><span className="v4Eyebrow">AGENT EXECUTION · OBSERVABLE GRAPH</span><h3><Workflow size={20}/> Workflow explorer</h3><p>Actual model and tool events. Click a node to inspect its output.</p></div><div className="v7GraphActions"><button type="button" className="v7GraphExpand" aria-label={expanded?'Exit workflow fullscreen':'Expand workflow graph'} onClick={()=>setExpanded(x=>!x)}>{expanded?<Minimize2 size={14}/>:<Maximize2 size={14}/>} {expanded?'Close focus':'Focus graph'}</button><div className="v6FlowStatus"><span className={loading?'is-live':''}/>{loading?'Streaming events':result?'Execution finished':'Ready to investigate'}</div></div></div>
    <div className="v6FlowScroll"><div className="v6FlowGrid">
      <div className={`v6FlowNode v6FlowTrigger ${loading||result?'completed':'idle'}`}><div className="v6NodeTop"><MousePointer2 size={17}/><span>01 / INPUT</span></div><strong>Operator request</strong><small>Investigation prompt</small><div className="v6NodeFoot"><Signal status={loading||result?'done':'idle'}/><span>{loading||result?'Received':'Awaiting'}</span></div></div>
      <div className={`v6FlowEdge ${loading?'live':''}`}><span/><ArrowRight size={18}/></div>
      <div className={`v6FlowNode v6FlowModel ${modelStatus}`}><div className="v6NodeTop"><BrainCircuit size={17}/><span>02 / MODEL</span></div><strong>{events.find(e=>e.model_id)?.model_id||result?.model_id||'LLM router'}</strong><small>{result?.mode==='deterministic_demo'?'Offline deterministic path':'Selects tools and synthesizes results'}</small><div className="v6NodeFoot"><Signal status={modelStatus}/><span>{summary.modelCalls?`${summary.modelCalls} model calls`:(result?.mode==='deterministic_demo'?'No LLM used':stageLabel(modelStatus))}</span></div></div>
      <div className={`v6FlowEdge ${loading&&summary.started.size?'live':''}`}><span/><ArrowRight size={18}/></div>
      <div className="v6FlowTools"><div className="v6ToolsTitle"><GitBranch size={15}/> 03 / OBSERVED TOOLS <span>{summary.started.size}/{runtimeNodes.length} used</span><button type="button" className="v16ToolsToggle" onClick={()=>setShowAllTools(v=>!v)}>{showAllTools?'Only executed':'All available'}</button></div><div className="v6ToolsGrid">{visibleNodes.map(t=>{
        const calls=summary.calls.get(t.id)||[];const status:Execution=summary.pending.has(t.id)?'running':calls.some(c=>c.status==='error')?'failed':calls.length?'done':'idle';
        return <button key={t.id} aria-pressed={chosen===t.id} className={`v6ToolNode ${status} ${chosen===t.id?'selected':''}`} onClick={()=>setChosen(c=>c===t.id?null:t.id)}><span className="v6ToolGlyph">{t.id==='prepare_dispatch_proposal'?<Route size={15}/>:t.id==='inspect_data_provenance'?<ShieldCheck size={15}/>:<Database size={15}/>}</span><span><strong>{t.label}</strong><small>{calls.length?`${calls.length} execution${calls.length>1?'s':''}`:'Not called'}</small></span><Signal status={status}/></button>;
      })}{visibleNodes.length===0&&<p className="v16EmptyToolGraph">No tool calls observed yet</p>}</div></div>
      <div className={`v6FlowEdge ${loading&&summary.started.size?'live':''}`}><span/><ArrowRight size={18}/></div>
      <div className={`v6FlowNode v6FlowOutput ${finalStatus}`}><div className="v6NodeTop"><Sparkles size={17}/><span>04 / OUTPUT</span></div><strong>Operational briefing</strong><small>Summary, evidence and plan</small><div className="v6NodeFoot"><Signal status={finalStatus}/><span>{stageLabel(finalStatus)}</span></div></div>
      <div className="v6FlowEdge"><span/><ArrowRight size={18}/></div>
      <div className={`v6FlowNode v6FlowApproval ${approvalStatus}`}><div className="v6NodeTop"><ShieldCheck size={17}/><span>05 / GATE</span></div><strong>{result?.proposed_plan?'Human approval':'Read-only review'}</strong><small>{result?.proposed_plan?'No automatic dispatch':'No dispatch decision in this run'}</small><div className="v6NodeFoot"><Signal status={approvalStatus}/><span>{approved?'Approved locally':result?.proposed_plan?'Awaiting operator':'Not applicable'}</span></div></div>
    </div></div>
    <div className="v6FlowBottom"><div><span className="v6FlowLegend"><i className="ok"/> Tool completed</span><span className="v6FlowLegend"><i className="busy"/> Running</span><span className="v6FlowLegend"><i/> Available, not invoked</span></div><span>Tool calls are observable; private model reasoning is not.</span></div>
    {chosenNode&&<div className="v6NodeDetails"><div className="v6NodeDetailsHead"><div><Terminal size={16}/><strong>{chosenNode.id}()</strong><span>{chosenNode.description}</span></div><button onClick={()=>setChosen(null)} aria-label="Close tool details">Close <ChevronDown size={14}/></button></div>{chosenCalls.length?chosenCalls.map((c,i)=><div key={i} className="v6NodeExecution"><span className={c.status==='error'?'failed':'success'}>{c.status} · {c.duration_ms} ms</span><pre>{c.detail}</pre></div>):<p className="v6EmptyNode">This tool is available but has not been called in this run.</p>}</div>}
  </section>;
}
