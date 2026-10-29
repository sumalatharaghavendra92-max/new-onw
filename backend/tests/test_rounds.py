import itertools
import math
import random

import pytest
from flask_jwt_extended import create_access_token
from app import db
from app.models import User, UserRole, Driver, ApprovalStatus, Vehicle
from app.services import rounds
from app.services.routing import ProviderUnavailable


def make_round(n, seed, back=True):
    rng = random.Random(seed)
    pts = [(rng.uniform(0, 20), rng.uniform(0, 20)) for _ in range(n + 1)]
    dist = [[math.dist(a, b) * 1000 for b in pts] for a in pts]
    dur = [[d / rng.uniform(6, 14) if d else 0 for d in row] for row in dist]
    elev = [rng.uniform(800, 950) for _ in pts]
    drops = [rng.uniform(50, 800) for _ in range(n)]
    return rounds.Round(dur, dist, elev, drops, sum(drops) + 100, 'truck', 'diesel', 28, False, back)


def brute(model, w, ts, cs):
    def score(order):
        r = model.evaluate(order)
        return w * r['co2_kg'] / cs + (1 - w) * r['duration_min'] * 60 / ts
    return min(score(list(p)) for p in itertools.permutations(range(model.n)))


@pytest.mark.parametrize('seed', [1, 2, 3])
@pytest.mark.parametrize('back', [True, False])
def test_held_karp_matches_brute_force(seed, back):
    model = make_round(6, seed, back)
    for w in (0.0, 0.5, 1.0):
        order = model.solve(w, 1000.0, 10.0)
        r = model.evaluate(order)
        got = w * r['co2_kg'] / 10.0 + (1 - w) * r['duration_min'] * 60 / 1000.0
        # evaluate() rounds totals, so compare with a tolerance.
        assert got == pytest.approx(brute(model, w, 1000.0, 10.0), abs=2e-3)


def test_greenest_drops_heaviest_first():
    # Two stops equidistant from the depot and each other: travel time ties, so
    # only the carried load separates the orders.
    dist = [[0, 10000, 10000], [10000, 0, 10000], [10000, 10000, 0]]
    dur = [[0 if d == 0 else 900 for d in row] for row in dist]
    model = rounds.Round(dur, dist, [900, 900, 900], [200, 3000], 3200, 'truck', 'diesel', 25, False, True)
    assert model.solve(1.0, 1.0, 1.0) == [1, 0]
    heavy_first, light_first = model.evaluate([1, 0]), model.evaluate([0, 1])
    assert heavy_first['duration_min'] == light_first['duration_min']
    assert heavy_first['co2_kg'] < light_first['co2_kg']


# ── Endpoint ──────────────────────────────────────────────────────────────────

POINTS = ['12.9716,77.5946', '12.9352,77.6245', '12.9719,77.6412', '13.0358,77.5970']


def fake_table(points):
    dist = [[math.dist(a, b) * 111_000 for b in points] for a in points]
    return [[d / 8 for d in row] for row in dist], dist


@pytest.fixture
def providers(monkeypatch):
    monkeypatch.setattr(rounds, 'osrm_table', fake_table)
    monkeypatch.setattr(rounds, 'osrm_path', lambda pts: [list(p) for p in pts])
    monkeypatch.setattr(rounds, 'get_elevations', lambda pts: [900.0 + i * 5 for i in range(len(pts))])
    monkeypatch.setattr(rounds, 'get_live_context', lambda *_: {
        'status': 'available', 'current': {'temperature_2m': 29.0, 'precipitation': 0.0}})
    return monkeypatch


@pytest.fixture
def driver_headers(app):
    user = User(name='Round Driver', email='round@example.test', phone='5551112222', role=UserRole.driver, password_hash='x')
    db.session.add(user); db.session.flush()
    driver = Driver(user_id=user.id, approval_status=ApprovalStatus.approved)
    db.session.add(driver); db.session.flush()
    db.session.add(Vehicle(vehicle_no='RND-1', type='Truck', fuel_type='Diesel', load_capacity_kg=6000, assigned_driver_id=driver.id))
    db.session.commit()
    return {'Authorization': f'Bearer {create_access_token(identity=str(user.id))}'}


def body(**extra):
    stops = [{'place': p, 'drop_kg': kg} for p, kg in zip(POINTS[1:], (300, 2500, 700))]
    return {'depot': POINTS[0], 'stops': stops, **extra}


def test_driver_round_has_three_consistent_plans(client, driver_headers, providers):
    res = client.post('/api/v1/rounds/plan', headers=driver_headers, json=body())
    assert res.status_code == 200, res.json
    data = res.json
    assert [p['key'] for p in data['plans']] == ['fastest', 'greenest', 'balanced']
    assert data['vehicle']['class'] == 'truck' and data['elevation_status'] == 'available'
    for plan in data['plans']:
        assert sorted(plan['order']) == [0, 1, 2]
        assert plan['co2_kg'] == pytest.approx(sum(l['co2_kg'] for l in plan['legs']), abs=0.01)
        assert plan['duration_min'] == pytest.approx(sum(l['duration_min'] for l in plan['legs']), abs=0.3)
        assert plan['legs'][0]['from'] == 'depot' and plan['legs'][-1]['to'] == 'depot'
        assert plan['legs'][0]['load_kg'] == 3500
    fastest, greenest = data['plans'][0], data['plans'][1]
    assert greenest['co2_kg'] <= fastest['co2_kg'] and fastest['duration_min'] <= greenest['duration_min']
    assert data['pareto'][0]['weight'] == 0.0


def test_admin_must_choose_vehicle(client, admin_headers, providers):
    assert client.post('/api/v1/rounds/plan', headers=admin_headers, json=body()).status_code == 422
    vehicle = Vehicle(vehicle_no='RND-ADMIN', type='Van', fuel_type='Electric', load_capacity_kg=4000)
    db.session.add(vehicle); db.session.commit()
    res = client.post('/api/v1/rounds/plan', headers=admin_headers, json=body(vehicle_id=vehicle.id))
    assert res.status_code == 200 and res.json['vehicle']['fuel'] == 'electric'


def test_validation_and_capacity(client, driver_headers, providers):
    too_many = {'depot': POINTS[0], 'stops': [{'place': f'12.{i:02d},77.5', 'drop_kg': 1} for i in range(11)]}
    assert client.post('/api/v1/rounds/plan', headers=driver_headers, json=too_many).status_code == 422
    assert client.post('/api/v1/rounds/plan', headers=driver_headers, json=body(start_load_kg=9000)).status_code == 409
    assert client.post('/api/v1/rounds/plan', headers=driver_headers, json=body(start_load_kg=100)).status_code == 422
    dup = {'depot': POINTS[0], 'stops': [{'place': POINTS[0], 'drop_kg': 1}]}
    assert client.post('/api/v1/rounds/plan', headers=driver_headers, json=dup).status_code == 422


def test_provider_failures(client, driver_headers, providers):
    providers.setattr(rounds, 'get_elevations', lambda pts: None)
    res = client.post('/api/v1/rounds/plan', headers=driver_headers, json=body())
    assert res.status_code == 200 and res.json['elevation_status'] == 'unavailable'
    assert any('Terrain unknown' in a for a in res.json['assumptions'])

    def down(points):
        raise ProviderUnavailable('Routing service could not connect all stops.')
    providers.setattr(rounds, 'osrm_table', down)
    assert client.post('/api/v1/rounds/plan', headers=driver_headers, json=body()).status_code == 503
