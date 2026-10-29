import pytest
from app.ml import physics


def flat(km=10, kmh=50, elevation=0):
    return [{'distance_m': km * 1000, 'duration_s': km / kmh * 3600, 'rise_m': 0, 'elevation_m': elevation}]


def co2(segments, vehicle='truck', fuel='diesel', load=3000, **kw):
    return physics.estimate(segments, vehicle, fuel, load, **kw)['co2_kg']


def test_fuel_factors_follow_ipcc_and_cea():
    assert physics.FUELS['diesel']['co2_kg_per_unit'] == pytest.approx(2.65, abs=0.01)
    assert physics.FUELS['petrol']['co2_kg_per_unit'] == pytest.approx(2.29, abs=0.01)
    assert physics.FUELS['electric']['co2_kg_per_unit'] == 0.716


def test_breakdown_adds_up_to_total():
    hill = [{'distance_m': 5000, 'duration_s': 600, 'rise_m': 200, 'elevation_m': 900},
            {'distance_m': 5000, 'duration_s': 400, 'rise_m': -200, 'elevation_m': 900}]
    for fuel in physics.FUELS:
        result = physics.estimate(hill, 'van', fuel, 500, temp_c=32, turns=6)
        assert sum(result['co2_breakdown_kg'].values()) == pytest.approx(result['co2_kg'], abs=0.01)


def test_physics_directions():
    assert co2(flat(), load=6000) > co2(flat(), load=1000)                         # heavier burns more
    assert co2(flat(kmh=90)) > co2(flat(kmh=50))                                  # drag grows with v²
    assert co2(flat(), temp_c=35) > co2(flat(), temp_c=22)                        # air-conditioning
    assert co2(flat(), turns=30) > co2(flat())                                    # stop-and-go
    assert co2(flat(), wet_road=True) > co2(flat())                               # wet road
    assert co2(flat(elevation=2000)) < co2(flat(elevation=0))                     # thinner air


def test_climb_is_not_fully_returned_downhill_except_by_regen():
    up_down = [{'distance_m': 5000, 'duration_s': 450, 'rise_m': 250, 'elevation_m': 0},
               {'distance_m': 5000, 'duration_s': 450, 'rise_m': -250, 'elevation_m': 0}]
    level = flat(10, 40)
    assert co2(up_down) > co2(level)                                              # diesel brakes downhill
    ev = physics.estimate(up_down, 'van', 'electric', 500)
    assert ev['co2_breakdown_kg']['regen'] < 0                                    # EV recovers some


def test_realistic_consumption_ranges():
    # Litres per 100 km at 50 km/h, typical load, some junctions: sanity bands from Indian fleet norms.
    truck = physics.estimate(flat(100), 'truck', 'diesel', 5000, turns=40)['fuel']
    van = physics.estimate(flat(100), 'van', 'diesel', 750, turns=40)['fuel']
    assert 12 < truck < 25 and 5 < van < 10


@pytest.mark.parametrize('text,expected', [
    ('Tata Ace', 'van'), ('Mini Truck', 'van'), ('Truck', 'truck'), ('Heavy Truck', 'heavy_truck'),
    ('Electric Van', 'van'), ('Sedan', 'car'), ('Bicycle', None), ('', None)])
def test_vehicle_class_keywords(text, expected):
    assert physics.vehicle_class(text) == expected


def test_fuel_kind_rejects_unmodelled_fuels():
    assert physics.fuel_kind('Diesel') == 'diesel'
    assert physics.fuel_kind('Electric') == 'electric'
    assert physics.fuel_kind('Hybrid') is None


def test_eco_score_is_relative_to_class_reference():
    reference = physics.reference_co2_per_km('truck', 'diesel', 8000)
    assert physics.eco_score(reference * 100, 100, reference) == 50
    assert physics.eco_score(reference * 50, 100, reference) == 75
    assert physics.eco_score(reference * 200, 100, reference) == 0
    assert physics.eco_score(0, 100, reference) == 100
