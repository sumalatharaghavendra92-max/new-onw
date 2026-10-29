# GoGreen: eco-routing and emissions accounting for small fleets

GoGreen plans delivery trips and multi-stop rounds that cut both travel time and CO₂, and tracks them.

**What it does:**
- **Predicts fuel and CO₂** for each road option with a physics model. Inputs come from live public APIs: OSRM for roads, and Open-Meteo for weather and terrain.
- **Learns each vehicle's real consumption** from completed trips.

**Two portals:**
- **Drivers:** plan a trip, pick a route, track by GPS, report fuel.
- **Admins:**
  - approve drivers and manage vehicles
  - optimise multi-stop rounds and inspect the model in the Model Lab
  - watch the live fleet and export reports

How the model works, with equations and sources: [`docs/MODEL.md`](docs/MODEL.md).

## Architecture

```
frontend/  React 19 + Vite + Leaflet + Tailwind     (driver and admin portals)
backend/   Flask REST API + SQLAlchemy (SQLite)
  app/ml/physics.py            road-load fuel/CO₂ model
  app/services/routing.py      OSRM routes + per-segment speed + turns + terrain
  app/services/rounds.py       exact multi-stop order optimiser (Held-Karp)
  app/services/calibration.py  per-vehicle learning loop
  app/services/decision_policy.py  when to recommend a greener route
```

## Run it

Follow [SETUP_EXPO.md](SETUP_EXPO.md) for Windows and macOS/Linux setup, personal administrator creation, real email OTP configuration, and a phone GPS walkthrough.

This version has no demo login or sandbox UI. The optional CSV contains 25 fictional vehicle profiles, clearly marked as samples; it is not a live fleet feed. Real GPS is recorded only when a driver starts a trip or round and grants location access. Fuel and CO₂ route figures are predictions, not measured telemetry.

Run backend tests from `backend`: `python -m pytest -q`. Frontend: `npm ci`, `npm run build`, `npm run lint`.
