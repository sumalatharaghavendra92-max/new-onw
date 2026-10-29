from app import db
from datetime import datetime, timezone

class FuelLog(db.Model):
    __tablename__ = 'fuel_logs'
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('trips.id'), nullable=False)
    fuel_used_l = db.Column(db.Float)
    cost = db.Column(db.Float)

class WeatherLog(db.Model):
    __tablename__ = 'weather_logs'
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('trips.id'), nullable=False)
    condition = db.Column(db.String(100))
    temperature = db.Column(db.Float)
    alert_flag = db.Column(db.Boolean, default=False)

class Emission(db.Model):
    __tablename__ = 'emissions'
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('trips.id'), nullable=False)
    route_id = db.Column(db.Integer, db.ForeignKey('routes.id'), nullable=False)
    co2_kg = db.Column(db.Float)
    emission_factor_used = db.Column(db.Float)

class MaintenanceLog(db.Model):
    __tablename__ = 'maintenance_logs'
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=False)
    predicted_risk_score = db.Column(db.Float)
    last_service_date = db.Column(db.Date)
    next_due_date = db.Column(db.Date)

class Setting(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)

class MLModel(db.Model):
    __tablename__ = 'ml_models'
    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(100), nullable=False)
    version = db.Column(db.String(50))
    trained_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    metrics_json = db.Column(db.Text)

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100))
    entity = db.Column(db.String(100))
    entity_id = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
