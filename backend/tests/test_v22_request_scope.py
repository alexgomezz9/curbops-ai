from app.services.request_scope import requests_whole_fleet, resolve_avoidance_scope


def test_fleet_intent_ignores_stale_map_selection():
    msg='Review all fleet routes and find alternatives around nearby municipal disruption zones.'
    assert requests_whole_fleet(msg)
    assert resolve_avoidance_scope(msg,'V-01','2026/883')==('ALL','')


def test_explicit_incident_can_scope_whole_fleet():
    msg='For every van avoid incident 2026/883 if possible.'
    assert resolve_avoidance_scope(msg,'V-03','2026/883')==('ALL','2026/883')


def test_single_vehicle_does_not_reuse_unmentioned_incident():
    msg='Avoid risks near V-02.'
    assert resolve_avoidance_scope(msg,'V-02','2026/1827')==('V-02','')


def test_spanish_fleet_and_casefolded_identifiers():
    msg='Revisa toda la flota y evita el riesgo del aviso SIM-ROADWORKS.'
    assert resolve_avoidance_scope(msg,'V-01','sim-roadworks')==('ALL','sim-roadworks')


def test_all_hazards_on_one_vehicle_not_all_fleet():
    assert not requests_whole_fleet('Avoid all incidents near V-02')
    assert resolve_avoidance_scope('Avoid all incidents near V-02','V-02','2026/883') == ('V-02','')
