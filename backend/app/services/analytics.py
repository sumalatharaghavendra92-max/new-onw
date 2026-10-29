from datetime import timedelta
from sqlalchemy import func
from app import db
from app.models import Trip, TripStatus, TripPlan, Route, Driver, Vehicle, ApprovalStatus
from app.services.trip_workflow import serialize, utcnow, iso


def summary():
    comparable = db.session.query(Trip, TripPlan, Route).join(TripPlan, TripPlan.trip_id == Trip.id).join(
        Route, Route.id == TripPlan.selected_route_id).filter(
            Trip.status == TripStatus.completed,
            func.coalesce(TripPlan.candidates[0]['decisionPolicy']['eco_ranking_withheld'].as_boolean(), False) == False)
    savings = TripPlan.baseline_co2_kg - Route.predicted_co2_kg
    count, saved, distance, co2 = comparable.with_entities(
        func.count(Trip.id), func.sum(savings), func.sum(Route.distance_km), func.sum(Route.predicted_co2_kg)).one()
    today = utcnow().date()
    days = []
    daily = comparable.filter(Trip.end_time >= today - timedelta(days=6)).with_entities(
        func.date(Trip.end_time), func.count(Trip.id), func.sum(savings)).group_by(func.date(Trip.end_time)).all()
    values = {str(day): (n, float(kg or 0)) for day, n, kg in daily}
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        n, kg = values.get(day.isoformat(), (0, 0))
        days.append({'date': day.isoformat(), 'label': day.strftime('%a'), 'trips': n, 'savings': round(kg, 2)})
    return {
        'total_drivers': Driver.query.filter_by(approval_status=ApprovalStatus.approved).count(),
        'pending_approvals': Driver.query.filter_by(approval_status=ApprovalStatus.pending).count(),
        'total_vehicles': Vehicle.query.count(),
        'active_trips': Trip.query.filter_by(status=TripStatus.in_progress).count(),
        'planned_trips': Trip.query.filter_by(status=TripStatus.planned).count(),
        'total_trips': Trip.query.filter_by(status=TripStatus.completed).count(),
        'comparable_trips': count, 'co2_saved_kg': round(float(saved or 0), 2),
        'distance_km': round(float(distance or 0), 1), 'predicted_co2_kg': round(float(co2 or 0), 2),
        'daily': days, 'updated_at': iso(utcnow()),
        'recent_trips': [serialize(t) for t in Trip.query.order_by(Trip.id.desc()).limit(8).all()],
    }
