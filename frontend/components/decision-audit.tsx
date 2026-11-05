'use client';
import {useEffect,useState} from 'react';
import {ArrowRight,CheckCircle2,ChevronDown,ClipboardList,LoaderCircle,MapPin,ShieldAlert,Shuffle,Truck,GitCompareArrows,MapPinned,AlertCircle} from 'lucide-react';
import {api} from '@/lib/api';
import type {DecisionAuditData} from '@/lib/types';

export default function DecisionAudit({proposalId,onVehicle,onIncident}:{proposalId:string;onVehicle?:(id:string)=>void;onIncident?:(id:string)=>void}) {
  const [audit,setAudit]=useState<DecisionAuditData|null>(null);
  const [problem,setProblem]=useState<string|null>(null);
  useEffect(()=>{
    let cancelled=false;
    setAudit(null);setProblem(null);
    api.decisionAudit().then(result=>{if(!cancelled && result.proposal_id===proposalId)setAudit(result);})
      .catch(error=>{if(!cancelled)setProblem(String(error));});
    return ()=>{cancelled=true;};
  },[proposalId]);
  return <section className="v10Audit" aria-label="Why the proposed dispatch changed">
    <header className="v10AuditHeader"><div><span className="v2Eyebrow">DECISION AUDIT · DETERMINISTIC</span><h3><ClipboardList size={18}/> Why did the plan change?</h3><p>Actual optimizer inputs and before/after assignments. This is an audit of a <strong>fictional scenario</strong>, not model chain-of-thought.</p></div><span className="v10AuditVerified"><CheckCircle2 size={14}/> Calculated</span></header>
    {problem&&<p className="v10AuditNotice">Could not fetch the audit: {problem}</p>}
    {!problem&&!audit&&<div className="v10AuditLoading"><LoaderCircle size={16} className="v2Spin"/> Comparing assignments and stop sequences…</div>}
    {audit&&<>
      <div className="v10AuditObjective"><Shuffle size={19}/><div><strong>What the optimizer evaluated</strong><p>{audit.objective}</p></div></div>
      {audit.risk_attribution&&<section className="v13Attribution" aria-label="Incident risk counterfactual">
        <div className="v13AttributionHeading"><GitCompareArrows size={20}/><div><span className="v2Eyebrow">COUNTERFACTUAL · SAME ROAD COST MATRIX</span><h4>Did incident proximity influence this plan?</h4></div></div>
        <div className={`v13AttributionVerdict ${audit.risk_attribution.changed_by_soft_incident_penalty?'influenced':'unchanged'}`}>
          {audit.risk_attribution.changed_by_soft_incident_penalty?<AlertCircle size={18}/>:<CheckCircle2 size={18}/>}
          <div><strong>{audit.risk_attribution.changed_by_soft_incident_penalty?'Yes, incident proximity changed the simulated plan':'No, incident proximity did not change the planned routes'}</strong><p>{audit.risk_attribution.changed_by_soft_incident_penalty?'The risk-weighted solution differs from the road-only solution. This does not establish avoidance of a confirmed closure.':'Assignment changes came from road costs and delivery constraints, not the incident risk term.'}</p></div>
        </div>
        <div className="v13AttributionCompare"><div><small>WITHOUT INCIDENT RISK WEIGHTS</small><b>{audit.risk_attribution.no_incident_objective?.base_travel_minutes.toFixed(1)??'—'} min</b><span>Base drive time for counterfactual assignment</span></div><div><small>WITH PROXIMITY RISK WEIGHTS</small><b>{audit.risk_attribution.risk_adjusted_objective?.base_travel_minutes.toFixed(1)??'—'} min</b><span>Base drive time for proposed assignment</span></div></div>
        <p className="v13AttributionCaveat">Both runs use the same OSRM/ORS cost matrix. Nearby incident points are approximate risks, not verified closures or live congestion. Do not attribute global savings to one incident.</p>
        {audit.risk_attribution.referenced_incidents.length>0&&<div className="v13RiskEvidence"><strong>Nearby notices used as risk signals</strong><div>{audit.risk_attribution.referenced_incidents.slice(0,5).map(item=><button key={item.id} onClick={()=>onIncident?.(item.id)} disabled={!onIncident} title={onIncident?'Focus notice on map':'Reference only'}><MapPinned size={13}/><span>{item.title}</span><small>{item.source==='municipal_open_data'?'Municipal':'Synthetic'}</small>{onIncident&&<ArrowRight size={12}/>}</button>)}</div></div>}
      </section>}
      <div className="v10AuditStats"><div><small>Reassigned deliveries</small><strong>{audit.reassigned_delivery_count}</strong></div><div><small>Proximity flags</small><strong>{audit.flags_before} <ArrowRight size={14}/> {audit.flags_after}</strong></div><div><small>Distance difference</small><strong>{audit.comparable&&audit.distance_delta_km!==null?`${audit.distance_delta_km>0?'+':''}${audit.distance_delta_km.toFixed(1)} km`:'Not comparable'}</strong></div></div>
      <div className="v10AuditVehicles">{audit.vehicles.map(v=><details key={v.vehicle_id} className="v10AuditVehicle"><summary><Truck size={16}/><strong>{v.vehicle_id}</strong><span>{v.stop_count_before} → {v.stop_count_after} stops</span>{v.incident_risk_changed_vehicle!==null&&v.incident_risk_changed_vehicle!==undefined&&<span className={`v13VehicleCause ${v.incident_risk_changed_vehicle?'yes':'no'}`}>{v.incident_risk_changed_vehicle?'Risk influenced':'Road-cost driven'}</span>}<span className="v10AuditKm">{audit.comparable?`${v.distance_before_km.toFixed(1)} → ${v.distance_after_km.toFixed(1)} km`:'Different geometry fidelity'}</span><ChevronDown size={15}/></summary><div className="v10AuditVehicleBody"><div><small>ORIGINAL STOP ORDER</small><p>{v.stops_before.join(' → ')||'None'}</p><small>PROPOSED STOP ORDER</small><p>{v.stops_after.join(' → ')||'None'}</p></div><div className="v10AuditChanges"><span>New on vehicle: <strong>{v.moved_in.length?v.moved_in.join(', '):'none'}</strong></span><span>Moved elsewhere: <strong>{v.moved_out.length?v.moved_out.join(', '):'none'}</strong></span>{v.counterfactual_stops_no_risk&&<div className="v13VehicleCounterfactual"><small>WITHOUT INCIDENT RISK WEIGHTS · SAME MATRIX</small><p>{v.counterfactual_stops_no_risk.join(' → ')}</p></div>}{v.explanation.map((reason,i)=><p key={i}><MapPin size={12}/>{reason}</p>)}</div>{onVehicle&&<button className="v10AuditLocate" onClick={()=>onVehicle(v.vehicle_id)}>Focus this vehicle on map <ArrowRight size={14}/></button>}</div></details>)}</div>
      <div className="v10AuditFooter"><ShieldAlert size={16}/><span>Incident flags are geometric indicators only. No validated road closures, current route ETAs or business savings are claimed. Do not interpret this panel as a causal explanation of the traffic situation.</span></div>
    </>}
  </section>;
}
