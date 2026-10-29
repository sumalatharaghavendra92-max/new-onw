import pytest
from flask_jwt_extended import create_access_token
from app import db
from app.models import (User, UserRole, Driver, ApprovalStatus, Vehicle, Notification, Trip, TripStatus,
                        DispatchedRound)
from tests.test_rounds import providers, POINTS  # noqa: F401 (fixture)


def person(name, phone, role=UserRole.driver):
    user = User(name=name, email=f'{phone}@example.test', phone=phone, role=role, password_hash='x')
    db.session.add(user); db.session.flush()
    return user


@pytest.fixture
def fleet(app):
    """One admin, two approved drivers with their own trucks, and a truck nobody drives."""
    admin = person('Admin', '5550000001', UserRole.admin)
    out = {'admin': {'Authorization': f'Bearer {create_access_token(identity=str(admin.id))}'}, 'drivers': []}
    for i in range(2):
        user = person(f'Driver {i}', f'555000010{i}')
        driver = Driver(user_id=user.id, approval_status=ApprovalStatus.approved)
        db.session.add(driver); db.session.flush()
        vehicle = Vehicle(vehicle_no=f'DSP-{i}', type='Truck', fuel_type='Diesel', load_capacity_kg=6000,
                          assigned_driver_id=driver.id)
        db.session.add(vehicle); db.session.flush()
        out['drivers'].append({'headers': {'Authorization': f'Bearer {create_access_token(identity=str(user.id))}'},
                               'vehicle_id': vehicle.id, 'user_id': user.id, 'driver_id': driver.id})
    spare = Vehicle(vehicle_no='DSP-SPARE', type='Truck', fuel_type='Diesel', load_capacity_kg=6000)
    db.session.add(spare); db.session.commit()
    out['spare_id'] = spare.id
    return out


def body(vehicle_id, key='greenest'):
    return {'vehicle_id': vehicle_id, 'depot': POINTS[0], 'plan_key': key, 'depot_label': 'Peenya',
            'stops': [{'place': POINTS[1], 'drop_kg': 300, 'label': 'A'},
                      {'place': POINTS[2], 'drop_kg': 2500, 'label': 'B'},
                      {'place': POINTS[3], 'drop_kg': 900, 'label': 'C'}]}


def dispatch(client, fleet, i=0, key='greenest'):
    res = client.post('/api/v1/rounds/dispatch', headers=fleet['admin'], json=body(fleet['drivers'][i]['vehicle_id'], key))
    assert res.status_code == 201, res.json
    return res.json['round']


def test_dispatch_replans_on_server_and_notifies_driver(client, fleet, providers):
    preview = client.post('/api/v1/rounds/plan', headers=fleet['admin'], json=body(fleet['drivers'][0]['vehicle_id'])).json
    greenest = next(p for p in preview['plans'] if p['key'] == 'greenest')
    sent = body(fleet['drivers'][0]['vehicle_id'])
    sent['co2_kg'] = 0.001  # client numbers are ignored
    rnd = client.post('/api/v1/rounds/dispatch', headers=fleet['admin'], json=sent).json['round']
    assert rnd['status'] == 'planned' and rnd['plan_key'] == 'greenest'
    assert [s['index'] for s in rnd['stops']] == greenest['order']
    assert rnd['co2_kg'] == greenest['co2_kg'] and rnd['load_now_kg'] == 3700
    note = Notification.query.filter_by(user_id=fleet['drivers'][0]['user_id'], type='round_assigned').one()
    assert '3 stops from Peenya' in note.message


def test_plan_key_is_respected_and_validated(client, fleet, providers):
    fastest = dispatch(client, fleet, 1, 'fastest')
    assert fastest['plan_key'] == 'fastest'
    res = client.post('/api/v1/rounds/dispatch', headers=fleet['admin'], json=body(fleet['drivers'][0]['vehicle_id'], 'cheapest'))
    assert res.status_code == 422


def test_dispatch_conflicts(client, fleet, providers):
    assert client.post('/api/v1/rounds/dispatch', headers=fleet['admin'], json=body(fleet['spare_id'])).status_code == 409
    dispatch(client, fleet)
    again = client.post('/api/v1/rounds/dispatch', headers=fleet['admin'], json=body(fleet['drivers'][0]['vehicle_id']))
    assert again.status_code == 409
    d = fleet['drivers'][1]
    db.session.add(Trip(driver_id=d['driver_id'], vehicle_id=d['vehicle_id'], source='A', destination='B',
                        status=TripStatus.in_progress))
    db.session.commit()
    assert client.post('/api/v1/rounds/dispatch', headers=fleet['admin'], json=body(d['vehicle_id'])).status_code == 409
    assert client.post('/api/v1/rounds/dispatch', headers=fleet['drivers'][0]['headers'],
                       json=body(fleet['drivers'][0]['vehicle_id'])).status_code == 403


def test_driver_lifecycle_trains_calibration(client, fleet, providers):
    rnd = dispatch(client, fleet)
    me, other = fleet['drivers'][0]['headers'], fleet['drivers'][1]['headers']
    mine = client.get('/api/v1/rounds/mine', headers=me).json
    assert mine['active'] is None and mine['upcoming'][0]['id'] == rnd['id']
    assert mine['vehicle']['calibration'] == {'factor': 1.0, 'trips': 0, 'rejected': 0, 'uncertainty_pct': 25.0}
    assert client.get(f"/api/v1/rounds/{rnd['id']}", headers=other).status_code == 403
    assert client.post(f"/api/v1/rounds/{rnd['id']}/start", headers=other).status_code == 403
    assert client.post(f"/api/v1/rounds/{rnd['id']}/stops/0/deliver", headers=me).status_code == 409

    started = client.post(f"/api/v1/rounds/{rnd['id']}/start", headers=me).json['round']
    assert started['status'] == 'in_progress' and started['started_at']
    first = started['stops'][0]
    after = client.post(f"/api/v1/rounds/{rnd['id']}/stops/0/deliver", headers=me).json['round']
    assert after['delivered_count'] == 1 and after['load_now_kg'] == 3700 - first['drop_kg']
    twice = client.post(f"/api/v1/rounds/{rnd['id']}/stops/0/deliver", headers=me).json['round']
    assert twice['stops'][0]['delivered_at'] == after['stops'][0]['delivered_at']
    assert client.post(f"/api/v1/rounds/{rnd['id']}/stops/9/deliver", headers=me).status_code == 404
    assert client.post(f"/api/v1/rounds/{rnd['id']}/log", headers=me, json={'lat': 12.95, 'lng': 77.6}).status_code == 201
    assert client.post(f"/api/v1/rounds/{rnd['id']}/log", headers=me, json={'lat': 99, 'lng': 77.6}).status_code == 422

    fleet_view = client.get('/api/v1/admin/fleet', headers=fleet['admin']).json
    assert fleet_view['rounds'][0]['last_location']['lat'] == 12.95 and 'trips' in fleet_view

    physics_fuel = db.session.get(DispatchedRound, rnd['id']).plan['physics_fuel']
    done = client.post(f"/api/v1/rounds/{rnd['id']}/end", headers=me, json={'actual_fuel_l': physics_fuel * 1.1}).json['round']
    assert done['status'] == 'completed' and done['calibration_result'] == 'learned' and done['delivered_count'] == 1
    assert client.post(f"/api/v1/rounds/{rnd['id']}/end", headers=me, json={}).json['round']['status'] == 'completed'
    assert db.session.get(Vehicle, fleet['drivers'][0]['vehicle_id']).calibration.trips == 1
    assert client.get('/api/v1/rounds/mine', headers=me).json['recent'][0]['id'] == rnd['id']
    assert client.post(f"/api/v1/rounds/{rnd['id']}/cancel", headers=me).status_code == 409


def test_implausible_fuel_is_rejected(client, fleet, providers):
    rnd = dispatch(client, fleet)
    me = fleet['drivers'][0]['headers']
    client.post(f"/api/v1/rounds/{rnd['id']}/start", headers=me)
    done = client.post(f"/api/v1/rounds/{rnd['id']}/end", headers=me, json={'actual_fuel_l': 900}).json['round']
    assert done['calibration_result'] == 'rejected'
    assert db.session.get(Vehicle, fleet['drivers'][0]['vehicle_id']).calibration.trips == 0


def test_cancel_and_admin_list(client, fleet, providers):
    a, b = dispatch(client, fleet, 0), dispatch(client, fleet, 1)
    assert client.post(f"/api/v1/rounds/{a['id']}/cancel", headers=fleet['admin']).json['round']['status'] == 'cancelled'
    planned = client.get('/api/v1/rounds?status=planned', headers=fleet['admin']).json['rounds']
    assert [r['id'] for r in planned] == [b['id']]
    assert len(client.get('/api/v1/rounds', headers=fleet['admin']).json['rounds']) == 2
    assert client.get('/api/v1/rounds?status=lost', headers=fleet['admin']).status_code == 422
    assert client.get('/api/v1/rounds', headers=fleet['drivers'][0]['headers']).status_code == 403
    assert client.get('/api/v1/rounds/999', headers=fleet['admin']).status_code == 404
