import app.services.routing as routing
import app.services.trip_workflow as workflow


def fake_routes(*_):
    flat = {'distance_m': 30000, 'duration_s': 2400, 'rise_m': 0, 'elevation_m': 900}
    hilly = {'distance_m': 25000, 'duration_s': 2600, 'rise_m': 300, 'elevation_m': 900}
    return [{'distance_km': 30, 'duration_min': 40, 'pathPoints': [[12.9, 77.5], [12.8, 77.4]],
             'segments': [flat], 'turns': 10, 'elevation_status': 'available'},
            {'distance_km': 25, 'duration_min': 43.3, 'pathPoints': [[12.9, 77.5], [12.8, 77.4]],
             'segments': [hilly], 'turns': 10, 'elevation_status': 'available'}]


def test_ai_fleet_health(client, admin_headers):
    res = client.get('/api/ai/fleet-health', headers=admin_headers)
    assert res.status_code == 200
    assert res.json['model'] == 'physics-road-load-v1'
    assert 'predictive_maintenance' in res.json


def test_model_card_lists_sources_and_factors(client, admin_headers):
    res = client.get('/api/v1/ai/model-card', headers=admin_headers)
    assert res.status_code == 200
    assert res.json['fuels']['electric']['co2_kg_per_unit'] == 0.716
    assert 'truck' in res.json['profiles'] and res.json['data_sources']
    assert client.get('/api/v1/ai/model-card').status_code == 401


def test_model_lab_compares_real_route_physics(client, admin_headers, monkeypatch):
    monkeypatch.setattr(routing, 'get_road_routes', fake_routes)
    monkeypatch.setattr(workflow, 'planning_weather', lambda *_: (30.0, False, 'available'))
    res = client.post('/api/v1/ai/model-lab', headers=admin_headers, json={
        'source': 'Bengaluru', 'destination': 'Hosur', 'vehicle_type': 'truck', 'fuel_type': 'diesel',
        'load_kg': 4000, 'capacity_kg': 8000})
    assert res.status_code == 200, res.json
    flat, hilly = res.json['routes']
    # The shorter route climbs 300 m with a 8.5 t truck: the climb must show up in its breakdown.
    assert hilly['breakdown']['grade'] > 0 and flat['breakdown']['grade'] == 0
    assert hilly['climbM'] == 300 and res.json['weather']['temp_c'] == 30.0


def test_model_lab_rejects_unknown_vehicle(client, admin_headers):
    res = client.post('/api/v1/ai/model-lab', headers=admin_headers, json={'vehicle_type': 'rocket', 'fuel_type': 'diesel'})
    assert res.status_code == 422


def test_driver_score_requires_login(client, admin_headers):
    assert client.post('/api/v1/ai/driver-score', json={}).status_code == 401
    res = client.post('/api/v1/ai/driver-score', headers=admin_headers, json={'harsh_braking': 2, 'idle_minutes': 10})
    assert res.status_code == 200 and res.json['method'].startswith('Rule-based')
