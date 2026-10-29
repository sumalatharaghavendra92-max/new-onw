import pytest
from app.services.decision_policy import choose_route


def choose(times, emissions):
    return choose_route([{'duration_min': t, 'distance_km': 20} for t in times],
                        [{'predicted_co2_kg': c} for c in emissions])


def test_negligible_saving_keeps_fastest():
    assert choose([40, 44], [5, 4.99])[1] == 0


def test_material_saving_within_time_budget():
    fastest, best, explanation = choose([40, 44, 60], [5, 4, 3])
    assert (fastest, best) == (0, 1)
    assert explanation['uncertainty_calibrated'] is False


def test_zero_emissions_ties_choose_fastest():
    assert choose([44, 40], [0, 0])[1] == 1


@pytest.mark.parametrize('value', [-1, float('nan'), float('inf')])
def test_invalid_predictions_are_rejected(value):
    with pytest.raises(ValueError): choose([40], [value])
