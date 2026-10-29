"""Interactive local administration: no predefined or demo accounts."""
import csv
from pathlib import Path
import click
import bcrypt
from app import db
from app.models import User, UserRole, Vehicle, VehicleStatus, FleetReading


def register_commands(app):
    @app.cli.command('create-admin')
    @click.option('--email', prompt=True)
    @click.option('--name', prompt=True)
    @click.option('--phone', prompt=True)
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
    def create_admin(email, name, phone, password):
        email = email.strip().lower()
        if '@' not in email or not name.strip() or not phone.strip():
            raise click.ClickException('A valid email, name and phone are required.')
        if not 8 <= len(password.encode('utf-8')) <= 72:
            raise click.ClickException('Password must be 8–72 bytes.')
        if User.query.filter((User.email == email) | (User.phone == phone)).first():
            raise click.ClickException('Email or phone already exists. No account was changed.')
        user = User(email=email, name=name.strip(), phone=phone.strip(), role=UserRole.admin,
                    password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode())
        db.session.add(user)
        db.session.commit()
        click.echo('Your administrator account is ready. Sign in with password and email code.')

    @app.cli.command('import-sample-fleet')
    def import_sample_fleet():
        """Import 25 fictional vehicle profiles; no fake live GPS or accounts."""
        path = Path(__file__).resolve().parents[1] / 'data' / 'sample_fleet.csv'
        count = 0
        with path.open(newline='') as f:
            for row in csv.DictReader(f):
                if Vehicle.query.filter_by(vehicle_no=row['vehicle_no']).first():
                    continue
                v = Vehicle(vehicle_no=row['vehicle_no'], type=row['type'], fuel_type=row['fuel_type'],
                    load_capacity_kg=float(row['load_capacity_kg']),
                    emission_factor_g_per_km=float(row['emission_factor_g_per_km']),
                    status=VehicleStatus[row['status']])
                db.session.add(v)
                db.session.flush()
                db.session.add(FleetReading(vehicle_id=v.id, fuel_percent=float(row['fuel_percent']),
                    load_kg=float(row['load_kg']), odometer_km=float(row['odometer_km']), source='sample'))
                count += 1
        db.session.commit()
        click.echo(f'Imported {count} fictional sample vehicles. Existing vehicles preserved. No live readings created.')
