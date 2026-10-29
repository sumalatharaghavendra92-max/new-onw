import math
import random
import time

import pytest
from flask_jwt_extended import create_access_token

from app import db
from app.models import User, UserRole
from app.services import simulation


def fake_matrix(points):
    """Road ≈ 1.3 × straight line at 30 km/h; no network."""
    metres = [[max(simulation._haversine_m(a, b) * 1.3, 1.0) for b in points] for a in points]
    return [[m / (30 / 3.6) for m in row] for row in metres], metres


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(simulation, 'osrm_matrix', fake_matrix)
    monkeypatch.setattr(simulation, 'osrm_path', lambda pts: [list(p) for p in pts])
    monkeypatch.setattr(simulation, 'get_elevations', lambda pts: [900.0 + (i % 7) * 3 for i in range(len(pts))])
    monkeypatch.setattr(simulation, 'get_live_context',
                        lambda *_: {'status': 'available', 'current': {'temperature_2m': 27.0, 'precipitation': 0.0}})
    monkeypatch.setattr(simulation, 'OSRM_INTERVAL_S', 0)
    simulation.reset()
    yield
    simulation.reset()


def build(seed=3, trucks=40, orders=200):
    return simulation.build_scenario(trucks=trucks, orders=orders, seed=seed,
                                     progress=lambda *_: None, throttled=lambda call: call())


def test_same_seed_gives_same_day():
    a, b = build(), build()
    assert [r['planned'] for r in a['rounds']] == [r['planned'] for r in b['rounds']]
    assert [r['executed'] for r in a['rounds']] == [r['executed'] for r in b['rounds']]


def test_every_order_assigned_once_and_capacity_respected():
    sc = build()
    delivered = [s['id'] for r in sc['rounds'] for s in r['stops']]
    assert len(delivered) == len(set(delivered))
    assert sorted(delivered + sc['unassigned_orders'] + sc['unroutable_orders']) == [o['id'] for o in sc['orders']]
    assert sc['unassigned_orders'] == []
    for r in sc['rounds']:
        truck = sc['trucks'][r['truck_id'] - 1]
        assert sum(s['drop_kg'] for s in r['stops']) <= truck['capacity_kg']
        assert 1 <= len(r['stops']) <= simulation.MAX_STOPS
    per_truck = {}
    for r in sc['rounds']:
        per_truck[r['truck_id']] = per_truck.get(r['truck_id'], 0) + 1
    assert max(per_truck.values()) <= 2


def test_traffic_makes_rounds_slower_and_dirtier():
    sc = build()
    r = sc['rounds'][0]
    truck = sc['trucks'][r['truck_id'] - 1]
    pts = [simulation.DEPOTS[r['depot']]] + [(s['lat'], s['lng']) for s in r['stops']]
    matrix = fake_matrix(pts)
    elev = [900.0] * len(pts)
    weather = {'temp_c': 27.0, 'wet_road': False}
    night = simulation.plan_and_execute(random.Random(1), truck, r['stops'], matrix, elev, weather, 3 * 60)
    peak = simulation.plan_and_execute(random.Random(1), truck, r['stops'], matrix, elev, weather, 18 * 60)
    assert peak['return_min'] - 18 * 60 > night['return_min'] - 3 * 60
    assert peak['executed']['co2_kg'] > night['executed']['co2_kg']
    assert peak['planned'] == night['planned']           # the planner does not see traffic


def test_traffic_table_covers_the_whole_day():
    assert all(simulation.traffic_multiplier(m) >= 1.0 for m in range(0, 1440, 15))
    assert simulation.traffic_multiplier(9 * 60) == 1.7


def test_calibration_learns_hidden_factor_and_rejects_bad_reports():
    cal = build(trucks=60, orders=300)['calibration']
    first, last = cal['series'][0]['mean_abs_error'], cal['series'][-1]['mean_abs_error']
    assert last < first / 2
    assert last < cal['no_learning_error']
    assert cal['rejected_reports'] > 0


def test_positions_follow_the_clock():
    sc = build()
    with simulation._lock:
        simulation._state.update(phase='ready', scenario=sc)
    early = simulation.state_at(simulation.DAY_START)
    assert all(t['status'] == 'idle' for t in early['trucks'])
    late = simulation.state_at(23 * 60)
    assert late['kpis']['delivered'] == sum(len(r['stops']) for r in sc['rounds'])
    assert all(t['status'] in ('idle', 'done') for t in late['trucks'])
    assert late['label'] == 'SIMULATION'
    middle = simulation.state_at(10 * 60)
    assert middle['kpis']['on_road'] > 0


@pytest.fixture
def driver_headers(app):
    user = User(email='sim-driver@example.test', phone='5550001234', name='Driver', role=UserRole.driver, password_hash='x')
    db.session.add(user)
    db.session.commit()
    return {'Authorization': f'Bearer {create_access_token(identity=str(user.id))}'}


def test_sandbox_endpoints_removed(client, admin_headers):
    for path in ('status', 'state', 'summary'):
        assert client.get('/api/v1/sim/' + path, headers=admin_headers).status_code == 404
    assert client.post('/api/v1/sim/start', headers=admin_headers, json={}).status_code == 404
