"""Physics-based fuel and CO2 model built on the road-load equation.

For every stretch of road the vehicle must overcome

    F = Crr·m·g·cos(θ)  +  ½·ρ·CdA·v²  +  m·g·sin(θ)
        rolling            air drag       climbing

and it loses ½·m·v² of kinetic energy every time it slows for a turn or stop.
Accessories (and air-conditioning when it is hot) draw power for the whole
trip. Wheel energy divided by drivetrain efficiency gives the energy taken from
the tank (or the grid), and IPCC / CEA factors turn that into CO2.

Parameters are typical published values for each vehicle class, not measured
for a specific vehicle. The learning loop (services/calibration.py) corrects
each vehicle from its own reported fuel.
"""
import math
import re

G = 9.81
R_AIR = 287.05          # J/(kg·K), specific gas constant of dry air
SCALE_HEIGHT_M = 8434   # isothermal atmosphere scale height
TURN_SPEED_MS = 15 / 3.6
MODEL_VERSION = 'physics-road-load-v1'


def _fuel(kg_co2_per_gj, mj_per_unit, unit, source):
    return {'unit': unit, 'mj_per_unit': mj_per_unit,
            'co2_kg_per_unit': round(kg_co2_per_gj * mj_per_unit / 1000, 4), 'source': source}


# IPCC 2006 Guidelines, Vol. 2 Ch. 3 default CO2 factors and net calorific values.
FUELS = {
    'diesel': _fuel(74.1, 43.0 * 0.832, 'L', 'IPCC 2006: 74.1 kg CO2/GJ, NCV 43.0 MJ/kg, density 0.832 kg/L'),
    'petrol': _fuel(69.3, 44.3 * 0.745, 'L', 'IPCC 2006: 69.3 kg CO2/GJ, NCV 44.3 MJ/kg, density 0.745 kg/L'),
    'cng': _fuel(56.1, 48.0, 'kg', 'IPCC 2006: 56.1 kg CO2/GJ, NCV 48.0 MJ/kg'),
    # Grid electricity: CEA CO2 Baseline Database v19, FY 2022-23 weighted average.
    'electric': {'unit': 'kWh', 'mj_per_unit': 3.6, 'co2_kg_per_unit': 0.716,
                 'source': 'CEA CO2 Baseline Database v19 (FY 2022-23): 0.716 kg CO2/kWh'},
}

# Tank-to-wheel (or wall-to-wheel) efficiency in typical mixed driving, the
# efficiency of running accessories at low engine load, and the share of
# braking energy recovered.
POWERTRAINS = {
    'diesel':   {'drive': 0.30, 'aux': 0.15, 'regen': 0.0},
    'petrol':   {'drive': 0.24, 'aux': 0.12, 'regen': 0.0},
    'cng':      {'drive': 0.24, 'aux': 0.12, 'regen': 0.0},
    'electric': {'drive': 0.77, 'aux': 0.85, 'regen': 0.6},
}

# Typical published ranges per vehicle class.
PROFILES = {
    'car':         {'label': 'Car',                 'curb_kg': 1200, 'cda_m2': 0.70, 'crr': 0.011, 'aux_kw': 0.4, 'ac_kw': 1.0},
    'van':         {'label': 'Van / light truck',   'curb_kg': 1600, 'cda_m2': 2.20, 'crr': 0.010, 'aux_kw': 0.6, 'ac_kw': 1.5},
    'truck':       {'label': 'Medium truck',        'curb_kg': 4500, 'cda_m2': 5.00, 'crr': 0.008, 'aux_kw': 1.2, 'ac_kw': 2.0},
    'heavy_truck': {'label': 'Heavy truck',         'curb_kg': 9000, 'cda_m2': 6.50, 'crr': 0.007, 'aux_kw': 1.8, 'ac_kw': 2.5},
}

_CLASS_WORDS = [
    ('heavy_truck', ('heavy', 'trailer', 'lorry', 'tipper', 'hcv', 'tractor')),
    ('van', ('mini truck', 'minitruck', 'pickup', 'pick up', 'tempo', 'lcv', 'van', 'ace')),
    ('truck', ('truck', 'icv', 'mcv')),
    ('car', ('car', 'sedan', 'hatchback', 'suv')),
]
_FUEL_WORDS = [('electric', ('electric', 'ev', 'battery')), ('cng', ('cng',)),
               ('diesel', ('diesel',)), ('petrol', ('petrol', 'gasoline'))]


def _match(text, table):
    """Whole-word lookup, so 'Spaceship' never matches 'ace'."""
    padded = ' ' + re.sub(r'[^a-z0-9]+', ' ', (text or '').lower()) + ' '
    for key, words in table:
        if any(f' {word} ' in padded or f' {word}s ' in padded for word in words):
            return key
    return None


def vehicle_class(text):
    return _match(text, _CLASS_WORDS)


def fuel_kind(text, vehicle_text=''):
    return _match(text, _FUEL_WORDS) or _match(vehicle_text, _FUEL_WORDS)


def air_density(temp_c, elevation_m=0.0):
    return 101325 / (R_AIR * (temp_c + 273.15)) * math.exp(-elevation_m / SCALE_HEIGHT_M)


def estimate(segments, vehicle_key, fuel_key, payload_kg, temp_c=25.0, wet_road=False, turns=0):
    """Fuel and CO2 for a route given as segments.

    segments: [{'distance_m', 'duration_s', 'rise_m', 'elevation_m'}], in travel order.
    turns: slow-downs for turns or junctions; each costs the kinetic energy between
    cruise speed and turning speed.
    """
    profile, fuel, power = PROFILES[vehicle_key], FUELS[fuel_key], POWERTRAINS[fuel_key]
    mass = profile['curb_kg'] + max(0.0, payload_kg)
    crr = profile['crr'] * (1.15 if wet_road else 1.0)
    rolling = aero = climb = recovered = 0.0
    distance = duration = total_rise = 0.0
    for seg in segments:
        d, t = float(seg['distance_m']), float(seg['duration_s'])
        if d <= 0 or t <= 0:
            continue
        v = d / t
        theta = math.atan2(float(seg.get('rise_m', 0.0)), d)
        f_roll = crr * mass * G * math.cos(theta)
        f_aero = 0.5 * air_density(temp_c, float(seg.get('elevation_m', 0.0))) * profile['cda_m2'] * v * v
        f_grade = mass * G * math.sin(theta)
        net = f_roll + f_aero + f_grade
        if net >= 0:
            # Attribute the work to each force; downhill pull lowers what is needed.
            rolling += f_roll * d
            aero += f_aero * d
            climb += max(0.0, f_grade) * d
            if f_grade < 0:
                rolling += f_grade * d * f_roll / (f_roll + f_aero)
                aero += f_grade * d * f_aero / (f_roll + f_aero)
        else:
            # Gravity exceeds resistance: the vehicle brakes, an EV recovers part of it.
            recovered += -net * d * power['regen']
        distance += d
        duration += t
        total_rise += max(0.0, float(seg.get('rise_m', 0.0)))

    cruise = distance / duration if duration else 0.0
    turn_drop = max(0.0, min(cruise, 50 / 3.6) ** 2 - TURN_SPEED_MS ** 2)
    stops = turns * 0.5 * mass * turn_drop * (1 - power['regen'])

    ac_share = min(1.0, max(0.0, (temp_c - 24) / 8))
    aux_w = (profile['aux_kw'] + profile['ac_kw'] * ac_share) * 1000

    wheel_j = {'rolling': rolling, 'aero': aero, 'grade': climb, 'stops': stops}
    source_mj = {k: v / power['drive'] / 1e6 for k, v in wheel_j.items()}
    source_mj['auxiliary'] = aux_w * duration / power['aux'] / 1e6
    source_mj['regen'] = -recovered / power['drive'] / 1e6
    total_mj = max(0.0, sum(source_mj.values()))

    quantity = total_mj / fuel['mj_per_unit']
    co2_per_mj = fuel['co2_kg_per_unit'] / fuel['mj_per_unit']
    return {
        'model': MODEL_VERSION,
        'fuel': round(quantity, 3),
        'fuel_unit': fuel['unit'],
        'co2_kg': round(quantity * fuel['co2_kg_per_unit'], 3),
        'co2_breakdown_kg': {k: round(v * co2_per_mj, 3) for k, v in source_mj.items()},
        'energy_mj': round(total_mj, 2),
        'mass_kg': round(mass),
        'distance_km': round(distance / 1000, 3),
        'avg_speed_kmh': round(cruise * 3.6, 1),
        'climb_m': round(total_rise),
        'turns': turns,
        'ac_share': round(ac_share, 2),
    }


def reference_co2_per_km(vehicle_key, fuel_key, capacity_kg):
    """CO2/km for this vehicle class in typical mixed driving: half its capacity, 55 km/h,
    gently rolling road (±30 m every 5 km), 4 junctions per 10 km, 28 °C."""
    rolling = [{'distance_m': 5000, 'duration_s': 5000 / (55 / 3.6), 'rise_m': 30, 'elevation_m': 0},
               {'distance_m': 5000, 'duration_s': 5000 / (55 / 3.6), 'rise_m': -30, 'elevation_m': 0}]
    result = estimate(rolling, vehicle_key, fuel_key, 0.5 * (capacity_kg or 0), temp_c=28, turns=4)
    return result['co2_kg'] / 10


def eco_score(co2_kg, distance_km, reference_per_km):
    """50 = the class reference; 100 = zero CO2; 0 = twice the reference CO2/km."""
    if distance_km <= 0 or reference_per_km <= 0:
        return 0.0
    ratio = co2_kg / distance_km / reference_per_km
    return round(max(0.0, min(100.0, 50 * (2 - ratio))), 1)
