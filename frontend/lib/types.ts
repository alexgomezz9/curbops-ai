export type Position = [number,number];
export type Provenance = {origin:'synthetic'|'municipal_open_data'|'computed'|'routing_provider';label:string;updated_at?:string|null;url?:string|null};
export type Vehicle = {id:string;driver:string;callsign:string;color:string;capacity:number;location:Position;stop_ids:string[];status:'en_route'|'idle'|'attention'};
export type Delivery = {id:string;customer:string;location:Position;district:string;scheduled_minutes:number;service_minutes:number;priority:'standard'|'urgent'|'critical';load_units:number};
export type Incident = {id:string;title:string;location:Position;kind:string;severity:'low'|'medium'|'high';radius_m:number;detail:string;starts_at?:string|null;ends_at?:string|null;provenance:Provenance};
export type LoadingZone = {id:string;label:string;location:Position;district:string;schedule:string;provenance:Provenance};
export type Camera = {id:string;label:string;location:Position;image_url?:string|null;provenance:Provenance};
export type RouteLine = {vehicle_id:string;coordinates:Position[];color:string;stop_ids:string[];distance_km:number;estimated_minutes:number;incidents_near:string[];fidelity:'illustrative'|'road_network'};
export type PlanMetrics = {distance_km:number;travel_minutes:number;late_deliveries:number;exposures:number;total_stops:number;score:number};
export type DispatchPlan = {id:string;status:'baseline'|'proposed'|'approved';generated_at:string;routes:RouteLine[];metrics:PlanMetrics;explanation:string;limitations:string[]};
export type SourceStatus = {id:string;name:string;connected:boolean;updated_at:string|null;count:number;provenance:'synthetic'|'municipal_open_data';detail:string};
export type MissionSnapshot = {scenario_name:string;source_mode:'demo'|'live';simulation:boolean;generated_at:string;depot:Position;vehicles:Vehicle[];deliveries:Delivery[];incidents:Incident[];loading_zones:LoadingZone[];cameras:Camera[];original_plan:DispatchPlan;proposed_plan:DispatchPlan|null;approved_plan:DispatchPlan|null;sources:SourceStatus[]};
export type TraceStep = {step:number;tool:string;detail:string;status:'success'|'warning'|'error';duration_ms:number};
export type AgentResponse = {mode:'llm_tool_agent'|'deterministic_demo'|'agent_error';provider:string;model_id?:string|null;model_requests_observed?:number|null;model_input_tokens?:number|null;model_output_tokens?:number|null;model_calls_with_usage?:number|null;summary:string;traces:TraceStep[];recommendations:string[];warnings:string[];proposed_plan:DispatchPlan|null;actions_require_approval:boolean;map_actions?:AgentMapAction[]};
export type LayerSelection = {incidents:boolean;deliveries:boolean;loading:boolean;cameras:boolean;traffic:boolean};
export type TrafficSensor = {id:string;location:Position;intensity_vph:number|null;occupancy_pct:number|null;speed_kmh:number|null;service_level:number|null;road_name:string|null};
export type CitySignals = {status:'unavailable'|'municipal_open_data';fetched_at:string|null;observed_at:string|null;source_url:string;total_valid:number;points:TrafficSensor[];distribution:Record<string,number>;note:string};

export type ProximityItem<T> = T & {distance_m:number};
export type IncidentEvidence = {
  incident:Incident;radius_m:number;calculation:'haversine_proximity';
  sensor_records_loaded:number;sensor_records_total_reported:number;
  fetched_at:string|null;observed_at:string|null;
  sensor_count_nearby:number;congested_sensor_count:number;camera_count_nearby:number;loading_zone_count_nearby:number;
  sensors:ProximityItem<TrafficSensor>[];cameras:ProximityItem<Camera>[];loading_zones:ProximityItem<LoadingZone>[];
  note:string;
};

export type AgentEvent = {type:string;completed?:number;total?:number;group?:string;vehicle_id?:string;km?:number;minutes?:number;original_km?:number;proposed_km?:number;counterfactual_changed?:boolean;points?:number;at?:number;mode?:string;provider?:string;model_id?:string;index?:number;duration_ms?:number;input_tokens?:number|null;output_tokens?:number|null;label?:string;reason?:string;step?:number;tool?:string;detail?:string;trace?:TraceStep;message?:string;action?:AgentMapAction};

/** Only observed differences between two successful municipality downloads. */
export type CityChanges = {available:boolean;previous_at:string|null;current_at:string|null;
  compared_sensor_count:number;worsened:number;improved:number;
  changed:{id:string;location:Position;road_name:string|null;previous_level:number;current_level:number;
           delta:number;speed_kmh:number|null}[];note:string};

/** Deterministic audit of the illustrative dispatch optimizer; NOT LLM reasoning. */
export type DecisionAuditData = {
  baseline_id:string;proposal_id:string;status:string;comparable:boolean;simulated:true;
  algorithm:string;objective:string;reassigned_delivery_count:number;
  distance_before_km:number;distance_after_km:number;distance_delta_km:number|null;
  flags_before:number;flags_after:number;limitations:string[];
  vehicles:Array<{vehicle_id:string;fidelity_before:string;fidelity_after:string;
    stop_count_before:number;stop_count_after:number;stops_before:string[];stops_after:string[];
    moved_in:string[];moved_out:string[];order_changed:boolean;
    distance_before_km:number;distance_after_km:number;distance_delta_km:number|null;
    proximity_flags_before:string[];proximity_flags_after:string[];explanation:string[];
    counterfactual_stops_no_risk?:string[]|null;incident_risk_changed_vehicle?:boolean|null}>;
  risk_attribution?:{
    method:string;changed_by_soft_incident_penalty:boolean;road_costs_compared:boolean;
    no_incident_counterfactual:Record<string,string[]>;
    risk_adjusted_objective?:{base_travel_minutes:number;road_km:number;approx_risk_points:number;weighted_objective:number};
    no_incident_objective?:{base_travel_minutes:number;road_km:number;approx_risk_points:number;weighted_objective:number};
    referenced_incidents:Array<{id:string;title:string;source:string;severity:string}>;
    estimated_affected_legs:number;interpretation:string;geometry_changed_for_synthetic_rehearsal?:boolean;
  }|null;
};

/** v1.4 — three independently routed scenarios, with per-source transparency. */
export type ScenarioId='A'|'B'|'C';
export type ComparisonId='AB'|'BC'|'AC';
export type ScenarioBundle={plan_id:string|null;generation:number;plan_stale?:boolean;routing_provider:string|null;as_of:string|null;
  A:DispatchPlan;B:DispatchPlan|null;C:DispatchPlan|null;
  risk_evidence:{method:string;selected_road_legs_checked?:number;known_street_legs?:number;total_directed_legs?:number;candidate_space_complete?:boolean;verified_road_closures?:number}|null;
  temporal_evidence:Array<{id:string;temporal_status:string;origin:string;verified_road_closure:boolean;starts_at:string|null;ends_at:string|null}>;precautionary_avoidance?:PrecautionaryOutcome|null;note:string};
export type RouteLegExplanation={from_stop_id:string;to_stop_id:string;road_km:number;base_minutes:number;
  modeled_late_minutes:number;nearby_incidents:Array<{id:string;title:string;severity:string;origin:string;method:string;verified_road_closure:boolean}>;risk_applied:boolean};
export type RouteScenarioDetail={scenario:ScenarioId;stop_ids:string[];road_km:number;base_minutes:number;incidents_near:string[];
  legs:RouteLegExplanation[];has_leg_detail:boolean;detour?:{geometry_changed:boolean;extra_km?:number;extra_base_minutes?:number;reason:string;incident_id:string}|null};
export type VehicleExplanation={plan_id:string|null;generation:number;vehicle_id:string;as_of:string|null;
  scenarios:{A:RouteScenarioDetail|null;B:RouteScenarioDetail|null;C:RouteScenarioDetail|null};
  interpretation:{A_to_B:string;B_to_C:string;A_to_C:string;road_restrictions:string;traffic:string;
    model_risk_changed_assignment:boolean|null;geometry_changed_due_to_synthetic_rehearsal?:boolean;evidence_method:string|null}};
export type RouteIncidentImpact={incident_id:string;title:string;severity:string;origin:string;temporal_status:string;
  affected_legs:Array<{vehicle_id:string;from_stop_id:string;to_stop_id:string}>;
  applied_to_optimizer:boolean;causal_route_change_measured:boolean;restriction_verified:boolean;note:string;
  candidate_ablation?:{method:string;selection_changed:boolean;before_stops:Record<string,string[]>;without_event_stops:Record<string,string[]>;note:string}|null};
export type VehicleCorridorIncident={id:string;title:string;location:Position;severity:string;origin:string;temporal_status:string;radius_m:number;applied_to_optimizer:boolean;restriction_verified:false};
export type VehicleCorridor={vehicle_id:string;scenario:'A'|'B'|'C';plan_id:string|null;generation:number;route_fidelity:string;nearby_count:number;applied_count:number;nearby_incidents:VehicleCorridorIncident[];note:string};
export type IncidentFleetCorridor={incident_id:string;scenario:string;nearby_vehicles:Array<{vehicle_id:string;applied_to_optimizer:boolean;temporal_status:string}>;note:string};
export type AgentMapAction={type:'select_vehicle'|'select_scenario'|'select_incident'|'show_comparison'|'open_map'|'fit_routes'|'show_traffic'|'highlight_route_incidents'|'highlight_route_sensors';
  value:string|null;plan_id:string|null;generation:number|null};

export type RouteTrafficReading={vehicle_id:string;scenario:ScenarioId;route_fidelity:string;sampled_nearby_count:number;showing:number;congested_nearby_count:number;observed_at:string|null;downloaded_at:string|null;congestion_duration_minutes:number|null;congestion_duration_status:string;note:string;observations:Array<{id:string;road_name:string;distance_m:number;service_level:number|null;intensity_vph:number|null;occupancy_pct:number|null;speed_kmh:number|null;location:[number,number]}>};

export type PrecautionaryOutcome={plan_id:string;mode:'operator_precautionary_what_if';requested_incident_ids:string[];verified_vehicle_detours:number;status:'verified_detour'|'no_matching_incidents'|'no_verified_detour';vehicles:Array<{vehicle_id:string;incident_ids:string[];avoided_ids:string[];still_near_ids:string[];verified:boolean;provider_checks:number;reason:string;extra_km:number;extra_base_minutes:number}>;comparison:{B_km:number;C_km:number;B_base_min:number;C_base_min:number};disclaimer:string};
