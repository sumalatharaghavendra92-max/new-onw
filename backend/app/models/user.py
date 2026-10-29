from app import db
import enum
from datetime import datetime, timezone

class UserRole(enum.Enum):
    admin = "admin"
    driver = "driver"

class UserStatus(enum.Enum):
    active = "active"
    inactive = "inactive"

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.Enum(UserRole), nullable=False)
    status = db.Column(db.Enum(UserStatus), default=UserStatus.active)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
