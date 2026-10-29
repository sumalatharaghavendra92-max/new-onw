from app import db
import enum
from datetime import datetime, timezone

class Route(db.Model):
    __tablename__ = 'routes'
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('trips.id'), nullable=False)
    route_label = db.Column(db.String(50))
    distance_km = db.Column(db.Float)
    traffic_density = db.Column(db.String(50))
    avg_speed = db.Column(db.Float)
    predicted_fuel_l = db.Column(db.Float)
    predicted_co2_kg = db.Column(db.Float)
    eco_score = db.Column(db.Float)
    is_recommended = db.Column(db.Boolean, default=False)
    
    trip = db.relationship('Trip', backref='routes')

    __table_args__ = (
        db.Index('idx_route_trip', 'trip_id'),
    )

class EventType(enum.Enum):
    deviation = "deviation"
    alert = "alert"
    checkpoint = "checkpoint"

class TripLog(db.Model):
    __tablename__ = 'trip_logs'
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('trips.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    event_type = db.Column(db.Enum(EventType))

    trip = db.relationship('Trip', backref='logs')

    __table_args__ = (
        db.Index('idx_triplog_trip_time', 'trip_id', 'timestamp'),
    )

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(50))
    message = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref='notifications')

    __table_args__ = (
        db.Index('idx_notif_user_read', 'user_id', 'is_read'),
    )
