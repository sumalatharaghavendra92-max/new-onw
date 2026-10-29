"""Fleet simulation sandbox endpoints (admin only). Every response is labelled SIMULATION."""
from flask import Blueprint, request, jsonify

from app import limiter
from app.services import simulation
from app.utils.rbac import role_required

sim_bp = Blueprint('sim', __name__)


def _int(value, label, low, high):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f'{label} must be a whole number between {low} and {high}.')
    return value


def _not_ready():
    return jsonify(label=simulation.LABEL, message='No simulation is ready. Start one first.'), 404


@sim_bp.route('/start', methods=['POST'])
@role_required('admin')
@limiter.limit('5 per minute')
def start():
    data = request.get_json() or {}
    try:
        trucks = _int(data.get('trucks', 150), 'Trucks', 10, 200)
        orders = _int(data.get('orders', 900), 'Orders', 50, 1200)
        seed = _int(data.get('seed', 7), 'Seed', 0, 1_000_000)
        simulation.start(trucks, orders, seed)
    except ValueError as exc:
        return jsonify(label=simulation.LABEL, message=str(exc)), 422
    return jsonify(simulation.status()), 202


@sim_bp.route('/status')
@role_required('admin')
@limiter.limit('120 per minute', override_defaults=True)
def status():
    return jsonify(simulation.status())


@sim_bp.route('/state')
@role_required('admin')
@limiter.limit('240 per minute', override_defaults=True)
def state():
    try:
        t = float(request.args.get('t', simulation.DAY_START))
    except ValueError:
        return jsonify(label=simulation.LABEL, message='t must be minutes since midnight.'), 422
    if not 0 <= t <= 24 * 60:
        return jsonify(label=simulation.LABEL, message='t must be between 0 and 1440.'), 422
    result = simulation.state_at(t)
    return jsonify(result) if result else _not_ready()


@sim_bp.route('/summary')
@role_required('admin')
@limiter.limit('60 per minute', override_defaults=True)
def summary():
    result = simulation.summary()
    return jsonify(result) if result else _not_ready()


@sim_bp.route('/trucks/<int:truck_id>')
@role_required('admin')
@limiter.limit('120 per minute', override_defaults=True)
def truck(truck_id):
    result = simulation.truck_detail(truck_id)
    if result:
        return jsonify(result)
    return (_not_ready() if not simulation.scenario()
            else (jsonify(label=simulation.LABEL, message='Truck not found.'), 404))


@sim_bp.route('/reset', methods=['POST'])
@role_required('admin')
def reset():
    simulation.reset()
    return jsonify(simulation.status())
