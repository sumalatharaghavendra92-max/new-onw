# How GoGreen predicts fuel and CO₂

GoGreen predicts fuel with a physics model. Each vehicle's own trips then correct it over time. Code: `backend/app/ml/physics.py`, `backend/app/services/calibration.py`, `backend/app/services/rounds.py`.

## 1. What goes in (all available before departure)

| Input | Source |
|---|---|
| Road geometry, per-segment distance and typical speed, turns | OSRM public router (live API) |
| Terrain height along the route | Open-Meteo Elevation API (Copernicus DEM, 90 m) |
| Temperature and rain at the start | Open-Meteo Forecast API |
| Vehicle class, fuel, payload | Vehicle record + the driver's cargo entry |

The route is cut into up to 99 stretches of similar length. Each stretch has a length `d`, a travel time `t` (so a speed `v = d/t`) and a rise `h` (so a slope `θ = atan(h/d)`).

## 2. The physics (road-load equation)

To keep moving, the vehicle has to push against three forces on each stretch:

```
F = Crr·m·g·cos θ      rolling resistance (tyres on road)
  + ½·ρ·CdA·v²         air drag (grows with the square of speed)
  + m·g·sin θ          climbing (negative when going downhill)
```

- `m` = curb mass + payload, `g` = 9.81 m/s²
- `Crr`, `CdA` = rolling-resistance coefficient and drag area for the vehicle class (table below). Wet roads raise `Crr` by 15%.
- `ρ` = air density = `101325 / (287.05 · T) · e^(−elevation/8434)`. Hot air and high roads have thinner air, so drag drops.

Work on a stretch = `F · d`. When gravity pulls harder than the resistances (steep downhill), a diesel vehicle wastes that energy in its brakes. An EV recovers 60% of it (regen).

Two more energy costs:

- **Turns and junctions:** each one slows the vehicle to 15 km/h. The kinetic energy `½·m·(v² − v_turn²)` is lost and spent again to speed back up.
- **Accessories and AC:** a constant power draw (lights, compressor, electronics), plus air-conditioning that ramps up from 24 °C to 32 °C. Energy = power × trip time.

## 3. From energy to fuel to CO₂

```
fuel energy = wheel energy / drivetrain efficiency
fuel        = fuel energy / energy per litre (or kg, or kWh)
CO₂         = fuel × emission factor
```

| Fuel | Efficiency | Energy | CO₂ factor | Source |
|---|---|---|---|---|
| Diesel | 30% | 35.8 MJ/L | 2.65 kg/L | IPCC 2006 (74.1 kg/GJ, 43.0 MJ/kg, 0.832 kg/L) |
| Petrol | 24% | 33.0 MJ/L | 2.29 kg/L | IPCC 2006 (69.3 kg/GJ, 44.3 MJ/kg, 0.745 kg/L) |
| CNG | 24% | 48.0 MJ/kg | 2.69 kg/kg | IPCC 2006 (56.1 kg/GJ) |
| Electric | 77% wall-to-wheel | 3.6 MJ/kWh | 0.716 kg/kWh | CEA CO₂ Baseline Database v19, FY 2022-23 |

| Class | Curb mass | CdA | Crr |
|---|---|---|---|
| Car | 1,200 kg | 0.70 m² | 0.011 |
| Van / light truck | 1,600 kg | 2.20 m² | 0.010 |
| Medium truck | 4,500 kg | 5.00 m² | 0.008 |
| Heavy truck | 9,000 kg | 6.50 m² | 0.007 |

The output also splits CO₂ by cause (rolling, drag, climbing, turns, accessories, regen), so you can see *why* one route burns more.

**Sanity check:** a loaded medium diesel truck at 50 km/h comes out at about 17.7 L/100 km (≈5.6 km/L), and a diesel van at about 6.8 L/100 km. Both are in the normal range for Indian fleets (`tests/test_physics.py`).

## 4. Learning from real trips (calibration)

Class-typical parameters are never exact for one specific vehicle. When a driver ends a trip and enters the fuel used, the system stores the ratio `r = reported / predicted`. Each vehicle's correction factor is

```
factor = (3 · 1.0 + Σ r) / (3 + n)
```

This is a shrinkage estimate. With no trips the factor is 1.0. A single trip moves it only a little. After many trips it approaches the vehicle's true average ratio. Ratios outside 0.4–2.5 are rejected as implausible, because reports are typed by drivers and unverified, and the factor is clamped to 0.6–1.8. After 3 trips, the spread of the ratios gives the ± uncertainty shown on every prediction. Until then it shows ±25%.

## 5. Choosing a route (single trip)

OSRM returns up to three real road alternatives. The recommended route has the lowest predicted CO₂ among routes at most 15% slower than the fastest. If the gain is smaller than max(2%, 0.1 kg), the fastest route is kept: tiny predicted differences are not worth the driver's time. Savings are stored with their sign, so a worse choice shows up as negative.

## 6. Ordering a multi-stop round

After every delivery the vehicle gets lighter. So the order of stops changes fuel use, not just time: dropping the heaviest load early means fewer kilometres carrying it. For up to 10 stops, GoGreen finds the **exact** best order with the Held-Karp dynamic programme. It works here because the load on any leg depends only on *which* stops are already done. It optimises:

```
w · CO₂ / CO₂_fastest  +  (1 − w) · time / time_fastest
```

for w = 0, 0.1, …, 1. This gives the fastest plan (w=0), the greenest plan (w=1) and the trade-off curve between them. Times and distances come from the OSRM distance matrix; each leg is costed with the physics model at the load carried on that leg.

Live example (Bengaluru, medium diesel truck, 6,500 kg over 5 stops): the greenest order saved 4.9% CO₂ for 4.2 extra minutes, even though it was 5.5 km longer. That is in line with the 4–8% route-choice savings measured by Ericsson et al. (2006).

## 7. Validation and limits

**Real trips (Vehicle Energy Dataset, `backend/scripts/validate_ved.py`).** 10,119 real petrol-car trips from Ann Arbor, USA, with fuel from the engine's air-flow sensor. Scored on 54 cars (2,231 trips) the model never saw:

| Method | Average error | Bias |
|---|---|---|
| Physics, before the trip | 41.7% | −41% (too little fuel) |
| Physics + per-vehicle learning | 24.8% | −2% |
| Simple baseline: distance × typical L/km | 19.8% | +6% |
| Physics with the real speed trace (after the trip) | 17.6% | −5% |

Plain reading:
- Before a trip, the model cannot see stop-and-go driving, so on its own it predicts too little fuel.
- Learning per vehicle removes that bias, but the simple baseline is still more accurate for planning.
- With the real speed trace, the physics beats the baseline. So the physics is sound; the missing piece is stop-and-go driving, which you only see during the trip. Ahn and Rakha (2008) warn about exactly this.
- These are US petrol cars. Accuracy on Indian diesel trucks is still unknown.

- **Real-data check:** `backend/scripts/evaluate_public_data.py` trains a vehicle-efficiency model on 24,593 FuelEconomy.gov vehicles and tests it on 2,097 from 2023–24. MAE is 0.52 L/100 km vs 2.18 for a baseline, R² 0.91. This validates vehicle efficiency, not trip fuel.
- **No live traffic:** OSRM speeds are typical road speeds, so congestion is not modelled.
- **Class-typical parameters** until a vehicle has calibration trips. Indian-fleet trip telemetry for a full validation has not been collected yet.
- **Turns are approximate:** OSRM maneuvers are counted as slow-downs. For rounds, the number of turns is estimated from road speed.

**Next steps:**
- Fit the residual (`reported − physics`) with gradient boosting on the Vehicle Energy Dataset (Oh, LeBlanc & Peng, 2022), splitting by vehicle and date.
- Add live traffic speeds.
- Add delivery time windows to the round optimiser.
