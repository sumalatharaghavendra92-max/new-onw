from types import SimpleNamespace
import pytest
from app.ml import hybrid, physics
import app.services.trip_workflow as workflow


def city_trip():
    seg = [{'distance_m': 12000, 'duration_s': 1500, 'rise_m': 20, 'elevation_m': 900}]
    return physics.estimate(seg, 'van', 'petrol', 300, temp_c=28, turns=18)


def test_applies_only_where_it_was_trained():
    assert hybrid.applies('van', 'petrol') and hybrid.applies('car', 'petrol')
    assert not hybrid.applies('truck', 'diesel')
    assert not hybrid.applies('van', 'diesel')
    assert not hybrid.applies('heavy_truck', 'petrol')


def test_correction_raises_city_fuel_and_keeps_breakdown_consistent():
    base = city_trip()
    corrected, ratio = hybrid.apply(base, 28, 25)
    assert ratio is not None and 0.5 < ratio < 3
    assert corrected['co2_kg'] == pytest.approx(base['co2_kg'] * ratio, rel=0.01)
    assert sum(corrected['co2_breakdown_kg'].values()) == pytest.approx(corrected['co2_kg'], abs=0.02)


def test_trip_estimate_labels_which_model_was_used(monkeypatch):
    route = {'distance_km': 12, 'duration_min': 25, 'turns': 18, 'pathPoints': [[12.9, 77.5]],
             'segments': [{'distance_m': 12000, 'duration_s': 1500, 'rise_m': 20, 'elevation_m': 900}],
             'elevation_status': 'available'}
    weather = (28.0, False, 'available')
    van = SimpleNamespace(type='Van', fuel_type='Petrol', load_capacity_kg=1000, calibration=None)
    truck = SimpleNamespace(type='Truck', fuel_type='Diesel', load_capacity_kg=8000, calibration=None)
    van_est = workflow.estimate(route, van, 300, weather)
    truck_est = workflow.estimate(route, truck, 3000, weather)
    assert van_est['prediction_mode'].startswith('Hybrid') and van_est['hybrid_correction']
    assert truck_est['prediction_mode'].startswith('Physics') and truck_est['hybrid_correction'] is None
    assert van_est['uncertainty_pct'] == 15.0
