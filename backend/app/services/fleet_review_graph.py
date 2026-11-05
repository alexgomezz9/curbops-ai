"""Small explicit LangGraph workflow for read-only fleet incident review.

This is not LLM reasoning and never modifies routes. Each node is a real, testable
operation: read road-geometry evidence, choose a focus, record provenance.
"""
from __future__ import annotations

from typing import TypedDict, Any
from langgraph.graph import StateGraph, START, END

from .fleet_impact import fleet_impact
from ..store import DemoStore


class FleetReviewState(TypedDict, total=False):
    scenario: str
    report: dict[str, Any]
    focus: str | None
    workflow_steps: list[str]


def review_fleet_graph(store: DemoStore, scenario: str = 'C', on_step=None) -> dict:
    """Execute deterministic inspection before any map-focus action."""
    def observe(state: FleetReviewState) -> dict:
        report=fleet_impact(store, state['scenario'])
        if on_step: on_step('inspect_road_corridors')
        return {'report':report, 'workflow_steps':['inspect_road_corridors']}

    def prioritize(state: FleetReviewState) -> dict:
        chosen=state['report']['recommended_focus']
        if on_step: on_step('prioritize_sensor_and_incident_evidence')
        return {'focus':chosen, 'workflow_steps':state['workflow_steps']+['prioritize_sensor_and_incident_evidence']}

    def describe(state: FleetReviewState) -> dict:
        if on_step: on_step('prepare_read_only_map_actions')
        return {'workflow_steps':state['workflow_steps']+['prepare_read_only_map_actions']}

    builder=StateGraph(FleetReviewState)
    builder.add_node('inspect_road_corridors',observe)
    builder.add_node('prioritize_evidence',prioritize)
    builder.add_node('prepare_map_actions',describe)
    builder.add_edge(START,'inspect_road_corridors')
    builder.add_edge('inspect_road_corridors','prioritize_evidence')
    builder.add_edge('prioritize_evidence','prepare_map_actions')
    builder.add_edge('prepare_map_actions',END)
    outcome=builder.compile().invoke({'scenario':scenario})
    report=outcome['report']
    return {**report, 'recommended_focus':outcome['focus'], 'workflow':{'engine':'LangGraph StateGraph','steps':outcome['workflow_steps'],'read_only':True}}
