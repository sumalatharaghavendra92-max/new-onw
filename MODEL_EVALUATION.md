# Public data and honest model evaluation

> **Update, 23 Oct 2026:** the synthetic Random Forest has been replaced by a physics road-load model with live weather, terrain and per-vehicle calibration. See `docs/MODEL.md`. Sections below that describe the synthetic model or display-only weather are historical.

The route model currently learns from synthetic data. Its random train/test score measures imitation of the generator, not fuel accuracy on roads. Live weather or a routing API improves input context but cannot itself validate predicted fuel or prove that an alternative route saves fuel.

## Executable public benchmark

`backend/scripts/evaluate_public_data.py` downloads the official [FuelEconomy.gov vehicle dataset](https://www.fueleconomy.gov/feg/ws/index.shtml), records source URL, retrieval time and SHA-256, then evaluates an experimental vehicle-efficiency regressor. The raw CSV stays local in `backend/public_data/vehicles.csv` and is ignored by Git. The source manifest and results are `source.json` and `evaluation.json` in the same directory.

From the repository root in PowerShell:

```powershell
.venv\Scripts\python.exe backend/scripts/evaluate_public_data.py --download
# Repeat the same snapshot without network:
.venv\Scripts\python.exe backend/scripts/evaluate_public_data.py
# Protocol checks:
Push-Location backend
..\.venv\Scripts\python.exe -m pytest tests/test_public_benchmark.py -q
Pop-Location
```

The download is a changing upstream snapshot; use the stored SHA and local CSV when reproducing a result. The default split trains on model years 2000–2022 and tests on 2023–2024. Newer records are deliberately outside this fixed benchmark. Only single-fuel gasoline/diesel rows with valid combined MPG are used. Electric MPGe and dual-fuel records are excluded. Combined MPG is converted to liters per 100 km with 235.214583 / MPG.

Features are year, displacement, cylinders, drive, transmission, vehicle class, primary fuel and technology type. Fuel economy, emissions, fuel cost and other target-derived columns are forbidden as predictors. Preprocessing is fitted on training records only. A fixed-seed random forest is compared with the training median baseline. Output includes MAE, RMSE, signed bias, R² and fuel-type slices; no fabricated “accuracy percentage.” Four protocol tests cover the temporal split, IDs, conversions, exclusions, invalid schema and signed errors.

**This benchmark predicts published US vehicle test ratings. It does not evaluate or replace the deployed trip model.** Model families can recur across years; the report counts overlapping families. It is not a holdout of unseen manufacturers or model families. Test-cycle ratings are not observed Indian freight-trip fuel use. No calibrated uncertainty or multiple-seed confidence interval is claimed. The experimental estimator is not saved into application model paths, and `deployment_eligible` is false.

## Route-level validation still required

The [original Vehicle Energy Dataset](https://github.com/gsoh/VED) is a stronger next source for trip telemetry: OBD-II measurements, timestamps, positions and speed from US personal vehicles. Its Apache-2.0 licensed repository distributes large compressed dynamic archives and static vehicle metadata. It is historical data, not a live feed; its population cannot establish Indian diesel freight accuracy.

Before promoting a route estimator, implement a separately versioned VED adapter that joins vehicle metadata, filters fuel types and missing signals, integrates rates over valid timestamp intervals, rejects large gaps and duplicate times, and splits whole vehicles/trips before fitting. Do not randomly divide telemetry rows: adjacent samples from one trip leak across the split. Features used for pre-trip recommendations must be available before departure; recorded future speed and fuel signals cannot masquerade as planning inputs.

Then collect local fleet journeys with consent and independently recorded fuel/energy. Freeze a chronological test set by vehicle, track MAE and bias by fuel, load, distance and weather, compare against distance-based and vehicle-efficiency baselines, and monitor missingness and drift. Driver-entered fuel is useful operational feedback but remains unverified. Repeated independent test evaluation requires a new untouched holdout. Comparative eco-route savings require a controlled or otherwise causally defensible experiment; a prediction on an untraveled route is not measured savings.

The project's defensible contribution is the workflow that keeps source timestamps, data quality, model scope, route decisions and later feedback traceable. Academic novelty and real-world fuel savings remain hypotheses to test.
