from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from app import db
from app.models import Driver, Vehicle, Trip, TripStatus
from app.models.driver import ApprovalStatus
from app.utils.rbac import role_required
from sqlalchemy import func

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/learning', methods=['GET'])
@role_required('admin')
def learning():
    from app.services.feedback import feedback_report
    return jsonify(feedback_report())

@admin_bp.route('/stats', methods=['GET'])
@role_required('admin')
def get_stats():
    from app.services.analytics import summary
    return jsonify(summary()), 200


@admin_bp.route('/fleet', methods=['GET'])
@role_required('admin')
def get_fleet():
    from app.services.trip_workflow import serialize
    from app.services.dispatch import serialize_round
    from app.models import DispatchedRound, RoundStatus
    return jsonify(trips=[serialize(t) for t in Trip.query.filter_by(status=TripStatus.in_progress).all()],
                   rounds=[serialize_round(r) for r in DispatchedRound.query.filter_by(status=RoundStatus.in_progress).all()])


from app.models import Setting
import json

DEFAULT_SETTINGS = {'auto_approve_drivers': False, 'strict_routing': True, 'ml_retrain_interval_days': 7}


def read_settings():
    result = dict(DEFAULT_SETTINGS)
    for setting in Setting.query.filter(Setting.key.in_(DEFAULT_SETTINGS)).all():
        result[setting.key] = json.loads(setting.value)
    return result


@admin_bp.route('/settings', methods=['GET'])
@role_required('admin')
def get_settings():
    return jsonify(read_settings())


@admin_bp.route('/settings', methods=['PATCH'])
@role_required('admin')
def update_settings():
    data = request.get_json() or {}
    for key, value in data.items():
        if key not in DEFAULT_SETTINGS:
            return jsonify(message='Unknown setting.'), 422
        if key == 'ml_retrain_interval_days':
            if type(value) is not int or not 1 <= value <= 365:
                return jsonify(message='Review interval must be 1–365 days.'), 422
        elif type(value) is not bool:
            return jsonify(message='Business rules must be true or false.'), 422
    for key, value in data.items():
        record = Setting.query.filter_by(key=key).first()
        if not record:
            record = Setting(key=key)
            db.session.add(record)
        record.value = json.dumps(value)
    db.session.commit()
    return jsonify(message='Settings saved.', settings=read_settings())


@admin_bp.route('/backup', methods=['POST'])
@role_required('admin')
def trigger_backup():
    from flask import send_file
    import sqlite3
    import tempfile
    from io import BytesIO
    if db.engine.dialect.name != 'sqlite':
        return jsonify(message='Use your database provider backup tool for this database.'), 501
    with tempfile.TemporaryDirectory() as folder:
        destination = folder + '/backup.db'
        source = db.engine.raw_connection()
        try:
            with sqlite3.connect(destination) as target:
                source.driver_connection.backup(target)
        finally:
            source.close()
        with open(destination, 'rb') as f:
            content = BytesIO(f.read())
    return send_file(content, mimetype='application/octet-stream', as_attachment=True, download_name='gogreen-backup.db')


@admin_bp.route('/restore', methods=['POST'])
@role_required('admin')
def trigger_restore():
    return jsonify(message='Automatic restore is unavailable. Stop the server and restore your SQLite backup as described in SETUP_EXPO.md.'), 501
