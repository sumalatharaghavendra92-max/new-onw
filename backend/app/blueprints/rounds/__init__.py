from flask import Blueprint, request, jsonify, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db, limiter
from app.ml import physics
from app.models import (User, UserRole, UserStatus, Driver, ApprovalStatus, Vehicle, VehicleStatus,
                        DispatchedRound, RoundStatus, RoundLog, Notification)
from app.services.routing import coordinates, ProviderUnavailable
from app.services.rounds import plan_round, MAX_STOPS
from app.services.trip_workflow import number, iso, utcnow
from app.services.dispatch import serialize_round, conflicts, OPEN
from app.utils.rbac import role_required

rounds_bp = Blueprint('rounds', __name__)


@rounds_bp.errorhandler(ValueError)
def invalid(exc):
    return jsonify(message=str(exc)), 422


def round_vehicle(data):
    """Admins plan for any active vehicle; approved drivers plan for their own."""
    user = db.session.get(User, int(get_jwt_identity()))
    if not user or user.status != UserStatus.active:
        abort(403, description='Account is not active.')
    if user.role == UserRole.admin:
        vehicle_id = data.get('vehicle_id')
        if not isinstance(vehicle_id, int) or isinstance(vehicle_id, bool):
            raise ValueError('Choose a vehicle for this round.')
        vehicle = db.session.get(Vehicle, vehicle_id)
        if not vehicle:
            abort(404, description='Vehicle not found.')
        if vehicle.status != VehicleStatus.active:
            abort(409, description='This vehicle is not active.')
        return vehicle
    driver = Driver.query.filter_by(user_id=user.id).first()
    if user.role != UserRole.driver or not driver or driver.approval_status != ApprovalStatus.approved:
        abort(403, description='An approved driver account is required.')
    vehicle = Vehicle.query.filter_by(assigned_driver_id=driver.id, status=VehicleStatus.active).first()
    if not vehicle:
        abort(409, description='Ask your administrator to assign an active vehicle first.')
    return vehicle


def parse_stops(raw):
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_STOPS:
        raise ValueError(f'Add between 1 and {MAX_STOPS} stops.')
    stops = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError('Each stop needs a place and a drop weight.')
        lat, lng = coordinates(item.get('place'))
        label = item.get('label') or f'Stop {i + 1}'
        if not isinstance(label, str) or len(label) > 60:
            raise ValueError('Stop labels must be text of at most 60 characters.')
        stops.append({'index': i, 'label': label.strip(), 'lat': lat, 'lng': lng,
                      'drop_kg': number(item.get('drop_kg', 0), 'Drop weight', 0, 100_000)})
    return stops


def prepare(data, vehicle):
    """Validate a round request for this vehicle; shared by preview and dispatch."""
    vehicle_key = physics.vehicle_class(vehicle.type)
    fuel_key = physics.fuel_kind(vehicle.fuel_type, vehicle.type)
    if not vehicle_key or not fuel_key:
        abort(409, description='This vehicle class or fuel has no physics profile yet. Use van, truck, heavy truck or car with diesel, petrol, CNG or electric.')

    depot = coordinates(data.get('depot'))
    stops = parse_stops(data.get('stops'))
    places = [depot] + [(s['lat'], s['lng']) for s in stops]
    if len(set(places)) != len(places):
        raise ValueError('Depot and stops must all be different locations.')

    drops = sum(s['drop_kg'] for s in stops)
    start_load = number(data['start_load_kg'], 'Starting load') if data.get('start_load_kg') is not None else drops
    if start_load < drops:
        raise ValueError('Starting load must cover every drop on the round.')
    if start_load > (vehicle.load_capacity_kg or 0):
        abort(409, description='Starting load exceeds the vehicle capacity.')
    back = data.get('return_to_depot', True)
    if not isinstance(back, bool):
        raise ValueError('return_to_depot must be true or false.')
    return vehicle_key, fuel_key, depot, stops, start_load, back


def run_plan(vehicle, vehicle_key, fuel_key, depot, stops, start_load, back):
    from app.services.calibration import factor_and_uncertainty
    factor, _ = factor_and_uncertainty(vehicle.calibration)
    return plan_round(depot, stops, vehicle_key, fuel_key, start_load, back, factor), factor


@rounds_bp.route('/plan', methods=['POST'])
@limiter.limit('20 per minute', override_defaults=True)
@jwt_required()
def plan():
    data = request.get_json() or {}
    vehicle = round_vehicle(data)
    vehicle_key, fuel_key, depot, stops, start_load, back = prepare(data, vehicle)
    try:
        result, _ = run_plan(vehicle, vehicle_key, fuel_key, depot, stops, start_load, back)
    except ProviderUnavailable as exc:
        return jsonify(message=str(exc)), 503
    return jsonify(vehicle={'id': vehicle.id, 'vehicle_no': vehicle.vehicle_no, 'class': vehicle_key,
                            'class_label': physics.PROFILES[vehicle_key]['label'], 'fuel': fuel_key},
                   depot={'lat': depot[0], 'lng': depot[1]}, stops=stops, **result)


# ── Dispatched rounds ─────────────────────────────────────────────────────────

def current_user():
    user = db.session.get(User, int(get_jwt_identity()))
    if not user or user.status != UserStatus.active:
        abort(403, description='Account is not active.')
    return user


def current_driver():
    user = current_user()
    driver = Driver.query.filter_by(user_id=user.id).first()
    if user.role != UserRole.driver or not driver or driver.approval_status != ApprovalStatus.approved:
        abort(403, description='An approved driver account is required.')
    return driver


def find_round(round_id, owner_only=False):
    """Admins may read any round; drivers only their own. Mutations need the owning driver."""
    rnd = db.session.get(DispatchedRound, round_id)
    if not rnd:
        abort(404, description='Round not found.')
    user = current_user()
    if not owner_only and user.role == UserRole.admin:
        return rnd
    driver = Driver.query.filter_by(user_id=user.id).first()
    if not driver or rnd.driver_id != driver.id:
        abort(403, description='This round belongs to another driver.')
    if owner_only and driver.approval_status != ApprovalStatus.approved:
        abort(403, description='An approved driver account is required.')
    return rnd


def require_status(rnd, status, action):
    if rnd.status != status:
        abort(409, description=f'Only a {status.value.replace("_", " ")} round can be {action}.')


@rounds_bp.route('/dispatch', methods=['POST'])
@limiter.limit('20 per minute', override_defaults=True)
@role_required('admin')
def dispatch():
    data = request.get_json() or {}
    plan_key = data.get('plan_key')
    if plan_key not in ('fastest', 'greenest', 'balanced'):
        raise ValueError('plan_key must be fastest, greenest or balanced.')
    vehicle = round_vehicle(data)
    driver = db.session.get(Driver, vehicle.assigned_driver_id) if vehicle.assigned_driver_id else None
    if not driver or driver.approval_status != ApprovalStatus.approved:
        abort(409, description='Assign this vehicle to an approved driver before dispatching.')
    if conflicts(driver.id, vehicle.id, OPEN):
        abort(409, description='This driver or vehicle already has an open round or an active trip.')
    vehicle_key, fuel_key, depot, stops, start_load, back = prepare(data, vehicle)
    try:
        result, factor = run_plan(vehicle, vehicle_key, fuel_key, depot, stops, start_load, back)
    except ProviderUnavailable as exc:
        return jsonify(message=str(exc)), 503

    chosen = next(p for p in result['plans'] if p['key'] == plan_key)
    ordered = [dict(stops[i], position=pos, delivered_at=None) for pos, i in enumerate(chosen['order'])]
    rnd = DispatchedRound(
        vehicle_id=vehicle.id, driver_id=driver.id, created_by=int(get_jwt_identity()), plan_key=plan_key,
        depot_lat=depot[0], depot_lng=depot[1], start_load_kg=start_load, stops=ordered,
        plan={'duration_min': chosen['duration_min'], 'distance_km': chosen['distance_km'],
              'co2_kg': chosen['co2_kg'], 'fuel': chosen['fuel'], 'fuel_unit': chosen['fuel_unit'],
              'physics_fuel': round(chosen['fuel'] / factor, 3), 'calibration_factor': round(factor, 3),
              'legs': chosen['legs'], 'path_points': chosen['path_points'], 'return_to_depot': back,
              'assumptions': result['assumptions']})
    db.session.add(rnd)
    depot_label = (data.get('depot_label') or 'the depot') if isinstance(data.get('depot_label'), str) else 'the depot'
    db.session.add(Notification(
        user_id=driver.user_id, type='round_assigned',
        message=f'New round: {len(ordered)} stops from {depot_label[:60]}, {chosen["distance_km"]:.0f} km, '
                f'about {chosen["duration_min"]:.0f} min. Open your dashboard to start.'))
    db.session.commit()
    return jsonify(round=serialize_round(rnd)), 201


@rounds_bp.route('', methods=['GET'])
@role_required('admin')
def list_rounds():
    query = DispatchedRound.query
    status = request.args.get('status')
    if status:
        try:
            query = query.filter_by(status=RoundStatus(status))
        except ValueError:
            raise ValueError('status must be planned, in_progress, completed or cancelled.')
    limit = int(number(request.args.get('limit', 50), 'Limit', 1, 200))
    return jsonify(rounds=[serialize_round(r) for r in query.order_by(DispatchedRound.id.desc()).limit(limit)])


@rounds_bp.route('/mine', methods=['GET'])
@jwt_required()
def my_rounds():
    from app.services.calibration import factor_and_uncertainty
    driver = current_driver()
    mine = DispatchedRound.query.filter_by(driver_id=driver.id)
    active = mine.filter_by(status=RoundStatus.in_progress).first()
    upcoming = mine.filter_by(status=RoundStatus.planned).order_by(DispatchedRound.id).all()
    recent = mine.filter(DispatchedRound.status.in_([RoundStatus.completed, RoundStatus.cancelled])) \
        .order_by(DispatchedRound.id.desc()).limit(10).all()
    vehicle = Vehicle.query.filter_by(assigned_driver_id=driver.id, status=VehicleStatus.active).first()
    vehicle_json = None
    if vehicle:
        factor, uncertainty = factor_and_uncertainty(vehicle.calibration)
        cal = vehicle.calibration
        vehicle_json = {'id': vehicle.id, 'vehicle_no': vehicle.vehicle_no, 'class': physics.vehicle_class(vehicle.type),
                        'fuel': physics.fuel_kind(vehicle.fuel_type, vehicle.type), 'capacity_kg': vehicle.load_capacity_kg,
                        'calibration': {'factor': round(factor, 3), 'trips': cal.trips if cal else 0,
                                        'rejected': cal.rejected if cal else 0, 'uncertainty_pct': uncertainty}}
    return jsonify(active=serialize_round(active) if active else None,
                   upcoming=[serialize_round(r) for r in upcoming],
                   recent=[serialize_round(r) for r in recent], vehicle=vehicle_json)


@rounds_bp.route('/<int:round_id>', methods=['GET'])
@jwt_required()
def get_round(round_id):
    return jsonify(round=serialize_round(find_round(round_id)))


@rounds_bp.route('/<int:round_id>/start', methods=['POST'])
@jwt_required()
def start_round(round_id):
    rnd = find_round(round_id, owner_only=True)
    if rnd.status == RoundStatus.in_progress:
        return jsonify(round=serialize_round(rnd))
    require_status(rnd, RoundStatus.planned, 'started')
    if conflicts(rnd.driver_id, rnd.vehicle_id, [RoundStatus.in_progress]):
        abort(409, description='Finish your active trip or round first.')
    rnd.status, rnd.started_at = RoundStatus.in_progress, utcnow()
    db.session.commit()
    return jsonify(round=serialize_round(rnd))


@rounds_bp.route('/<int:round_id>/stops/<int:position>/deliver', methods=['POST'])
@jwt_required()
def deliver_stop(round_id, position):
    rnd = find_round(round_id, owner_only=True)
    require_status(rnd, RoundStatus.in_progress, 'updated')
    if not 0 <= position < len(rnd.stops):
        abort(404, description='Stop not found on this round.')
    if not rnd.stops[position].get('delivered_at'):
        stops = [dict(s) for s in rnd.stops]   # reassign so SQLAlchemy sees the JSON change
        stops[position]['delivered_at'] = iso(utcnow())
        rnd.stops = stops
        db.session.commit()
    return jsonify(round=serialize_round(rnd))


@rounds_bp.route('/<int:round_id>/log', methods=['POST'])
@limiter.limit('12 per minute', override_defaults=True)
@jwt_required()
def log_round_gps(round_id):
    rnd = find_round(round_id, owner_only=True)
    require_status(rnd, RoundStatus.in_progress, 'tracked')
    data = request.get_json() or {}
    db.session.add(RoundLog(round_id=rnd.id, lat=number(data.get('lat'), 'Latitude', -90, 90),
                            lng=number(data.get('lng'), 'Longitude', -180, 180)))
    db.session.commit()
    return jsonify(message='Location saved'), 201


@rounds_bp.route('/<int:round_id>/end', methods=['POST'])
@jwt_required()
def end_round(round_id):
    rnd = find_round(round_id, owner_only=True)
    if rnd.status == RoundStatus.completed:
        return jsonify(round=serialize_round(rnd))
    require_status(rnd, RoundStatus.in_progress, 'completed')
    data = request.get_json() or {}
    fuel = number(data['actual_fuel_l'], 'Fuel used') if data.get('actual_fuel_l') is not None else None
    rnd.status, rnd.ended_at, rnd.actual_fuel_l = RoundStatus.completed, utcnow(), fuel
    if fuel is not None:
        from app.services.calibration import learn_from_trip
        rnd.calibration_result = learn_from_trip(rnd.vehicle, rnd.plan.get('physics_fuel'), fuel)
    db.session.commit()
    return jsonify(round=serialize_round(rnd))


@rounds_bp.route('/<int:round_id>/cancel', methods=['POST'])
@jwt_required()
def cancel_round(round_id):
    rnd = find_round(round_id)
    if current_user().role != UserRole.admin:
        rnd = find_round(round_id, owner_only=True)
    if rnd.status == RoundStatus.completed:
        abort(409, description='A completed round cannot be cancelled.')
    rnd.status, rnd.ended_at = RoundStatus.cancelled, rnd.ended_at or utcnow()
    db.session.commit()
    return jsonify(round=serialize_round(rnd))
