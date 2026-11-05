"""Incident timing and geometry safety checks for an explainable *simulation*.

An official point is not a verified closed road edge. No hard road restriction
is inferred from the administrative type `closure`.
"""
from __future__ import annotations
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from ..models import Incident

MADRID = ZoneInfo('Europe/Madrid')


def _date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        value = None
        for pattern in ('%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                value = datetime.strptime(raw, pattern)
                break
            except ValueError:
                continue
    if value is None:
        return None
    return value.replace(tzinfo=MADRID) if value.tzinfo is None else value.astimezone(MADRID)


def incident_status(incident: Incident, at: datetime) -> str:
    """active / outside_window / unknown. Unknown never becomes validated closure."""
    at = at.replace(tzinfo=timezone.utc) if at.tzinfo is None else at
    at = at.astimezone(MADRID)
    start, end = _date(incident.starts_at), _date(incident.ends_at)
    if (incident.starts_at and not start) or (incident.ends_at and not end):
        return 'unknown'
    if start and end and end < start:
        return 'unknown'
    if start and at < start or end and at > end:
        return 'outside_window'
    if start or end:
        return 'active'
    # Deterministic synthetic rehearsal events have no real clock validity.
    return 'synthetic_scenario' if incident.provenance.origin == 'synthetic' else 'unknown'


def eligible_incidents(incidents: list[Incident], at: datetime) -> tuple[list[Incident], list[dict]]:
    statuses = [{'id': i.id, 'temporal_status': incident_status(i, at),
                 'origin': i.provenance.origin, 'verified_road_closure': False,
                 'starts_at': i.starts_at, 'ends_at': i.ends_at}
                for i in incidents]
    # Missing hours are not a signal of current risk. Keep unknown as evidence.
    active_ids = {s['id'] for s in statuses if s['temporal_status'] in ('active', 'synthetic_scenario')}
    return [i for i in incidents if i.id in active_ids], statuses
