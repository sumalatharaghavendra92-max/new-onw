from app import db
from datetime import datetime, timezone


class VehicleCalibration(db.Model):
    """Running statistics of reported fuel / physics-predicted fuel for one vehicle."""
    __tablename__ = 'vehicle_calibrations'
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), primary_key=True)
    trips = db.Column(db.Integer, nullable=False, default=0)
    ratio_sum = db.Column(db.Float, nullable=False, default=0.0)
    ratio_sq_sum = db.Column(db.Float, nullable=False, default=0.0)
    rejected = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    vehicle = db.relationship('Vehicle', backref=db.backref('calibration', uselist=False))
