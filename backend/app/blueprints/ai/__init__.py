from types import SimpleNamespace

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from app import limiter
from app.ml import physics
from app.utils.rbac import role_required

ai_bp = Blueprint('ai_engine', __name__, url_prefix='/api/ai')

EQUATION = ('F = Crr·m·g·cos θ + ½·ρ·CdA·v² + m·g·sin θ;  '
            'energy = Σ F·d + turns·½·m·(v² − v_turn²) + P_aux·t;  '
            'fuel = energy / (efficiency · energy per litre);  CO₂ = fuel · emission factor')

ASSUMPTIONS = [
    'Each vehicle type uses typical weight, size and tyre values until the app learns that vehicle.',
    'Road speeds are normal road speeds. Live traffic is not included.',
    'Every turn slows the vehicle down and costs fuel to speed up again. Electric vehicles get 60% of it back.',
    'Hot days use more fuel because the AC runs. Thin air on high roads means less wind resistance.',
    'Wet roads add 15% to tyre resistance.',
    'Electric vehicles count the CO₂ of the electricity from the Indian grid, not zero.',
]

DATA_SOURCES = [
    {'name': 'OSRM', 'url': 'https://project-osrm.org/', 'use': 'Road alternatives, per-segment speed, turns, distance matrix'},
    {'name': 'Open-Meteo Forecast', 'url': 'https://open-meteo.com/', 'use': 'Live temperature and rain at the start point'},
    {'name': 'Open-Meteo Elevation', 'url': 'https://open-meteo.com/en/docs/elevation-api', 'use': 'Terrain height along each route (Copernicus DEM 90 m)'},
    {'name': 'IPCC 2006 Guidelines', 'url': 'https://www.ipcc-nggip.iges.or.jp/public/2006gl/vol2.html', 'use': 'Fuel CO₂ factors and calorific values'},
    {'name': 'CEA CO₂ Baseline Database v19', 'url': 'https://cea.nic.in/cdm-co2-baseline-database/', 'use': 'Indian grid factor 0.716 kg CO₂/kWh'},
    {'name': 'FuelEconomy.gov', 'url': 'https://www.fueleconomy.gov/feg/ws/index.shtml', 'use': 'Real-data validation of a vehicle-efficiency regressor'},
]


@ai_bp.route('/fleet-health')
@role_required('admin')
def fleet_health():
    from app.services.calibration import calibration_rows
    rows = calibration_rows()
    return jsonify(model=physics.MODEL_VERSION, system_status='Model ready',
                   vehicles=len(rows), calibrated_vehicles=sum(1 for r in rows if r['trips'] >= 3),
                   predictive_maintenance={'available': False, 'reason': 'No measured maintenance model connected'})


VED_ROW_NAMES = {
    'physics': 'Physics model, before the trip',
    'physics_calibrated': 'Physics + learning per vehicle',
    'baseline_class_median': 'Simple baseline: distance × typical L/km',
    'baseline_own_median': "Baseline using the car's own past trips",
    'physics_post_trip': 'Physics with the real speed trace (after the trip)',
    'hybrid': 'Hybrid: physics + ML correction',
    'hybrid_calibrated': 'Hybrid + learning per vehicle',
}
VED_ROW_ORDER = ['hybrid_calibrated', 'hybrid', 'baseline_own_median', 'baseline_class_median',
                 'physics_calibrated', 'physics']


def _metric_rows(group):
    """Pick every {name: {mae_pct, ...}} entry out of one result group."""
    rows = []
    if not isinstance(group, dict):
        return rows
    for name, metrics in group.items():
        if isinstance(metrics, dict) and 'mae_pct' in metrics:
            rows.append({'key': name, 'name': VED_ROW_NAMES.get(name, name.replace('_', ' ').capitalize()),
                         'mae_pct': metrics['mae_pct'], 'bias_pct': metrics.get('bias_pct'),
                         'r2': metrics.get('r2'), 'trips': metrics.get('trips')})
    return rows


def ved_validation():
    """Compact view of the real-trip validation on the Vehicle Energy Dataset, if it has been run."""
    from pathlib import Path
    import json
    path = Path(__file__).resolve().parents[3] / 'public_data' / 'ved_evaluation.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    counts = data.get('counts', {})
    # The hybrid run re-scored every method on the same holdout trips, so prefer its table.
    hybrid = data.get('hybrid') or {}
    rows = _metric_rows(hybrid.get('holdout')) or _metric_rows(data.get('headline_holdout_vehicles'))
    rows.sort(key=lambda r: VED_ROW_ORDER.index(r['key']) if r['key'] in VED_ROW_ORDER else 99)
    return {'holdout_vehicles': counts.get('holdout_vehicles'), 'holdout_trips': counts.get('holdout_scored_trips'),
            'trips_kept': counts.get('trips_kept'), 'hybrid_train_trips': hybrid.get('train_trips'),
            'hybrid_train_vehicles': hybrid.get('train_vehicles'),
            'rows': rows,
            'post_trip': _metric_rows(data.get('post_trip_variant'))[:1],
            'applies_to_indian_trucks': data.get('applies_to_indian_trucks', False),
            'limitations': (data.get('limitations') or [])[:4]}


@ai_bp.route('/model-card')
@role_required('admin')
def model_card():
    from app.services.calibration import calibration_rows
    from app.services.feedback import public_benchmark
    return jsonify(model_version=physics.MODEL_VERSION, equation=EQUATION,
                   profiles=physics.PROFILES, fuels=physics.FUELS, powertrains=physics.POWERTRAINS,
                   assumptions=ASSUMPTIONS, data_sources=DATA_SOURCES,
                   public_benchmark=public_benchmark(), ved_validation=ved_validation(),
                   calibration=calibration_rows())


@ai_bp.route('/model-lab', methods=['POST'])
@role_required('admin')
@limiter.limit('20 per minute')
def model_lab():
    """Compare real road alternatives for a hypothetical vehicle; nothing is saved."""
    from app.services.routing import get_road_routes, ProviderUnavailable
    from app.services.trip_workflow import number, estimate
    from app.services.decision_policy import choose_route
    data = request.get_json() or {}
    vehicle_key, fuel_key = data.get('vehicle_type'), data.get('fuel_type')
    try:
        if vehicle_key not in physics.PROFILES:
            raise ValueError(f'vehicle_type must be one of {", ".join(physics.PROFILES)}.')
        if fuel_key not in physics.FUELS:
            raise ValueError(f'fuel_type must be one of {", ".join(physics.FUELS)}.')
        capacity = number(data.get('capacity_kg', 1000), 'Capacity', 0, 40000)
        load = number(data.get('load_kg', 0), 'Load', 0, capacity)
        candidates = get_road_routes(data.get('source', ''), data.get('destination', ''))
    except ValueError as exc:
        return jsonify(message=str(exc)), 422
    except ProviderUnavailable as exc:
        return jsonify(message=str(exc)), 503
    vehicle = SimpleNamespace(type=physics.PROFILES[vehicle_key]['label'], fuel_type=fuel_key,
                              load_capacity_kg=capacity, calibration=None)
    estimates = [estimate(route, vehicle, load) for route in candidates]
    fastest, best, decision = choose_route(candidates, estimates)
    routes = []
    for i, (route, metrics) in enumerate(zip(candidates, estimates)):
        routes.append({'id': i, 'title': 'Fastest route' if i == fastest else f'Alternative {i + 1}',
                       'distanceKm': round(route['distance_km'], 2), 'durationMin': round(route['duration_min'], 1),
                       'fuelLiters': metrics['predicted_fuel_l'], 'fuelUnit': metrics['fuel_unit'],
                       'co2Kg': metrics['predicted_co2_kg'], 'breakdown': metrics['breakdown'],
                       'climbM': metrics['climb_m'], 'avgSpeedKmh': metrics['avg_speed_kmh'], 'turns': metrics['turns'],
                       'ecoScore': metrics['eco_score'], 'isFastest': i == fastest,
                       'isRecommended': i == best and not decision['eco_ranking_withheld'],
                       'pathPoints': route['pathPoints']})
    inputs = estimates[0]['evidence']['inputs']
    return jsonify(routes=routes, decision=decision,
                   weather={'temp_c': inputs['temperature_c'], 'wet_road': inputs['wet_road'], 'status': inputs['weather_status']},
                   elevation_status='available' if all(r.get('elevation_status') == 'available' for r in candidates) else 'unavailable',
                   vehicle={'class': vehicle_key, 'label': physics.PROFILES[vehicle_key]['label'], 'fuel': fuel_key,
                            'mass_kg': estimates[0]['mass_kg']})


@ai_bp.route('/driver-score', methods=['POST'])
@jwt_required()
def calculate_driver_score():
    """Rule-based eco-driving coach from driver-entered events (not learned)."""
    data = request.get_json() or {}
    from app.services.trip_workflow import number
    try:
        harsh_braking = number(data.get('harsh_braking', 0), 'Harsh braking', 0, 1000)
        rapid_accel = number(data.get('rapid_accel', 0), 'Rapid acceleration', 0, 1000)
        idle_minutes = number(data.get('idle_minutes', 0), 'Idle minutes', 0, 1440)
        avg_speed = number(data.get('avg_speed', 0), 'Average speed', 0, 200)
    except ValueError as exc:
        return jsonify(message=str(exc)), 422

    penalty = harsh_braking * 4.5 + rapid_accel * 3.5 + max(0.0, (idle_minutes - 5.0) * 1.5) + (10.0 if avg_speed > 75 else 0.0)
    score = int(max(20, min(100, 100 - penalty)))
    if score >= 85:
        tier, colour, tip = 'Eco Champion', 'emerald', 'Smooth acceleration and minimal idling. Excellent fuel conservation!'
    elif score >= 65:
        tier, colour, tip = 'Efficient Driver', 'amber', 'Watch prolonged stop-and-go idling.'
    else:
        tier, colour, tip = 'Needs Optimization', 'rose', 'Frequent harsh braking and sudden acceleration. Ease throttle pressure.'
    return jsonify({
        'success': True, 'eco_score': score, 'tier': tier, 'tier_color': colour, 'primary_coaching_tip': tip,
        'method': 'Rule-based penalties; not a learned model',
        'telemetry_breakdown': {'harsh_braking_events': harsh_braking, 'rapid_accel_events': rapid_accel,
                                'idle_duration_min': idle_minutes, 'average_speed_kmh': avg_speed},
    }), 200
