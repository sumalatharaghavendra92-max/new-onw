"""Synthetic checks of the VED validation maths; no network or real data needed."""
import numpy as np
import pandas as pd
import pytest

from scripts.validate_ved import (chronological_split, filter_reason, fuel_litres_per_second,
                                  integrate_trip, calibration_factor, metrics)


def samples(ms, speed_kmh=36.0, maf=5.0, trims=0.0):
    n = len(ms)
    return pd.DataFrame({'ms': ms, 'speed_kmh': [speed_kmh] * n, 'maf': [maf] * n, 'oat': [20.0] * n,
                         'lat': np.linspace(42.27, 42.30, n), 'lng': np.linspace(-83.74, -83.70, n),
                         'stft1': [trims] * n, 'stft2': [np.nan] * n, 'ltft1': [0.0] * n, 'ltft2': [np.nan] * n})


def test_maf_to_litres_uses_stoichiometry_trims_and_density():
    assert fuel_litres_per_second(14.7 * 745, 0.0, 0.0) == pytest.approx(1.0)
    assert fuel_litres_per_second(14.7 * 745, 10.0, np.nan) == pytest.approx(1.1)


def test_gaps_and_duplicate_timestamps_are_not_integrated():
    # 1 s steps for 100 s, one duplicate, then a 60 s gap, then 1 s steps again.
    ms = list(range(0, 101_000, 1000)) + [100_000] + list(range(160_000, 261_000, 1000))
    trip = integrate_trip(samples(ms))
    assert trip['duration_s'] == pytest.approx(200)          # the 60 s gap is excluded
    assert trip['distance_m'] == pytest.approx(200 * 10)     # 36 km/h = 10 m/s
    assert trip['fuel_l'] == pytest.approx(200 * fuel_litres_per_second(5.0, 0, 0))


def test_missing_maf_is_imputed_at_the_trip_rate_and_reported():
    frame = samples(list(range(0, 301_000, 1000)))
    frame.loc[:29, 'maf'] = np.nan
    trip = integrate_trip(frame)
    assert trip['coverage'] == pytest.approx(0.9)
    assert trip['fuel_l'] == pytest.approx(300 * fuel_litres_per_second(5.0, 0, 0))


def test_filters():
    long_trip = integrate_trip(samples(list(range(0, 301_000, 1000))))   # 3 km, 5 min
    assert filter_reason(long_trip) is None
    assert filter_reason(integrate_trip(samples(list(range(0, 100_000, 1000))))) == 'shorter_than_2km'
    assert filter_reason(integrate_trip(samples(list(range(0, 301_000, 1000)), maf=200.0))) == 'implausible_l_per_100km'


def test_chronological_split_never_scores_a_trip_older_than_a_learning_trip():
    rows = [{'vehicle': v, 'trip': i, 'day': float(i), 'start_ms': 0.0} for v in (1, 2) for i in range(10)]
    learn, score = chronological_split(pd.DataFrame(rows).sample(frac=1, random_state=0))
    for vehicle in (1, 2):
        assert learn[learn.vehicle == vehicle].day.max() < score[score.vehicle == vehicle].day.min()
    assert len(learn) == 6 and len(score) == 14


def test_calibration_matches_app_rule_and_gate():
    assert calibration_factor([]) == 1.0
    assert calibration_factor([5.0, 5.0]) == 1.0                  # implausible ratios rejected
    assert 1.0 < calibration_factor([1.2] * 5) < 1.2               # shrunk towards 1


def test_metrics_signed_bias():
    result = metrics([10, 10], [11, 9])
    assert result['mae_pct'] == 10 and result['bias_pct'] == 0


def test_hybrid_features_use_only_pre_departure_inputs_in_order():
    from scripts.validate_ved import HYBRID_FEATURES, hybrid_features
    frame = pd.DataFrame({'distance_km': [10.0], 'duration_min': [20.0], 'turns': [5], 'climb_m': [40.0],
                          'temp_c': [18.0], 'mass_kg': [1500.0], 'physics': [0.8],
                          'actual_l': [99.0], 'vehicle': [1]})          # target-side columns must be ignored
    features = hybrid_features(frame)
    assert list(features.columns) == HYBRID_FEATURES
    row = features.iloc[0]
    assert row.planned_speed_kmh == 30 and row.turns_per_km == 0.5 and row.climb_m_per_km == 4
    assert row.physics_l_per_100km == pytest.approx(8.0)
    assert 'actual_l' not in features.columns
