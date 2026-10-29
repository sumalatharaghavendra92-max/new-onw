"""Per-vehicle learning loop.

The physics model uses class-typical parameters. Each completed trip with a
reported fuel figure gives one ratio  r = reported / physics prediction.
The vehicle's correction factor is a shrinkage estimate that starts at 1.0 and
moves towards the mean ratio as trips accumulate:

    factor = (PRIOR_TRIPS · 1.0 + Σ r) / (PRIOR_TRIPS + n)

Reports are driver-entered and unverified, so implausible ratios are rejected
instead of learned, and the factor is clamped.
"""
import math
from datetime import datetime, timezone

from app import db
from app.models import VehicleCalibration
from app.ml import physics

PRIOR_TRIPS = 3
RATIO_RANGE = (0.4, 2.5)
FACTOR_RANGE = (0.6, 1.8)
DEFAULT_UNCERTAINTY_PCT = 25.0


def factor_and_uncertainty(calibration):
    """Correction factor and ± percentage uncertainty for one vehicle."""
    if not calibration or calibration.trips == 0:
        return 1.0, DEFAULT_UNCERTAINTY_PCT
    n = calibration.trips
    factor = (PRIOR_TRIPS + calibration.ratio_sum) / (PRIOR_TRIPS + n)
    factor = min(FACTOR_RANGE[1], max(FACTOR_RANGE[0], factor))
    if n < 3:
        return factor, DEFAULT_UNCERTAINTY_PCT
    mean = calibration.ratio_sum / n
    variance = max(0.0, calibration.ratio_sq_sum / n - mean * mean)
    spread = math.sqrt(variance) / mean * 100
    return factor, round(min(40.0, max(5.0, spread)), 1)


def learn_from_trip(vehicle, physics_fuel, reported_fuel):
    """Record one completed trip. Returns 'learned', 'rejected' or 'skipped'."""
    if physics_fuel is None or reported_fuel is None or physics_fuel <= 0:
        return 'skipped'
    if vehicle.calibration is None:
        vehicle.calibration = VehicleCalibration(trips=0, ratio_sum=0.0, ratio_sq_sum=0.0, rejected=0)
        db.session.add(vehicle.calibration)
    calibration = vehicle.calibration
    ratio = reported_fuel / physics_fuel
    calibration.updated_at = datetime.now(timezone.utc)
    if not RATIO_RANGE[0] <= ratio <= RATIO_RANGE[1]:
        calibration.rejected += 1
        return 'rejected'
    calibration.trips += 1
    calibration.ratio_sum += ratio
    calibration.ratio_sq_sum += ratio * ratio
    return 'learned'


def calibration_rows():
    from app.models import Vehicle
    rows = []
    for vehicle in Vehicle.query.order_by(Vehicle.vehicle_no).all():
        factor, uncertainty = factor_and_uncertainty(vehicle.calibration)
        cal = vehicle.calibration
        rows.append({'vehicle_no': vehicle.vehicle_no, 'class': physics.vehicle_class(vehicle.type),
                     'fuel': physics.fuel_kind(vehicle.fuel_type, vehicle.type),
                     'trips': cal.trips if cal else 0, 'rejected': cal.rejected if cal else 0,
                     'factor': round(factor, 3), 'uncertainty_pct': uncertainty,
                     'updated_at': cal.updated_at.replace(tzinfo=timezone.utc).isoformat() if cal and cal.updated_at else None})
    return rows
