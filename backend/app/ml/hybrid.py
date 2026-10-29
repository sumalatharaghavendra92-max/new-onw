"""ML correction on top of the physics model, trained on real car trips (VED).

The physics model cannot see stop-and-go driving before a trip, so on real
cars it predicts too little fuel. A gradient-boosted model learned how far off
it is (log of actual / physics) from 6,951 real trips by 127 cars, using only
inputs known before departure. On 54 cars it never saw, physics alone was off
by 37% on average; physics × this correction by 14%.

It was trained on US petrol cars and light trucks only, so it is used only for
petrol cars and vans. Everything else keeps physics + per-vehicle calibration.
"""
import json
import logging
import math
import warnings
from functools import lru_cache
from pathlib import Path

MODEL_PATH = Path(__file__).parent / 'models' / 'ved_residual.joblib'
META_PATH = Path(__file__).parent / 'models' / 'ved_residual.json'
APPLIES_TO_CLASSES = ('car', 'van')
APPLIES_TO_FUELS = ('petrol',)


@lru_cache(maxsize=1)
def _load():
    """(model, feature names) or (None, None) if the files are missing or incompatible."""
    try:
        import joblib
        from sklearn.exceptions import InconsistentVersionWarning
        meta = json.loads(META_PATH.read_text(encoding='utf-8'))
        with warnings.catch_warnings():
            warnings.simplefilter('error', InconsistentVersionWarning)
            model = joblib.load(MODEL_PATH)
        return model, meta['features']
    except Exception as exc:  # missing file, wrong sklearn version, corrupt pickle
        logging.getLogger(__name__).warning('Hybrid correction unavailable (%s); using physics only.', type(exc).__name__)
        return None, None


def applies(vehicle_key, fuel_key):
    return vehicle_key in APPLIES_TO_CLASSES and fuel_key in APPLIES_TO_FUELS and _load()[0] is not None


def correction(physics_result, temp_c, duration_min):
    """Multiplier for the physics fuel and CO2, or None when it cannot be computed."""
    model, features = _load()
    distance_km = physics_result['distance_km']
    if model is None or distance_km <= 0 or physics_result['fuel'] <= 0:
        return None
    row = {
        'distance_km': distance_km,
        'planned_speed_kmh': physics_result['avg_speed_kmh'],
        'turns_per_km': physics_result['turns'] / distance_km,
        'climb_m_per_km': physics_result['climb_m'] / distance_km,
        'temp_c': temp_c,
        'mass_kg': physics_result['mass_kg'],
        'physics_l_per_100km': physics_result['fuel'] / distance_km * 100,
        'duration_min': duration_min,
    }
    import pandas as pd
    residual = float(model.predict(pd.DataFrame([[row[f] for f in features]], columns=features))[0])
    return math.exp(residual) if math.isfinite(residual) else None


def apply(physics_result, temp_c, duration_min):
    """Physics result with fuel and CO2 scaled by the ML correction.

    The extra fuel is what physics misses from stop-and-go driving, so it is
    added to the 'stops' part of the breakdown (scaled evenly if negative).
    """
    ratio = correction(physics_result, temp_c, duration_min)
    if ratio is None:
        return physics_result, None
    result = dict(physics_result)
    breakdown = dict(physics_result['co2_breakdown_kg'])
    extra = physics_result['co2_kg'] * (ratio - 1)
    if breakdown['stops'] + extra >= 0:
        breakdown['stops'] = round(breakdown['stops'] + extra, 3)
    else:
        breakdown = {k: round(v * ratio, 3) for k, v in breakdown.items()}
    result.update(fuel=round(physics_result['fuel'] * ratio, 3), co2_kg=round(physics_result['co2_kg'] * ratio, 3),
                  co2_breakdown_kg=breakdown, model='hybrid-physics-ved-v1')
    return result, round(ratio, 3)
