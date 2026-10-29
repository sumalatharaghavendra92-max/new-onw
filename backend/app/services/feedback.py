from sqlalchemy import func
from app import db
from app.models import Trip, TripPlan, Route, TripStatus
from app.services.trip_workflow import iso
from app.services.calibration import calibration_rows
import json
from pathlib import Path


def public_benchmark():
    """Read only a locally generated evaluation; never train during a request."""
    path = Path(__file__).resolve().parents[2] / 'public_data' / 'evaluation.json'
    try:
        result = json.loads(path.read_text(encoding='utf-8'))
        return result if isinstance(result, dict) else None
    except (OSError, ValueError):
        return None


def feedback_report():
    query = db.session.query(Trip, TripPlan, Route).join(TripPlan, TripPlan.trip_id == Trip.id).join(
        Route, Route.id == TripPlan.selected_route_id).filter(
            Trip.status == TripStatus.completed, ~TripPlan.prediction_mode.ilike('Demo%'))
    eligible = query.count()
    measured = query.filter(Trip.actual_fuel_l.isnot(None))
    error = Trip.actual_fuel_l - Route.predicted_fuel_l
    count, mae, bias = measured.with_entities(func.count(Trip.id), func.avg(func.abs(error)), func.avg(error)).one()
    rows = []
    for trip, plan, route in measured.order_by(Trip.end_time.desc()).limit(30):
        rows.append({'trip_id': trip.id, 'origin': trip.source, 'destination': trip.destination,
                     'predicted_l': route.predicted_fuel_l, 'reported_l': trip.actual_fuel_l,
                     'error_l': round(trip.actual_fuel_l - route.predicted_fuel_l, 3),
                     'model': plan.prediction_mode, 'completed_at': iso(trip.end_time)})
    return {'eligible_trips': eligible, 'reported_trips': count,
            'coverage_percent': round(count / eligible * 100, 1) if eligible else 0,
            'mae_l': round(float(mae), 3) if mae is not None else None,
            'bias_l': round(float(bias), 3) if bias is not None else None,
            'records': rows, 'measurement_source': 'Driver-reported, unverified',
            'evaluation_status': 'Operational diagnostic only; not a held-out model evaluation',
            'automatic_retraining': False, 'public_benchmark': public_benchmark(),
            'calibration': calibration_rows()}
