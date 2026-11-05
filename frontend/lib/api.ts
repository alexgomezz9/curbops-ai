import type {PrecautionaryOutcome,AgentEvent,AgentResponse,DispatchPlan,MissionSnapshot,CitySignals,IncidentEvidence,CityChanges,DecisionAuditData,ScenarioBundle,VehicleExplanation,RouteIncidentImpact,RouteTrafficReading,VehicleCorridor,IncidentFleetCorridor} from './types';
const ROOT=(process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/,'');

async function request<T>(path:string,method:'GET'|'POST'='GET',body?:unknown):Promise<T>{
  const resp=await fetch(`${ROOT}${path}`,{method,headers:{'Content-Type':'application/json'},body:body === undefined? undefined:JSON.stringify(body),cache:'no-store'});
  if(!resp.ok){let detail=`HTTP ${resp.status}`;try{const p=await resp.json();detail=p.detail||detail;}catch{}throw new Error(detail);}
  return resp.json() as Promise<T>;
}
export const api={
  cameraImageUrl:(cameraId:string,refresh=0)=>`${ROOT}/api/cameras/${encodeURIComponent(cameraId)}/snapshot${refresh?`?refresh=${refresh}`:''}`,
  mission:()=>request<MissionSnapshot>('/api/mission'),
  decisionAudit:()=>request<DecisionAuditData>('/api/decision/audit'),
  scenarios:()=>request<ScenarioBundle>('/api/decision/scenarios'),
  vehicleExplanation:(id:string)=>request<VehicleExplanation>(`/api/decision/vehicles/${encodeURIComponent(id)}`),
  incidentRouteImpact:(id:string)=>request<RouteIncidentImpact>(`/api/decision/incidents/${encodeURIComponent(id)}`),
  vehicleCorridor:(id:string,scenario:'A'|'B'|'C'='C')=>request<VehicleCorridor>(`/api/decision/vehicles/${encodeURIComponent(id)}/corridor?scenario=${scenario}`),
  incidentFleetCorridor:(id:string,scenario:'A'|'B'|'C'='C')=>request<IncidentFleetCorridor>(`/api/decision/incidents/${encodeURIComponent(id)}/fleet?scenario=${scenario}`),
  vehicleTraffic:(id:string,scenario:'A'|'B'|'C'='C')=>request<RouteTrafficReading>(`/api/decision/vehicles/${encodeURIComponent(id)}/traffic?scenario=${scenario}`),
  signals:()=>request<CitySignals>('/api/signals'),
  changes:()=>request<CityChanges>('/api/signals/changes'),
  incidentEvidence:(id:string,radius=800)=>request<IncidentEvidence>(`/api/intelligence/incidents/${encodeURIComponent(id)}?radius_m=${radius}`),
  replan:()=>request<DispatchPlan>('/api/replan','POST',{include_incidents:true}),
  roadNetworkPlan:()=>request<DispatchPlan>('/api/replan/road-network','POST',{}),
  roadBaseline:()=>request<DispatchPlan>('/api/routing/baseline','POST',{}),
  routingAvailability:()=>request<{enabled:boolean;provider:string;mode:string;note:string}>('/api/routing/availability'),
  approve:(id:string)=>request<DispatchPlan>('/api/approve','POST',{plan_id:id,reviewer:'Portfolio demo operator'}),
  reset:()=>request<MissionSnapshot>('/api/reset','POST',{}),
  agent:(message:string,modelTier:'efficient'|'advanced'='efficient')=>request<AgentResponse>('/api/agent/run','POST',{message,model_tier:modelTier}),
  agentStream:async(message:string,modelTier:'efficient'|'advanced',onEvent:(event:AgentEvent)=>void,
    history:Array<{role:'user'|'assistant';content:string}>=[],context?:{scenario:'A'|'B'|'C';selected_vehicle:string|null;selected_incident:string|null}):Promise<AgentResponse>=>{
    const response=await fetch(`${ROOT}/api/agent/stream`,{
      method:'POST',headers:{'Content-Type':'application/json','Accept':'text/event-stream'},
      body:JSON.stringify({message,model_tier:modelTier,history,context}),cache:'no-store',
    });
    if(!response.ok)throw new Error(`Agent streaming failed: HTTP ${response.status}`);
    if(!response.body)throw new Error('Streaming is not supported in this browser.');
    const reader=response.body.getReader();
    const decoder=new TextDecoder();let buffer='';let finished:AgentResponse|null=null;
    const parseBlock=(block:string)=>{
      const line=block.split('\n').find(part=>part.startsWith('data: '));
      if(!line)return;
      const parsed=JSON.parse(line.slice(6)) as AgentEvent & {result?:AgentResponse};
      if(parsed.type==='result' && parsed.result){finished=parsed.result;return;}
      if(parsed.type==='error')throw new Error(parsed.message||'Agent error');
      onEvent(parsed);
    };
    try{
      while(true){
        const {value,done}=await reader.read();
        if(done)break;
        buffer+=decoder.decode(value,{stream:true}).replace(/\r\n/g,'\n');
        let ix=buffer.indexOf('\n\n');
        while(ix!==-1){const block=buffer.slice(0,ix);buffer=buffer.slice(ix+2);parseBlock(block);ix=buffer.indexOf('\n\n');}
      }
      buffer+=decoder.decode();
      if(buffer.trim())parseBlock(buffer);
    }finally{reader.releaseLock();}
    if(!finished)throw new Error('Stream ended without a final result.');
    return finished;
  },
  precautionaryAvoidance:(vehicleId='ALL',incidentIds?:string[])=>request<PrecautionaryOutcome>('/api/decision/precautionary-avoidance','POST',{vehicle_id:vehicleId,incident_ids:incidentIds||null}),
  rehearsal:(vehicleId:string,clear=false,incidentId?:string|null)=>request<{active:boolean;incident?:unknown;note:string}>('/api/decision/rehearsal','POST',{vehicle_id:vehicleId,clear,incident_id:incidentId||null}),
  refresh:()=>request<{results:Record<string,{ok:boolean;count?:number;error?:string}>}>('/api/sources/refresh','POST',{}),
  mode:(mode:'demo'|'live')=>request<MissionSnapshot>('/api/mode','POST',{mode}),
};
