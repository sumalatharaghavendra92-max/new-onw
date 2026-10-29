from types import SimpleNamespace
from app.services.evidence import evidence_for
from app.services.decision_policy import choose_route


DETAILS = {'temp_c': 25.0, 'wet_road': False, 'weather_status': 'available', 'elevation_status': 'available',
           'turns': 4, 'uncertainty_pct': 25.0, 'calibration_trips': 0}


def test_unknown_vehicle_and_fuel_are_out_of_domain():
    result = evidence_for(SimpleNamespace(type='Spaceship', fuel_type='Hybrid'), 300, DETAILS, 'Physics')
    assert result['within_documented_domain'] is False
    assert len([l for l in result['limitations'] if 'not modelled' in l or 'no physics profile' in l]) == 2


def test_missing_terrain_and_weather_are_disclosed_not_hidden():
    details = dict(DETAILS, elevation_status='unavailable', weather_status='unavailable')
    result = evidence_for(SimpleNamespace(type='Van', fuel_type='Diesel'), 200, details, 'Physics')
    assert result['within_documented_domain']
    assert any('flat' in l for l in result['limitations'])
    assert any('Weather unavailable' in l for l in result['limitations'])
    assert 'not yet calibrated' in result['confidence']
    assert result['truck_restrictions_verified'] is False


def test_unsupported_evidence_withholds_eco_ranking():
    candidates = [{'distance_km': 30, 'duration_min': 40}, {'distance_km': 25, 'duration_min': 44}]
    estimates = [{'predicted_co2_kg': c, 'evidence': {'within_documented_domain': False}} for c in (10, 5)]
    _, best, policy = choose_route(candidates, estimates)
    assert best == 0 and policy['eco_ranking_withheld']


def test_empty_feedback_has_no_invented_accuracy(client, admin_headers):
    report = client.get('/api/v1/admin/learning', headers=admin_headers)
    assert report.status_code == 200
    assert report.json['mae_l'] is None
    assert report.json['coverage_percent'] == 0
    assert report.json['automatic_retraining'] is False
    assert client.get('/api/v1/admin/learning').status_code == 401
