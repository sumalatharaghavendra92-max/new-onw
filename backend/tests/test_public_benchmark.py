"""Protocol tests for the public-data benchmark, with no network access."""
import numpy as np
import pandas as pd
import pytest

from scripts.evaluate_public_data import FEATURES, prepare, scores


def frame():
    return pd.DataFrame([{'id': i, 'year': 2021 if i < 120 else 2023,
                         'displ': 2, 'cylinders': 4, 'drive': 'Front-Wheel Drive',
                         'trany': 'Automatic', 'VClass': 'Compact Cars',
                         'fuelType1': 'Regular Gasoline', 'fuelType2': '',
                         'atvType': np.nan, 'comb08': 30} for i in range(160)])


def test_temporal_split_and_no_target_features():
    train, test = prepare(frame(), 2022)
    assert train.year.max() <= 2022 < test.year.min()
    assert set(train.id).isdisjoint(test.id)
    assert len(train) == 120 and len(test) == 40
    assert train.target_l_per_100km.iloc[0] == pytest.approx(235.214583 / 30)
    assert not {'comb08', 'city08', 'highway08', 'co2', 'fuelCost08'} & set(FEATURES)


def test_electric_dual_fuel_invalid_mpg_and_duplicate_excluded():
    data = frame()
    data.loc[0, 'fuelType1'] = 'Electricity'
    data.loc[1, 'fuelType2'] = 'Electricity'
    data.loc[2, 'comb08'] = 0
    data = pd.concat([data, data.iloc[[4]]])
    train, _ = prepare(data, 2022)
    assert len(train) == 117


def test_fail_closed_missing_columns_and_small_test():
    with pytest.raises(ValueError, match='Missing columns'):
        prepare(frame().drop(columns=['comb08']), 2022)
    with pytest.raises(ValueError, match='Insufficient'):
        prepare(frame(), 2025)


def test_signed_bias_and_error_units():
    metrics = scores(np.array([2., 4.]), np.array([1., 3.]))
    assert metrics['mae_l_per_100km'] == 1
    assert metrics['bias_predicted_minus_actual_l_per_100km'] == -1

