from app import db
import enum
from datetime import datetime, timezone

class TripStatus(enum.Enum):
    planned = "planned"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"

class Trip(db.Model):
    __tablename__ = 'trips'
    id = db.Column(db.Integer, primary_key=True)
    driver_id = db.Column(db.Integer, db.ForeignKey('drivers.id'), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=False)
    source = db.Column(db.String(255), nullable=False)
    destination = db.Column(db.String(255), nullable=False)
    load_weight_kg = db.Column(db.Float)
    purpose = db.Column(db.String(255))
    preferred_time = db.Column(db.DateTime)
    status = db.Column(db.Enum(TripStatus))
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    actual_fuel_l = db.Column(db.Float)
    actual_co2_kg = db.Column(db.Float)

    driver = db.relationship('Driver', backref='trips')
    vehicle = db.relationship('Vehicle', backref='trips')

    __table_args__ = (
        db.Index('idx_driver_status', 'driver_id', 'status'),
    )


class TripPlan(db.Model):
    """Additive workflow table: existing trip records remain untouched."""
    __tablename__ = 'trip_plans'
    trip_id = db.Column(db.Integer, db.ForeignKey('trips.id'), primary_key=True)
    candidates = db.Column(db.JSON, nullable=False)
    selected_route_id = db.Column(db.Integer, db.ForeignKey('routes.id'))
    baseline_co2_kg = db.Column(db.Float, nullable=False)
    prediction_mode = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    # Nullable unique reservations prevent simultaneous active trips.
    active_driver_id = db.Column(db.Integer, unique=True)
    active_vehicle_id = db.Column(db.Integer, unique=True)
    trip = db.relationship('Trip', backref=db.backref('plan', uselist=False))
