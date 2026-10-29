"""Dispatched rounds: serialisation and the state checks shared by the endpoints."""
from app.ml import physics
from app.models import RoundLog, RoundStatus
from app.services.trip_workflow import iso


def serialize_round(rnd):
    vehicle_key = physics.vehicle_class(rnd.vehicle.type)
    stops = rnd.stops
    delivered = [s for s in stops if s.get('delivered_at')]
    last = RoundLog.query.filter_by(round_id=rnd.id).order_by(RoundLog.timestamp.desc()).first()
    plan = rnd.plan
    return {
        'id': rnd.id, 'status': rnd.status.value, 'plan_key': rnd.plan_key, 'label': 'Dispatched round',
        'vehicle': {'id': rnd.vehicle.id, 'vehicle_no': rnd.vehicle.vehicle_no, 'class': vehicle_key,
                    'class_label': physics.PROFILES[vehicle_key]['label'] if vehicle_key else rnd.vehicle.type,
                    'fuel': physics.fuel_kind(rnd.vehicle.fuel_type, rnd.vehicle.type)},
        'driver': {'id': rnd.driver.id, 'name': rnd.driver.user.name},
        'depot': {'lat': rnd.depot_lat, 'lng': rnd.depot_lng},
        'stops': stops,
        'duration_min': plan['duration_min'], 'distance_km': plan['distance_km'], 'co2_kg': plan['co2_kg'],
        'fuel': plan['fuel'], 'fuel_unit': plan['fuel_unit'], 'path_points': plan['path_points'],
        'start_load_kg': rnd.start_load_kg,
        'load_now_kg': round(rnd.start_load_kg - sum(s['drop_kg'] for s in delivered), 1),
        'delivered_count': len(delivered), 'stop_count': len(stops),
        'next_stop': next((s for s in stops if not s.get('delivered_at')), None),
        'created_at': iso(rnd.created_at), 'started_at': iso(rnd.started_at), 'ended_at': iso(rnd.ended_at),
        'actual_fuel_l': rnd.actual_fuel_l, 'calibration_result': rnd.calibration_result,
        'last_location': {'lat': last.lat, 'lng': last.lng, 'timestamp': iso(last.timestamp)} if last else None,
    }


def busy(model, column, value, statuses):
    return model.query.filter(column == value, model.status.in_(statuses)).first() is not None


def conflicts(driver_id, vehicle_id, round_statuses):
    """True if the driver or vehicle already has an open round (in the given states) or an active trip."""
    from app.models import DispatchedRound, Trip, TripStatus
    return (busy(DispatchedRound, DispatchedRound.driver_id, driver_id, round_statuses)
            or busy(DispatchedRound, DispatchedRound.vehicle_id, vehicle_id, round_statuses)
            or busy(Trip, Trip.driver_id, driver_id, [TripStatus.in_progress])
            or busy(Trip, Trip.vehicle_id, vehicle_id, [TripStatus.in_progress]))


OPEN = [RoundStatus.planned, RoundStatus.in_progress]
