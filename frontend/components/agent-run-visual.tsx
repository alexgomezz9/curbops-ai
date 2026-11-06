'use client';
import {useMemo} from 'react';
import {
  ArrowRight, Check, CheckCircle2, Clock3, LoaderCircle,
  Route, Layers, Radar, ShieldCheck, AlertTriangle, Search,
  BrainCircuit, Terminal, ChevronDown, Truck,
} from 'lucide-react';
import type {AgentEvent,AgentResponse,MissionSnapshot,TraceStep} from '@/lib/types';
import AgentFlowGraph from './agent-flow-graph';
import BriefingMarkdown from './briefing-markdown';
import DecisionAudit from './decision-audit';

type Props={events:AgentEvent[];result:AgentResponse|null;loading:boolean;snapshot:MissionSnapshot;onMap:(vehicleId?:string)=>void;onIncident?:(id:string)=>void};
const prettyName=(name:string)=>({
  inspect_fleet:'Inspect fleet and assignments',
  inspect_operational_context:'Inspect operational context',
  query_incidents:'Query municipal incidents',
  get_active_incidents:'Query mapped incidents',
  inspect_loading_zones:'Check loading reserves',
  inspect_loading_reserves:'Check loading reserves',
  inspect_data_provenance:'Verify data provenance',
  inspect_incident_evidence:'Inspect nearby municipal evidence',
  prepare_dispatch_proposal:'Generate alternative dispatch plan',
  inspect_dispatch_decision:'Audit simulated route decision',
}[name]||name.replaceAll('_',' '));
const compact=(n:number)=>n.toLocaleString('en-GB',{maximumFractionDigits:1});

export default function AgentRunVisual({events,result,loading,snapshot,onMap,onIncident}:Props){
  const started=events.some(e=>e.type==='session.started');
  const fallback=events.find(e=>e.type==='session.fallback');
  const complete=Boolean(result);
  const toolNodes=useMemo(()=>{
    const nodes:{key:string;tool:string;status:'running'|'success'|'error';trace?:TraceStep;at?:number}[]=[];
    for(const e of events){
      if(e.type==='tool.started' && e.tool){
        nodes.push({key:`${e.step||nodes.length}-${e.tool}-${nodes.length}`,tool:e.tool,status:'running',at:e.at});
      }else if(e.type==='tool.completed' && e.trace){
        const node=[...nodes].reverse().find(n=>n.tool===e.trace!.tool&&n.status==='running');
        if(node){node.status='success';node.trace=e.trace;}
        else nodes.push({key:`done-${nodes.length}`,tool:e.trace.tool,status:'success',trace:e.trace});
      }else if(e.type==='tool.failed'&&e.tool){
        const node=[...nodes].reverse().find(n=>n.tool===e.tool&&n.status==='running');
        if(node){node.status='error';node.trace={step:e.step||0,tool:e.tool,detail:e.detail||'Tool error',status:'error',duration_ms:0};}
      }
    }
    if(!nodes.length && result){return result.traces.map((t,i)=>({key:`past-${i}`,tool:t.tool,status:'success' as const,trace:t}));}
    return nodes;
  },[events,result]);
  // Do not show a stale proposal during unrelated investigations.
  const proposalTools=['prepare_dispatch_proposal','prepare_precautionary_avoidance','rehearse_incident_response'];
  const proposedInThisRun=Boolean(result?.proposed_plan && events.some(e=>e.type==='tool.completed' && e.trace && proposalTools.includes(e.trace.tool)));
  const candidatePlan=proposedInThisRun ? result!.proposed_plan : null;
  const finalPlan=candidatePlan?.routes.every(r=>r.fidelity==='road_network')?candidatePlan:null;
  const base=snapshot.original_plan;
  const sameFidelity=Boolean(finalPlan && base.routes.every(r=>r.fidelity==='road_network'));
  const saved=finalPlan && sameFidelity ? base.metrics.distance_km-finalPlan.metrics.distance_km : null;
  const hasLive=events.some(e=>e.type==='model.started');
  const completedCalls=events.filter(e=>e.type==='model.call_completed');
  const startedCalls=events.filter(e=>e.type==='model.call_started');
  const roadProgress=[...events].reverse().find(e=>e.type==='routing.route_completed');
  const routingStarted=events.some(e=>e.type==='routing.started');
  const routingFinished=events.some(e=>e.type==='routing.completed');
  const matrixStarted=events.some(e=>e.type==='routing.matrix_started');
  const matrixFinished=events.find(e=>e.type==='routing.matrix_completed');
  const routingFailed=events.find(e=>e.type==='routing.failed');
  const runningModel=loading && hasLive && (startedCalls.length===0 || startedCalls.length>completedCalls.length);
  return <div className="v4RunRoot">
    <div className="v4ExecutionHeader">
      <div className="v4ExecutionIcon"><BrainCircuit size={18}/></div>
      <div><span className="v4Eyebrow">EXECUTION OVERVIEW</span><h3>{loading?'Investigation in progress':complete?(result?.mode==='agent_error'?'Investigation stopped':'Investigation completed'):'Starting investigation'}</h3></div>
      <span className={`v4SessionState ${loading?'processing':result?.mode==='llm_tool_agent'?'real':'simulated'}`}>
        {loading?<><LoaderCircle className="v2Spin" size={13}/> Running</>:result?.mode==='llm_tool_agent'?<><CheckCircle2 size={13}/> LLM verified</>:result?.mode==='agent_error'?<><AlertTriangle size={13}/> LLM limit</>:<><ShieldCheck size={13}/> Offline demo</>}
      </span>
    </div>
    {hasLive&&<div className="v4CallTelemetry"><BrainCircuit size={14}/><strong>{events.find(e=>e.type==='model.started')?.model_id||'LLM provider'}</strong><span>{startedCalls.length} model request{startedCalls.length===1?'':'s'} observed · {completedCalls.length} completed · {toolNodes.length} tool call{toolNodes.length===1?'':'s'}</span></div>}
    {result?.model_input_tokens!==null&&result?.model_input_tokens!==undefined&&<div className="v10UsageMeter"><span><BrainCircuit size={14}/> Model usage reported by provider</span><strong>{result.model_input_tokens.toLocaleString('en-GB')} input tokens</strong><strong>{result.model_output_tokens?.toLocaleString('en-GB')||'—'} output tokens</strong><small>{result.model_calls_with_usage} model call(s) reported usage; costs depend on billing tier.</small></div>}
    {matrixStarted&&!routingStarted&&!routingFailed&&<div className="v12StreetProgress" role="status"><span className="v12StreetProgressIcon"><Route size={18}/></span><div className="v12StreetProgressContent"><strong>{matrixFinished?'Road cost matrix calculated':'Calculating 16 × 16 road cost matrix'}</strong><small>{matrixFinished?`Counterfactual checked: ${matrixFinished.counterfactual_changed?'incident risk changed the modeled decision':'incident risk did not change the decision'}`:'Provider road costs for 15 fictional deliveries and the depot; route geometries are not yet published.'}</small><div className="v12RouteProgressTrack"><span style={{width:matrixFinished?'100%':'40%'}}/></div></div></div>}
    {(routingStarted||routingFailed)&&<div className={`v12StreetProgress ${routingFailed?'error':routingFinished?'complete':''}`} role="status" aria-live="polite">
      <span className="v12StreetProgressIcon"><Route size={18}/></span>
      <div className="v12StreetProgressContent"><strong>{routingFailed?'Street routing unavailable':routingFinished?'Street scenarios verified':'Calculating street geometries'}</strong>
      <small>{routingFailed?.reason|| (routingFinished?'Baseline and alternative on the same street network · road-time matrix optimized; no verified street closures':`${roadProgress?.group==='proposed'?'Proposed':'Baseline'} · ${roadProgress?.vehicle_id||'fleet'} · ${roadProgress?.completed||0}/6 routes calculated` )}</small>
      <div className="v12RouteProgressTrack"><span style={{width:`${routingFinished?100:Math.round((roadProgress?.completed||0)/(roadProgress?.total||6)*100)}%`}}/></div></div>
      <b>{routingFinished?`${roadProgress?.total||9}/${roadProgress?.total||9}`:`${roadProgress?.completed||0}/${roadProgress?.total||9}`}</b>
    </div>}
    <AgentFlowGraph events={events} result={result} loading={loading} approved={Boolean(candidatePlan && snapshot.approved_plan?.id===candidatePlan.id)}/>
    <div className="v4PhaseRail">
      <div className={started?'active':''}><span>01</span> Interpret</div>
      <div className={toolNodes.length?'active':''}><span>02</span> Execute tools</div>
      <div className={finalPlan?'active':''}><span>03</span> Prepare plan</div>
      <div className={complete?'active':''}><span>04</span> Operator review</div>
    </div>
    {fallback&&<div className="v4Fallback"><AlertTriangle size={16}/><div><strong>LLM fallback activated</strong><p>{fallback.reason}</p><small>The tool steps below belong to the local deterministic workflow, not to Gemini.</small></div></div>}
    <section className="v4Telemetry">
      <div className="v4SectionBar"><div><Radar size={16}/><strong>Execution timeline</strong></div><span>{toolNodes.length} tool call{toolNodes.length===1?'':'s'} {loading?'· live':''}</span></div>
      {runningModel && <div className="v4ModelActivity"><LoaderCircle className="v2Spin" size={15}/><div><strong>Model processing</strong><span>Choosing the next action or preparing the final answer</span></div><span className="v4LiveDot">LIVE</span></div>}
      {toolNodes.length? <ol className="v4ToolList">{toolNodes.map((item,i)=><li key={item.key} className={item.status}>
        <span className="v4ToolMarker">{item.status==='running'?<LoaderCircle className="v2Spin" size={15}/>:item.status==='error'?<AlertTriangle size={15}/>:<Check size={15}/>}</span>
        <div className="v4ToolContent"><div className="v4ToolRow"><strong>{prettyName(item.tool)}</strong><span>{item.status==='running'?'Executing…':`${item.trace?.duration_ms??0} ms`}</span></div>
          <span className="v4ToolId">{item.tool}()</span>
          {item.trace?.detail&&<details className="v4ToolOutput" open={i===toolNodes.length-1}><summary><Terminal size={12}/> Tool output <ChevronDown size={12}/></summary><p>{item.trace.detail}</p></details>}
        </div>
      </li>)}</ol>:<div className="v4EmptyTools">{loading?'Waiting for the first tool event…':'Tools will appear here as they execute.'}</div>}
      <div className="v4EvidenceNote"><ShieldCheck size={13}/> Only tool calls, outputs and decision summaries are shown; no private model reasoning is exposed.</div>
    </section>
    {result&&<>
      <section className="v4Briefing">
        <div className="v4SectionBar"><div><Layers size={16}/><strong>Operational briefing</strong></div><span>{result.model_id||result.provider}{result.model_requests_observed?` · ${result.model_requests_observed} model requests`:''}</span></div>
        <div className="v4BriefingBody"><span className="v4Eyebrow">EXECUTIVE SUMMARY</span><BriefingMarkdown text={result.summary}/></div>
        {result.recommendations.length>0&&<div className="v4Recommended"><strong>Recommended next steps</strong>{result.recommendations.map((x,i)=><div key={i}><span>{i+1}</span><p>{x}</p></div>)}</div>}
      </section>
      {finalPlan&&sameFidelity&&<section className="v4Decision">
        <div className="v4DecisionHead"><div><Route size={18}/><div><span className="v4Eyebrow">PROPOSED ROUTE CHANGES</span><h3>Visualize the dispatch decision</h3></div></div><span className="v4ApprovalBadge">{snapshot.approved_plan?.id===finalPlan.id?"Approved locally · no dispatch":"Human approval required"}</span></div>
        <div className="v4DecisionNumbers">
          <div><small>Baseline · {base.routes.every(r=>r.fidelity==='road_network')?'road network':'schematic'}</small><strong>{compact(base.metrics.distance_km)} km</strong></div>
          <ArrowRight size={18}/>
          <div><small>Proposed · {finalPlan.routes.every(r=>r.fidelity==='road_network')?'road network':'schematic'}</small><strong>{compact(finalPlan.metrics.distance_km)} km</strong></div>
          <div className="v4DecisionDelta">{saved===null?'Not comparable':`${saved>=0?'−':'+'}${compact(Math.abs(saved))} km*`}</div>
        </div>
        <p className="v4DecisionDisclaimer">*{sameFidelity?'Both plans routed on streets. Stop order is heuristic; base durations are not live ETAs and incident closures were not applied.':'Baseline is schematic; provider geometries must not be compared as like-for-like.'}</p>
        <div className="v4VehicleRows">{finalPlan.routes.map(r=>{
          const baseRoute=base.routes.find(b=>b.vehicle_id===r.vehicle_id);
          return <button key={r.vehicle_id} onClick={()=>onMap(r.vehicle_id)} title={`Open route ${r.vehicle_id} on map`}>
            <span className="v4VehicleDot" style={{background:r.color}}/><Truck size={15}/><strong>{r.vehicle_id}</strong><span>{r.stop_ids.length} stops</span><em>{sameFidelity&&baseRoute?`${compact(baseRoute.distance_km)} → ${compact(r.distance_km)} km`:`${compact(r.distance_km)} km`}</em><ArrowRight size={15}/>
          </button>;
        })}</div>
        <button className="v4MapCTA" onClick={()=>onMap()}><MapPinnedIcon/> <span><strong>OPEN ROUTE COMPARISON</strong><small>Show original vs proposed · inspect vehicles · play simulated routes</small></span><ArrowRight size={18}/></button>
      </section>}
      {finalPlan&&sameFidelity&&<DecisionAudit proposalId={finalPlan.id} onVehicle={id=>onMap(id)} onIncident={onIncident}/>}
      {result.warnings.length>0&&<details className="v4Limitations"><summary><AlertTriangle size={15}/> Assumptions & limitations <ChevronDown size={14}/></summary>{result.warnings.map((w,i)=><p key={i}>{w}</p>)}</details>}
    </>}
  </div>;
}
function MapPinnedIcon(){return <Route size={19}/>;}
