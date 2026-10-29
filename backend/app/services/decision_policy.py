"""Explicit decision policy, not a statistical confidence estimate."""
import math


def choose_route(candidates, estimates):
    if not candidates or len(candidates) != len(estimates):
        raise ValueError('Route candidates and estimates must match.')
    for route, prediction in zip(candidates, estimates):
        for value in (route['duration_min'], route['distance_km']):
            if not math.isfinite(value) or value <= 0:
                raise ValueError('Route duration and distance must be positive and finite.')
        if not math.isfinite(prediction['predicted_co2_kg']) or prediction['predicted_co2_kg'] < 0:
            raise ValueError('Emissions prediction must be finite and nonnegative.')
    fastest = min(range(len(candidates)), key=lambda i: candidates[i]['duration_min'])
    eligible = [i for i, route in enumerate(candidates)
                if route['duration_min'] <= candidates[fastest]['duration_min'] * 1.15]
    best = min(eligible, key=lambda i: (estimates[i]['predicted_co2_kg'], candidates[i]['duration_min']))
    baseline = estimates[fastest]['predicted_co2_kg']
    threshold = max(0.1, baseline * 0.02)
    improvement = baseline - estimates[best]['predicted_co2_kg']
    unsupported = any(p.get('evidence', {}).get('within_documented_domain') is False for p in estimates)
    if unsupported:
        best = fastest
        reason = 'We could not compare roads for this vehicle type, so we show the fastest road.'
    elif improvement < threshold:
        best = fastest
        reason = 'The fastest road is kept: no other road saves enough CO₂.'
    else:
        reason = 'This road saves the most CO₂ and is at most 15% slower than the fastest.'
    return fastest, best, {'version': 'evidence-aware-v2', 'reason': reason,
                          'eco_ranking_withheld': unsupported,
                          'minimum_improvement_kg': round(threshold, 4),
                          'max_time_overhead_percent': 15,
                          'uncertainty_calibrated': False,
                          'note': '2% / 0.1 kg threshold is a product heuristic, not a confidence interval.'}
