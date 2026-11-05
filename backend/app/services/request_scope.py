"""Resolve explicit operator scope independently of potentially stale UI/LLM focus.

A whole-fleet request may not silently inherit a single selected van or incident.
Only an incident identifier actually present in the CURRENT request scopes an
avoidance run. This preserves natural-language tool selection while enforcing
an operator-intent safety contract at the execution boundary.
"""
from __future__ import annotations
import re

_FLEET = re.compile(
    r"\b(?:fleet|every\s+(?:van|vehicle|route)|each\s+(?:van|vehicle|route)|"
    r"(?:all|entire|whole)\s+(?:three\s+|3\s+)?(?:fleet|vehicles|vans|routes)|"
    r"three\s+vehicles|3\s+vehicles|toda\s+la\s+flota|"
    r"todos\s+los\s+veh[ií]culos|tres\s+veh[ií]culos)\b", re.I)


def requests_whole_fleet(message: str) -> bool:
    return bool(_FLEET.search(message))


def resolve_avoidance_scope(message: str, vehicle_id: str, incident_id: str) -> tuple[str, str]:
    """Prevent unrequested narrow targeting from previous conversation turns.

    If the operator specified a single vehicle but no incident, the tool should
    examine *all* nearby risk points on that route, rather than reuse an old ID.
    """
    all_fleet = requests_whole_fleet(message)
    vehicle = 'ALL' if all_fleet else vehicle_id
    incident = incident_id if incident_id and incident_id.casefold() in message.casefold() else ''
    return vehicle, incident
