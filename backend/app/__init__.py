import os
import secrets
from flask import Flask, app
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
cors = CORS()
limiter = Limiter(key_func=get_remote_address, default_limits=["2000 per day", "500 per hour"])

def create_app(test_config=None):
    app = Flask(__name__)

    # Default config
    # Never fall back to a guessable secret: without env values, use a random
    # per-process key (sessions end on restart) and say so.
    for key in ('SECRET_KEY', 'JWT_SECRET_KEY'):
        app.config[key] = os.environ.get(key) or secrets.token_hex(32)
        if not os.environ.get(key) and not test_config:
            app.logger.warning('%s is not set; using a random key for this process.', key)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///gogreen.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    if test_config:
        app.config.update(test_config)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    cors_origins = os.environ.get('CORS_ORIGINS', 'http://localhost:5173')
    if cors_origins == '*':
        cors.init_app(app)
    else:
        cors.init_app(app, resources={r"/api/*": {"origins": cors_origins.split(',')}})

    limiter.init_app(app)

    from flask import request, jsonify
    from werkzeug.exceptions import HTTPException

    @app.before_request
    def validate_json_object():
        if request.is_json and request.method in ('POST', 'PATCH', 'PUT'):
            if not isinstance(request.get_json(), dict):
                return jsonify(message='JSON request body must be an object.'), 422

    @app.errorhandler(HTTPException)
    def api_error(exc):
        return jsonify(message=exc.description, error=exc.name), exc.code

    # Import models so Flask-Migrate can detect them
    from app.models import (User, Driver, Vehicle, Trip, Route, TripLog,
                             FuelLog, WeatherLog, Emission, MaintenanceLog,
                             Notification, Setting, MLModel, AuditLog)

    # Register blueprints
    from app.blueprints.auth.routes import auth_bp
    from app.blueprints.drivers.routes import drivers_bp
    from app.blueprints.vehicles.routes import vehicles_bp
    from app.blueprints.trips.routes import trips_bp
   
    from app.blueprints.notifications.routes import notifications_bp
    from app.blueprints.ai import ai_bp
   
    from app.blueprints.admin.routes import admin_bp
    from app.blueprints.reports.routes import reports_bp
    from app.blueprints.context.routes import context_bp

    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(drivers_bp, url_prefix='/api/v1/drivers')
    app.register_blueprint(vehicles_bp, url_prefix='/api/v1/vehicles')
    app.register_blueprint(trips_bp, url_prefix='/api/v1/trips')
    app.register_blueprint(ai_bp, url_prefix='/api/ai')
    app.register_blueprint(ai_bp, url_prefix='/api/v1/ai', name='ai_v1')
    app.register_blueprint(notifications_bp, url_prefix='/api/v1/notifications')
    app.register_blueprint(admin_bp, url_prefix='/api/v1/admin')
    app.register_blueprint(reports_bp, url_prefix='/api/v1/reports')
    app.register_blueprint(context_bp, url_prefix='/api/v1/context')
    from app.blueprints.rounds import rounds_bp
    app.register_blueprint(rounds_bp, url_prefix='/api/v1/rounds')

    @app.cli.command('init-db')
    def init_db():
        """Create missing tables without deleting existing data."""
        db.create_all()
        print('Database tables ready; existing records preserved.')

    from app.commands import register_commands
    register_commands(app)

    return app
