from .fleet_reading import FleetReading
from .otp import EmailOTP
from .user import User, UserRole, UserStatus
from .driver import Driver, ApprovalStatus
from .vehicle import Vehicle, VehicleStatus
from .trip import Trip, TripStatus, TripPlan
from .route_logs import Route, TripLog, EventType, Notification
from .others import FuelLog, WeatherLog, Emission, MaintenanceLog, Setting, MLModel, AuditLog
from .calibration import VehicleCalibration
from .dispatch import DispatchedRound, RoundLog, RoundStatus
