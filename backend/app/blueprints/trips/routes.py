from flask import Blueprint, request, jsonify, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError
from app import db, limiter
from app.models import (Trip, TripStatus, TripPlan, Route, TripLog, Driver, Vehicle,
                        User, UserRole, UserStatus, ApprovalStatus, VehicleStatus)
from app.services.routing import get_road_routes, ProviderUnavailable
from app.services.trip_workflow import number, estimate, serialize, selected, utcnow

trips_bp = Blueprint('trips', __name__)


@trips_bp.errorhandler(ValueError)
def invalid(exc):
    return jsonify(message=str(exc)), 422


def actor():
    user = db.session.get(User, int(get_jwt_identity()))
    if not user or user.status != UserStatus.active:
        abort(403, description='Account is not active.')
    return user


def driver_actor():
    user = actor()
    driver = Driver.query.filter_by(user_id=user.id).first()
    if user.role != UserRole.driver or not driver or driver.approval_status != ApprovalStatus.approved:
        abort(403, description='An approved driver account is required.')
    return driver


def accessible(trip_id, mutate=False):
    user = actor()
    trip = db.session.get(Trip, trip_id)
    if not trip:
        abort(404, description='Trip not found.')
    if mutate:
        driver = driver_actor()
        if trip.driver_id != driver.id:
            abort(403, description='This trip belongs to another driver.')
    elif user.role != UserRole.admin and trip.driver.user_id != user.id:
        abort(403, description='This trip belongs to another driver.')
    return trip


@trips_bp.route('', methods=['POST'])
@jwt_required()
def create_trip():
    driver = driver_actor()
    data = request.get_json() or {}
    source, destination = data.get('source', ''), data.get('destination', '')
    load = number(data.get('load_weight_kg', 0), 'Cargo weight')
    vehicle = Vehicle.query.filter_by(assigned_driver_id=driver.id, status=VehicleStatus.active).first()
    if not vehicle:
        return jsonify(message='Ask your administrator to assign an active vehicle first.'), 409
    if load > (vehicle.load_capacity_kg or 0):
        raise ValueError('Cargo exceeds the assigned vehicle capacity.')
    if Trip.query.filter(Trip.status == TripStatus.in_progress,
                         (Trip.driver_id == driver.id) | (Trip.vehicle_id == vehicle.id)).first():
        return jsonify(message='Finish or cancel the active trip before planning another.'), 409
    try:
        candidates = get_road_routes(source, destination)
    except ProviderUnavailable as exc:
        return jsonify(message=str(exc)), 503
    if not candidates:
        return jsonify(message='No routes found; no trip was created.'), 503
    estimates = [estimate(r, vehicle, load) for r in candidates]
    from app.services.decision_policy import choose_route
    fastest, best, decision = choose_route(candidates, estimates)
    trip = Trip(driver_id=driver.id, vehicle_id=vehicle.id, source=source.strip(),
                destination=destination.strip(), load_weight_kg=load, status=TripStatus.planned)
    db.session.add(trip)
    db.session.flush()
    records = []
    for i, (candidate, metrics) in enumerate(zip(candidates, estimates)):
        label = ('Fastest · evidence limited' if decision['eco_ranking_withheld'] else 'Recommended route') if i == best else ('Fastest route' if i == fastest else f'Alternative {i + 1}')
        route = Route(trip_id=trip.id, route_label=label, distance_km=candidate['distance_km'],
                      avg_speed=candidate['distance_km'] / candidate['duration_min'] * 60,
                      traffic_density='Unknown', is_recommended=i == best and not decision['eco_ranking_withheld'],
                      predicted_fuel_l=metrics['predicted_fuel_l'], predicted_co2_kg=metrics['predicted_co2_kg'],
                      eco_score=metrics['eco_score'])
        db.session.add(route)
        db.session.flush()
        records.append({'id': route.id, 'title': label, 'type': 'eco' if route.is_recommended else 'alternative',
                        'distanceKm': round(candidate['distance_km'], 2),
                        'durationMin': round(candidate['duration_min'], 1),
                        'fuelLiters': route.predicted_fuel_l, 'co2Kg': route.predicted_co2_kg,
                        'evidence': metrics.get('evidence'),
                        'fuelUnit': metrics.get('fuel_unit', 'L'), 'physicsFuel': metrics.get('physics_fuel'),
                        'breakdown': metrics.get('breakdown'), 'climbM': metrics.get('climb_m'),
                        'avgSpeedKmh': metrics.get('avg_speed_kmh'), 'turns': metrics.get('turns'),
                        'uncertaintyPct': metrics.get('uncertainty_pct'),
                        'calibrationFactor': metrics.get('calibration_factor'),
                        'ecoScore': route.eco_score, 'isAiRecommended': route.is_recommended, 'isDefault': i == best,
                        'decisionPolicy': decision, 'isFastest': i == fastest, 'pathPoints': candidate['pathPoints']})
    plan = TripPlan(trip_id=trip.id, candidates=records,
                    baseline_co2_kg=estimates[fastest]['predicted_co2_kg'],
                    prediction_mode=estimates[best]['prediction_mode'])
    db.session.add(plan)
    db.session.commit()
    return jsonify(serialize(trip)), 201


@trips_bp.route('/history')
@jwt_required()
def history():
    driver = driver_actor()
    trips = Trip.query.filter_by(driver_id=driver.id).order_by(Trip.id.desc()).limit(100).all()
    return jsonify(trips=[serialize(t) for t in trips])


@trips_bp.route('/<int:trip_id>')
@jwt_required()
def get_trip(trip_id):
    return jsonify(serialize(accessible(trip_id)))


@trips_bp.route('/<int:trip_id>/select-route', methods=['PATCH'])
@jwt_required()
def select_route(trip_id):
    trip = accessible(trip_id, True)
    if trip.status != TripStatus.planned or not trip.plan:
        return jsonify(message='Only a planned trip can change routes.'), 409
    route_id = (request.get_json() or {}).get('route_id')
    if not any(r['id'] == route_id for r in trip.plan.candidates):
        raise ValueError('Choose a route belonging to this trip.')
    trip.plan.selected_route_id = route_id
    db.session.commit()
    return jsonify(serialize(trip))


@trips_bp.route('/<int:trip_id>/start', methods=['POST'])
@jwt_required()
def start_trip(trip_id):
    trip = accessible(trip_id, True)
    if trip.status == TripStatus.in_progress:
        return jsonify(serialize(trip))
    if trip.status != TripStatus.planned or not selected(trip):
        return jsonify(message='Select a route on a planned trip first.'), 409
    from datetime import timezone
    age = (utcnow() - trip.plan.created_at.replace(tzinfo=timezone.utc)).total_seconds()
    if age > 1800:
        return jsonify(message='This plan is older than 30 minutes. Cancel it and request fresh routes.'), 409
    if trip.vehicle.assigned_driver_id != trip.driver_id or trip.vehicle.status != VehicleStatus.active:
        return jsonify(message='Vehicle assignment or availability changed. Plan a new trip.'), 409
    if (trip.load_weight_kg or 0) > (trip.vehicle.load_capacity_kg or 0):
        return jsonify(message='Cargo exceeds current vehicle capacity.'), 409
    conflict = Trip.query.filter(Trip.status == TripStatus.in_progress,
                                 (Trip.driver_id == trip.driver_id) | (Trip.vehicle_id == trip.vehicle_id)).first()
    if conflict:
        return jsonify(message='Driver or vehicle already has an active trip.'), 409
    trip.plan.active_driver_id = trip.driver_id
    trip.plan.active_vehicle_id = trip.vehicle_id
    trip.start_time = utcnow()
    trip.status = TripStatus.in_progress
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(message='Driver or vehicle already has an active trip.'), 409
    return jsonify(serialize(trip))


@trips_bp.route('/<int:trip_id>/end', methods=['POST'])
@jwt_required()
def end_trip(trip_id):
    trip = accessible(trip_id, True)
    if trip.status == TripStatus.completed:
        return jsonify(serialize(trip))
    if trip.status != TripStatus.in_progress:
        return jsonify(message='Only an active trip can be completed.'), 409
    data = request.get_json() or {}
    fuel = number(data['actual_fuel_l'], 'Measured fuel') if data.get('actual_fuel_l') is not None else None
    co2 = number(data['actual_co2_kg'], 'Measured CO2') if data.get('actual_co2_kg') is not None else None
    trip.actual_fuel_l, trip.actual_co2_kg = fuel, co2
    trip.status, trip.end_time = TripStatus.completed, utcnow()
    if trip.plan:
        trip.plan.active_driver_id = trip.plan.active_vehicle_id = None
    route = selected(trip)
    if route:
        trip.driver.eco_score = route['ecoScore']
        if fuel is not None:
            from app.services.calibration import learn_from_trip
            learn_from_trip(trip.vehicle, route.get('physicsFuel'), fuel)
    db.session.commit()
    return jsonify(serialize(trip))


@trips_bp.route('/<int:trip_id>/cancel', methods=['POST'])
@jwt_required()
def cancel_trip(trip_id):
    trip = accessible(trip_id, True)
    if trip.status == TripStatus.completed:
        return jsonify(message='A completed trip cannot be cancelled.'), 409
    trip.status = TripStatus.cancelled
    trip.end_time = utcnow()
    if trip.plan:
        trip.plan.active_driver_id = trip.plan.active_vehicle_id = None
    db.session.commit()
    return jsonify(serialize(trip))


@trips_bp.route('/<int:trip_id>/log', methods=['POST'])
@limiter.limit('12 per minute', override_defaults=True)
@jwt_required()
def log_gps(trip_id):
    trip = accessible(trip_id, True)
    if trip.status != TripStatus.in_progress:
        return jsonify(message='Location updates require an active trip.'), 409
    data = request.get_json() or {}
    lat = number(data.get('lat'), 'Latitude', -90, 90)
    lng = number(data.get('lng'), 'Longitude', -180, 180)
    db.session.add(TripLog(trip_id=trip.id, lat=lat, lng=lng))
    db.session.commit()
    return jsonify(message='Location saved'), 201
