import math
from datetime import datetime, timezone
from app.ml import physics

DEFAULT_TEMP_C = 25.0


def number(value, label, minimum=0, maximum=1_000_000):
    try:
        if isinstance(value, bool):
            raise ValueError()
        value = float(value)
        if not math.isfinite(value) or not minimum <= value <= maximum:
            raise ValueError()
        return value
    except (ValueError, TypeError):
        raise ValueError(f'{label} must be a number between {minimum} and {maximum}.')


def iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


def planning_weather(lat, lng):
    """(temperature °C, wet road, status) from live Open-Meteo data; a labelled default if unavailable."""
    from app.services.live_context import get_live_context
    context = get_live_context(lat, lng)
    current = context.get('current')
    if not current:
        return DEFAULT_TEMP_C, False, 'unavailable'
    return current['temperature_2m'], current['precipitation'] > 0.2, context['status']


def estimate(route, vehicle, load, weather=None):
    """Physics prediction for one candidate route.

    Petrol cars and vans also get the ML correction learned from real trips
    (app/ml/hybrid.py). Every vehicle is then corrected by its own calibration.
    """
    from app.ml import hybrid
    from app.services.calibration import factor_and_uncertainty, DEFAULT_UNCERTAINTY_PCT
    from app.services.evidence import evidence_for
    vehicle_key = physics.vehicle_class(vehicle.type)
    fuel_key = physics.fuel_kind(vehicle.fuel_type, vehicle.type)
    segments = route.get('segments') or [{'distance_m': route['distance_km'] * 1000,
                                          'duration_s': route['duration_min'] * 60, 'rise_m': 0, 'elevation_m': 0}]
    temp_c, wet_road, weather_status = weather or planning_weather(*route['pathPoints'][0])
    # Unsupported vehicles still get numbers so routes can be shown, but the
    # evidence marks them out of domain and the decision policy withholds ranking.
    result = physics.estimate(segments, vehicle_key or 'van', fuel_key or 'diesel', load,
                              temp_c=temp_c, wet_road=wet_road, turns=route.get('turns', 0))
    physics_co2 = result['co2_kg']
    hybrid_ratio = None
    if hybrid.applies(vehicle_key, fuel_key):
        result, hybrid_ratio = hybrid.apply(result, temp_c, route['duration_min'])
    factor, uncertainty = factor_and_uncertainty(getattr(vehicle, 'calibration', None))
    trips = vehicle.calibration.trips if getattr(vehicle, 'calibration', None) else 0
    if hybrid_ratio is not None and trips < 3 and uncertainty == DEFAULT_UNCERTAINTY_PCT:
        uncertainty = 15.0  # hybrid's average error on unseen real cars was 14%
    reference = physics.reference_co2_per_km(vehicle_key or 'van', fuel_key or 'diesel', vehicle.load_capacity_kg)
    co2 = result['co2_kg'] * factor
    base = 'Hybrid model (physics + ML from real trips)' if hybrid_ratio is not None else 'Physics road-load model'
    mode = base + (f', calibrated on {trips} trip' + ('s' if trips != 1 else '') if trips else ', class defaults')
    details = {'temp_c': temp_c, 'wet_road': wet_road, 'weather_status': weather_status,
               'elevation_status': route.get('elevation_status', 'unavailable'), 'turns': route.get('turns', 0),
               'uncertainty_pct': uncertainty, 'calibration_trips': trips}
    return {
        'predicted_fuel_l': round(result['fuel'] * factor, 3), 'fuel_unit': result['fuel_unit'],
        'predicted_co2_kg': round(co2, 3), 'physics_fuel': result['fuel'],
        'breakdown': {k: round(v * factor, 3) for k, v in result['co2_breakdown_kg'].items()},
        'climb_m': result['climb_m'], 'avg_speed_kmh': result['avg_speed_kmh'], 'turns': result['turns'],
        'mass_kg': result['mass_kg'], 'uncertainty_pct': uncertainty, 'calibration_factor': round(factor, 3),
        # Eco score compares the road itself with the class reference, so it uses physics CO2.
        'eco_score': physics.eco_score(physics_co2 * factor, route['distance_km'], reference),
        'hybrid_correction': hybrid_ratio,
        'prediction_mode': mode, 'evidence': evidence_for(vehicle, load, details, mode),
    }


def selected(trip):
    if not trip.plan:
        return None
    return next((r for r in trip.plan.candidates if r['id'] == trip.plan.selected_route_id), None)


def serialize(trip):
    route = selected(trip)
    plan = trip.plan
    from app.models import TripLog
    last = TripLog.query.filter_by(trip_id=trip.id).order_by(TripLog.timestamp.desc()).first()
    comparable = route and not route.get('decisionPolicy', {}).get('eco_ranking_withheld', False)
    saved = plan.baseline_co2_kg - route['co2Kg'] if plan and comparable else None
    return {
        'id': trip.id, 'tripId': trip.id, 'origin': trip.source, 'destination': trip.destination,
        'status': trip.status.value, 'driverName': trip.driver.user.name,
        'vehicleId': trip.vehicle.vehicle_no, 'loadWeight': trip.load_weight_kg,
        'startedAt': iso(trip.start_time), 'completedAt': iso(trip.end_time),
        'createdAt': iso(plan.created_at) if plan else None,
        'routes': plan.candidates if plan else [],
        'selectedRouteId': plan.selected_route_id if plan else None,
        'selectedRoute': route,
        'estimatedSavingsKg': round(saved, 2) if saved is not None else None,
        'predictionMode': plan.prediction_mode if plan else 'Legacy record — no saved prediction',
        'actualFuelLiters': trip.actual_fuel_l, 'actualCo2Kg': trip.actual_co2_kg,
        'fuelPredictionErrorLiters': round(trip.actual_fuel_l - route['fuelLiters'], 3)
        if route and trip.actual_fuel_l is not None else None,
        'measurementSource': 'Driver-reported; not independently verified' if trip.actual_fuel_l is not None else 'Not recorded',
        'lastLocation': {'lat': last.lat, 'lng': last.lng, 'timestamp': iso(last.timestamp)} if last else None,
    }


def utcnow():
    return datetime.now(timezone.utc)
