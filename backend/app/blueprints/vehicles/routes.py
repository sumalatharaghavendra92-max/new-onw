from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from app import db
from app.models import Vehicle, VehicleStatus, Driver, AuditLog
from app.utils.rbac import role_required

vehicles_bp = Blueprint('vehicles', __name__)


def _write_audit(actor_id, action, entity_id):
    log = AuditLog(actor_id=actor_id, action=action, entity='vehicle', entity_id=entity_id)
    db.session.add(log)


@vehicles_bp.route('', methods=['GET'])
@role_required('admin')
def list_vehicles():
    vehicles = Vehicle.query.all()
    result = []
    from app.models import FleetReading
    for v in vehicles:
        reading = db.session.get(FleetReading, v.id)
        driver = Driver.query.get(v.assigned_driver_id) if v.assigned_driver_id else None
        from app.models import User
        driver_user = User.query.get(driver.user_id) if driver else None
        result.append({
            "reading": reading.to_dict() if reading else None,
            "id": v.id,
            "vehicle_no": v.vehicle_no,
            "type": v.type,
            "fuel_type": v.fuel_type,
            "load_capacity_kg": v.load_capacity_kg,
            "emission_factor_g_per_km": v.emission_factor_g_per_km,
            "status": v.status.value,
            "assigned_driver_id": v.assigned_driver_id,
            "assigned_driver_name": driver_user.name if driver_user else None,
        })
    return jsonify(result), 200


@vehicles_bp.route('', methods=['POST'])
@role_required('admin')
def create_vehicle():
    actor_id = get_jwt_identity()
    data = request.get_json() or {}
    required = ['vehicle_no', 'type', 'fuel_type']
    for f in required:
        if not data.get(f):
            return jsonify({"error": "validation_error", "message": f"{f} is required"}), 422

    if Vehicle.query.filter_by(vehicle_no=data['vehicle_no']).first():
        return jsonify({"error": "conflict", "message": "Vehicle number already exists"}), 409

    vehicle = Vehicle(
        vehicle_no=data['vehicle_no'],
        type=data['type'],
        fuel_type=data['fuel_type'],
        load_capacity_kg=data.get('load_capacity_kg', 1000),
        emission_factor_g_per_km=data.get('emission_factor_g_per_km', 120.0),
        assigned_driver_id=data.get('assigned_driver_id'),
        status=VehicleStatus.active
    )
    db.session.add(vehicle)
    db.session.flush()
    _write_audit(actor_id, 'create', vehicle.id)
    db.session.commit()

    return jsonify({"message": "Vehicle created", "id": vehicle.id}), 201


@vehicles_bp.route('/<int:vehicle_id>', methods=['PATCH'])
@role_required('admin')
def update_vehicle(vehicle_id):
    actor_id = get_jwt_identity()
    vehicle = Vehicle.query.get(vehicle_id)
    if not vehicle:
        return jsonify({"error": "not_found", "message": "Vehicle not found"}), 404

    data = request.get_json() or {}
    allowed = ['type', 'fuel_type', 'load_capacity_kg', 'emission_factor_g_per_km',
               'assigned_driver_id', 'status']
    for field in allowed:
        if field in data:
            if field == 'status':
                try:
                    setattr(vehicle, field, VehicleStatus[data[field]])
                except KeyError:
                    return jsonify({"error": "validation_error", "message": "Invalid status"}), 422
            else:
                setattr(vehicle, field, data[field])

    _write_audit(actor_id, 'update', vehicle_id)
    db.session.commit()
    return jsonify({"message": "Vehicle updated"}), 200


@vehicles_bp.route('/<int:vehicle_id>', methods=['DELETE'])
@role_required('admin')
def delete_vehicle(vehicle_id):
    actor_id = get_jwt_identity()
    vehicle = Vehicle.query.get(vehicle_id)
    if not vehicle:
        return jsonify({"error": "not_found", "message": "Vehicle not found"}), 404

    _write_audit(actor_id, 'delete', vehicle_id)
    from app.models import FleetReading
    FleetReading.query.filter_by(vehicle_id=vehicle.id).delete()
    db.session.delete(vehicle)
    db.session.commit()
    return jsonify({"message": "Vehicle deleted"}), 200


@vehicles_bp.route('/<int:vehicle_id>/reading', methods=['PUT'])
@role_required('admin')
def record_reading(vehicle_id):
    from app.models import FleetReading
    from datetime import datetime, timezone
    import math
    vehicle = db.session.get(Vehicle, vehicle_id)
    if not vehicle:
        return jsonify(message='Vehicle not found'), 404
    data = request.get_json() or {}
    try:
        values = {k: float(data[k]) for k in ('fuel_percent', 'load_kg', 'odometer_km')}
        if not all(math.isfinite(x) for x in values.values()):
            raise ValueError()
        if not 0 <= values['fuel_percent'] <= 100 or not 0 <= values['load_kg'] <= vehicle.load_capacity_kg or values['odometer_km'] < 0:
            raise ValueError()
    except (KeyError, ValueError, TypeError):
        return jsonify(message='Enter fuel/battery 0–100%, load within vehicle capacity, and a nonnegative odometer.'), 422
    reading = db.session.get(FleetReading, vehicle_id)
    if not reading:
        reading = FleetReading(vehicle_id=vehicle_id)
        db.session.add(reading)
    for k, v in values.items():
        setattr(reading, k, v)
    reading.source = 'manual'
    reading.recorded_at = datetime.now(timezone.utc).isoformat()
    _write_audit(get_jwt_identity(), 'record_reading', vehicle_id)
    db.session.commit()
    return jsonify(reading.to_dict())
