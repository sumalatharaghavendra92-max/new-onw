"""Evidence available at planning time: what the prediction rests on and where it is weak."""
from app.ml import physics


def evidence_for(vehicle, load, details, mode):
    vehicle_key = physics.vehicle_class(vehicle.type)
    fuel_key = physics.fuel_kind(vehicle.fuel_type, vehicle.type)
    out_of_domain, notes = [], []
    if not vehicle_key:
        out_of_domain.append(f'Vehicle type "{vehicle.type}" has no physics profile. Use car, van, truck or heavy truck.')
    if not fuel_key:
        out_of_domain.append(f'Fuel "{vehicle.fuel_type}" is not modelled; supported: diesel, petrol, CNG, electric.')
    if details['elevation_status'] != 'available':
        notes.append('Hill data unavailable, so the road is treated as flat.')
    if details['weather_status'] == 'unavailable':
        notes.append(f'Weather unavailable: we assumed {details["temp_c"]:.0f} °C and a dry road.')
    notes.append('Road speeds are normal speeds, not live traffic.')
    if mode.startswith('Hybrid'):
        notes.append('Includes an ML correction learned from real petrol-car trips (USA).')
    return {
        'schema': 'planning-evidence-v2', 'within_documented_domain': not out_of_domain,
        'limitations': out_of_domain + notes,
        'inputs': {'vehicle_class': vehicle_key, 'fuel': fuel_key, 'cargo_kg': load,
                   'temperature_c': round(details['temp_c'], 1), 'wet_road': details['wet_road'],
                   'weather_status': details['weather_status'], 'elevation_status': details['elevation_status'],
                   'turns': details['turns'], 'road_speeds': 'OSRM typical speeds'},
        'routing_provider': 'OSRM driving', 'truck_restrictions_verified': False,
        'model': physics.MODEL_VERSION, 'prediction_mode': mode,
        'confidence': f'±{details["uncertainty_pct"]:.0f}% '
                      + ('(learned from this vehicle\'s trips)' if details['calibration_trips'] >= 3 else '(class default, not yet calibrated)'),
    }
