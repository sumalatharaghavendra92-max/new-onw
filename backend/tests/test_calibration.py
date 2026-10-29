import pytest
from app import db
from app.models import Vehicle
from app.services.calibration import learn_from_trip, factor_and_uncertainty, DEFAULT_UNCERTAINTY_PCT
from tests.test_workflow import drivers, routes, plan, start  # noqa: F401 (fixtures and helpers)


def vehicle():
    v = Vehicle(vehicle_no='CAL-1', type='Truck', fuel_type='Diesel', load_capacity_kg=8000)
    db.session.add(v)
    db.session.commit()
    return v


def test_uncalibrated_vehicle_uses_class_defaults(app):
    assert factor_and_uncertainty(None) == (1.0, DEFAULT_UNCERTAINTY_PCT)


def test_factor_moves_towards_reported_ratio_with_shrinkage(app):
    v = vehicle()
    for reported in (12, 12.5, 11.5, 12, 12):
        assert learn_from_trip(v, 10, reported) == 'learned'
    db.session.commit()
    factor, uncertainty = factor_and_uncertainty(v.calibration)
    assert 1.0 < factor < 1.2          # shrunk from the observed 1.2 towards 1.0
    assert uncertainty < DEFAULT_UNCERTAINTY_PCT


def test_implausible_reports_are_rejected_not_learned(app):
    v = vehicle()
    assert learn_from_trip(v, 10, 80) == 'rejected'
    assert learn_from_trip(v, 10, None) == 'skipped'
    db.session.commit()
    assert v.calibration.trips == 0 and v.calibration.rejected == 1
    assert factor_and_uncertainty(v.calibration)[0] == 1.0


def test_completed_trip_with_reported_fuel_trains_the_vehicle(client, drivers, monkeypatch):
    import app.blueprints.trips.routes as endpoints
    monkeypatch.setattr(endpoints, 'estimate', lambda r, *_: {
        'predicted_fuel_l': r['distance_km'] / 10, 'predicted_co2_kg': r['distance_km'], 'physics_fuel': r['distance_km'] / 10,
        'fuel_unit': 'L', 'eco_score': 60, 'prediction_mode': 'Test fixture'})
    monkeypatch.setattr(endpoints, 'get_road_routes', lambda *_: [
        {'distance_km': 30, 'duration_min': 40, 'pathPoints': [[12.9, 77.5], [12.8, 77.4]]}])
    trip = plan(client, drivers[0])
    start(client, drivers[0], trip)
    res = client.post(f'/api/v1/trips/{trip["id"]}/end', headers=drivers[0], json={'actual_fuel_l': 3.3})
    assert res.status_code == 200
    v = db.session.get(Vehicle, 1)
    assert v.calibration.trips == 1 and v.calibration.ratio_sum == pytest.approx(1.1)
