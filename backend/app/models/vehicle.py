from app import db
import enum

class VehicleStatus(enum.Enum):
    active = "active"
    maintenance = "maintenance"
    retired = "retired"

class Vehicle(db.Model):
    __tablename__ = 'vehicles'
    id = db.Column(db.Integer, primary_key=True)
    vehicle_no = db.Column(db.String(50), unique=True, nullable=False)
    type = db.Column(db.String(50))
    fuel_type = db.Column(db.String(50))
    load_capacity_kg = db.Column(db.Float)
    emission_factor_g_per_km = db.Column(db.Float)
    assigned_driver_id = db.Column(db.Integer, db.ForeignKey('drivers.id'))
    status = db.Column(db.Enum(VehicleStatus), default=VehicleStatus.active)

    assigned_driver = db.relationship('Driver', backref='assigned_vehicles')
