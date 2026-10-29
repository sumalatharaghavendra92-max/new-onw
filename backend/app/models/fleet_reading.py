from app import db

class FleetReading(db.Model):
    __tablename__ = 'fleet_readings'
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), primary_key=True)
    fuel_percent = db.Column(db.Float, nullable=False)
    load_kg = db.Column(db.Float, nullable=False)
    odometer_km = db.Column(db.Float, nullable=False)
    source = db.Column(db.String(20), nullable=False)
    recorded_at = db.Column(db.String(40))

    def to_dict(self):
        return {k: getattr(self, k) for k in ('fuel_percent', 'load_kg', 'odometer_km', 'source', 'recorded_at')}
