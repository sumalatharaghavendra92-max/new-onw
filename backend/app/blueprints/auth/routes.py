from flask import Blueprint, request, jsonify
from app import db, limiter
from app.models import User, Driver, UserRole
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
import bcrypt
import secrets
import time

auth_bp = Blueprint('auth', __name__)

from app.models import EmailOTP, UserStatus
from app.services.email_delivery import send_otp
from werkzeug.security import generate_password_hash, check_password_hash
import re

OTP_TTL_SECONDS = 600


def _otp_valid(email, otp, purpose='register'):
    record = EmailOTP.query.filter_by(email=email, purpose=purpose).first()
    if not record or time.time() > record.expires_at or record.attempts >= 5:
        return False
    if not check_password_hash(record.code_hash, str(otp)):
        record.attempts += 1
        db.session.commit()
        return False
    return True


def _send_code(email, purpose):
    record = EmailOTP.query.filter_by(email=email, purpose=purpose).first()
    now = time.time()
    if record and now - record.sent_at < 60:
        return jsonify(message='Please wait 60 seconds before requesting another code.'), 429
    code = f'{secrets.randbelow(10**6):06d}'
    try:
        send_otp(email, code)
    except Exception:
        # Provider exceptions can contain credentials or message bodies: do not log them.
        return jsonify(message='Email delivery failed. Ask the administrator to check email provider configuration.'), 503
    if not record:
        record = EmailOTP(email=email, purpose=purpose)
        db.session.add(record)
    record.code_hash = generate_password_hash(code)
    record.expires_at = now + OTP_TTL_SECONDS
    record.sent_at = now
    record.attempts = 0
    db.session.commit()
    return jsonify(message='Verification code sent to your email.', otp_required=True), 200


@auth_bp.route('/request-otp', methods=['POST'])
@limiter.limit('5 per minute')
def request_otp():
    data = request.get_json() or {}
    email = str(data.get('email', '')).strip().lower()
    if len(email) > 120 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        return jsonify(message='Enter a valid email address.'), 422
    return _send_code(email, 'register')


@auth_bp.route('/verify-otp', methods=['POST'])
@limiter.limit("10 per minute")
def verify_otp():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    otp = data.get('otp', '').strip()
    if not email or not otp:
        return jsonify({"error": "validation_error", "message": "Email and OTP required"}), 422

    if not _otp_valid(email, otp):
        return jsonify({"error": "invalid_otp", "message": "Invalid or expired OTP"}), 400

    return jsonify({"message": "OTP verified", "verified": True}), 200


@auth_bp.route('/register', methods=['POST'])
@limiter.limit('10 per minute')
def register():
    data = request.get_json() or {}
    required = ['email', 'name', 'phone', 'password', 'otp']
    for field in required:
        if not data.get(field):
            return jsonify({"error": "validation_error", "message": f"{field} is required"}), 422

    email = data['email'].strip().lower()
    otp = data['otp'].strip()

    if not 8 <= len(data['password'].encode('utf-8')) <= 72:
        return jsonify(message='Password must be 8–72 bytes.'), 422

    # Verify OTP first
    if not _otp_valid(email, otp):
        return jsonify({"error": "invalid_otp", "message": "Invalid or expired OTP. Please restart registration."}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "conflict", "message": "An account with this email already exists"}), 409

    if User.query.filter_by(phone=data['phone']).first():
        return jsonify({"error": "conflict", "message": "An account with this phone already exists"}), 409

    pw_hash = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user = User(
        name=data['name'],
        email=email,
        phone=data['phone'],
        password_hash=pw_hash,
        role=UserRole.driver
    )
    db.session.add(user)
    db.session.flush()  # get user.id

    # Parse dob string to date
    from datetime import datetime
    try:
        dob_date = datetime.strptime(data.get('dob'), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        dob_date = None

    driver = Driver(
        user_id=user.id,
        dob=dob_date,
        address=data.get('address'),
        license_no=data.get('license_no'),
        experience_years=data.get('experience_years'),
        emergency_contact=data.get('emergency_contact'),
    )
    from app.blueprints.admin.routes import read_settings
    if read_settings()['auto_approve_drivers']:
        from app.models import ApprovalStatus
        driver.approval_status = ApprovalStatus.approved
    db.session.add(driver)
    EmailOTP.query.filter_by(email=email, purpose='register').delete()
    db.session.commit()

    return jsonify({"message": "Registration submitted.", "driver_id": driver.id}), 201


@auth_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not isinstance(password, str) or len(password.encode('utf-8')) > 72:
        return jsonify(message='Invalid email or password'), 401
    if not email or not password:
        return jsonify({"error": "validation_error", "message": "Email and password required"}), 422

    user = User.query.filter_by(email=email).first()
    if user and bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
        if user.status != UserStatus.active:
            return jsonify(message='Account is inactive.'), 403
        # For drivers, verify approval status
        if user.role == UserRole.driver:
            driver = Driver.query.filter_by(user_id=user.id).first()
            if driver and driver.approval_status.value != 'approved':
                return jsonify({
                    "error": "not_approved",
                    "message": f"Your account is {driver.approval_status.value}. Please wait for admin approval.",
                    "status": driver.approval_status.value
                }), 403

        otp = str(data.get('otp', '')).strip()
        if not otp:
            return _send_code(email, 'login')
        if not _otp_valid(email, otp, 'login'):
            return jsonify(message='Invalid or expired code. Request a new code after five failed attempts.'), 400
        EmailOTP.query.filter_by(email=email, purpose='login').delete()
        db.session.commit()
        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))
        return jsonify({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "role": user.role.value,
            "name": user.name
        }), 200

    return jsonify({"error": "invalid_credentials", "message": "Invalid email or password"}), 401


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    access_token = create_access_token(identity=identity)
    return jsonify({"access_token": access_token}), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_me():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "not_found", "message": "User not found"}), 404

    result = {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "role": user.role.value
    }

    if user.role == UserRole.driver:
        driver = Driver.query.filter_by(user_id=user.id).first()
        if driver:
            result["driver"] = {
                "id": driver.id,
                "approval_status": driver.approval_status.value,
                "license_no": driver.license_no,
                "experience_years": driver.experience_years,
            }
            # Include assigned vehicle
            from app.models import Vehicle
            vehicle = Vehicle.query.filter_by(assigned_driver_id=driver.id).first()
            if vehicle:
                result["driver"]["vehicle"] = {
                    "id": vehicle.id,
                    "vehicle_no": vehicle.vehicle_no,
                    "type": vehicle.type,
                    "fuel_type": vehicle.fuel_type,
                    "load_capacity_kg": vehicle.load_capacity_kg,
                    "emission_factor_g_per_km": vehicle.emission_factor_g_per_km,
                    "status": vehicle.status.value
                }

    return jsonify(result), 200
