from app import db
import enum
from datetime import datetime, timezone


class RoundStatus(enum.Enum):
    planned = "planned"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class DispatchedRound(db.Model):
    """A multi-stop round planned by an admin and sent to one driver."""
    __tablename__ = 'dispatched_rounds'
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey('drivers.id'), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    status = db.Column(db.Enum(RoundStatus), nullable=False, default=RoundStatus.planned)
    plan_key = db.Column(db.String(20), nullable=False)
    depot_lat = db.Column(db.Float, nullable=False)
    depot_lng = db.Column(db.Float, nullable=False)
    start_load_kg = db.Column(db.Float, nullable=False)
    stops = db.Column(db.JSON, nullable=False)   # visit order: position, index, label, lat, lng, drop_kg, delivered_at
    plan = db.Column(db.JSON, nullable=False)    # totals, legs, path, physics_fuel (uncalibrated)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    started_at = db.Column(db.DateTime)
    ended_at = db.Column(db.DateTime)
    actual_fuel_l = db.Column(db.Float)
    calibration_result = db.Column(db.String(20))

    vehicle = db.relationship('Vehicle')
    driver = db.relationship('Driver')

    __table_args__ = (db.Index('idx_round_driver_status', 'driver_id', 'status'),)


class RoundLog(db.Model):
    __tablename__ = 'round_logs'
    id = db.Column(db.Integer, primary_key=True)
    round_id = db.Column(db.Integer, db.ForeignKey('dispatched_rounds.id'), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.Index('idx_roundlog_round_time', 'round_id', 'timestamp'),)
