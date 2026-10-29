> Historical reference from the original upload. For this updated build, use [SETUP_EXPO.md](SETUP_EXPO.md); old demo startup instructions no longer apply.

# Eco-routing research and workflow improvement review

> **Update, 23 Oct 2026:** the synthetic Random Forest has been replaced by a physics road-load model with live weather, terrain and per-vehicle calibration. See `docs/MODEL.md`. Sections below that describe the synthetic model or display-only weather are historical.

Reviewed 23 October 2026. This is a focused engineering literature/product review, not an exhaustive systematic review or a benchmark proving superiority over commercial systems. Primary product documentation, research abstracts, and dataset documentation were inspected. Where full papers were not reviewed, conclusions below stay at the level supported by their abstracts. Local findings refer to the working source code.

## Main conclusion

GoGreen's strongest opportunity is a transparent, auditable trip decision and measurement workflow. Adding a more complicated regressor alone will not make its recommendations credible. Current commercial providers already incorporate information our system lacks. We should integrate suitable provider capabilities, document missing evidence, and evaluate our own contribution honestly.

## Comparison with existing approaches

| Approach | Evidence and capabilities | Boundary and consequence for GoGreen |
|---|---|---|
| Google Routes eco-routing | Uses engine type, traffic and road conditions; supports fuel estimates and compares an efficient route with a default route | Documented constraints include supported regions, traffic-aware routing and no intermediate waypoint. It is not evidence that our own model is equally capable. Current documentation includes India; do not assume lack of Indian support. |
| TomTom routing | Supports current/typical traffic, vehicle properties and configurable consumption models | Consumption parameters must be supplied appropriately; returned estimates are not measured ground truth. Road restriction coverage is not universally complete. |
| Uncertainty-aware neural ensembles | Khiari and Olaverri-Monreal evaluate VED energy predictions and uncertainty measures against baselines | Uncertainty estimation is already researched; claiming it as novel would be wrong. We need calibrated intervals on held-out data before presenting confidence. |
| Mixed-fleet route energy prediction | Ayman et al. integrate CARTA bus telemetry, traffic, weather and map/elevation information | This demonstrates the importance of data integration. Results from a particular bus fleet do not establish transfer to our vans or Indian conditions. |
| VED-based experiments | Public OBD-II driving records from 383 personal vehicles in Ann Arbor | Useful for a reproducible experiment, but not a representative Indian commercial fleet. Vehicle fuel signals, missingness and usable targets must be checked. |
| Network-level routing research | Simulation work studies the emissions consequences of routing strategies across urban traffic | Individual route efficiency and network-wide efficiency are different objectives. Our single-trip selector cannot claim to optimize a city's emissions. |

Sources:

- [Google eco-friendly routes](https://developers.google.com/maps/documentation/routes/eco-routes)
- [TomTom Calculate Route](https://docs.tomtom.com/routing-api/documentation/tomtom-maps/v1/calculate-route)
- [Uncertainty-aware vehicle energy prediction, 2023](https://arxiv.org/abs/2304.07073)
- [Mixed-vehicle transit fleet energy prediction, 2020](https://arxiv.org/abs/2004.06043)
- [VED dataset and provenance](https://github.com/gsoh/VED)
- [How Routing Strategies Impact Urban Emissions, 2022](https://arxiv.org/abs/2207.01456)
- [Eco-routing taxonomy/review author publication record](https://research.monash.edu/en/publications/eco-friendly-route-planning-algorithms-taxonomies-literature-revi/)

These are documented capability boundaries and evaluation gaps, not claims of exploitable security vulnerabilities in third-party products.

## Loopholes found in our current system

### 1. Positive-only savings hide regressions — fixed in this iteration

Previously every difference was clipped at zero. If one journey saved 5 kg and another emitted 8 kg more than its baseline, the dashboard would report 5 kg avoided instead of a net increase of 3 kg. Trip serialization, dashboard aggregation and exports now retain signed differences. Labels say net estimated avoided emissions; a negative number means additional predicted emissions. Historical comparisons still use their original saved assumptions.

### 2. Tiny differences receive unjustified certainty — partially addressed

Selecting a slower route for a 0.01 kg predicted improvement is not defensible without error estimates. The new versioned decision policy retains the fastest candidate unless estimated improvement is at least both 2% of baseline and 0.1 kg. It still enforces the 15% travel-time allowance. This is a configurable-in-code product heuristic, not a statistically calibrated confidence bound. The policy explanation is persisted with new route candidates. Invalid/nonfinite predictions are rejected.

Next: calibrate predictive intervals on an independent validation set, measure interval coverage and width, and abstain when alternatives cannot be distinguished reliably. Do not interpret tree disagreement alone as calibrated uncertainty.

### 3. Old plans can start with obsolete estimates — fixed with a conservative expiry

Newly starting a plan older than 30 minutes is rejected with instructions to cancel/replan. Existing active trips may still resume. This prevents indefinite reuse, but does not create live traffic awareness or guarantee current road conditions. The 30-minute threshold is an initial policy choice, not a research-derived constant.

### 4. Feature availability mismatch — remains

The existing fuel model takes distance, load, categorical traffic/weather, and vehicle type. The live planner supplies fixed medium/clear categories. It does not ingest the actual speed profile, grades, stops, or departure-time traffic. For the same vehicle/load, route differences are largely distance-driven. The route geometry is real, but the environmental inputs are assumptions.

Training on actual future average speed, idle time or acceleration and then substituting guessed values at planning time can produce deceptively good offline accuracy. Maintain separate pre-trip prediction and post-trip analysis feature contracts. Evaluate with the same input availability as deployment.

### 5. Fuel/vehicle taxonomy and operating domain — remains

Vehicle type text controls the current mapping, while fuel_type is not a properly modeled feature. Unknown vehicle types can silently become vans. EV tailpipe CO2, grid emissions and battery energy are different quantities; diesel/petrol/CNG factors cannot be interchanged. Random Forest training ranges also do not establish safe behavior outside those ranges.

Next: explicit supported vehicle/fuel profiles, model domain metadata, bounds checks and a clear unavailable result for unsupported profiles. Keep liters and kWh separate. Do not use a passenger-car dataset to certify truck predictions.

### 6. Candidate-route limitation — remains

The selector ranks the alternatives returned by OSRM. It does not search every road path for minimum emissions. A globally better route may never enter the candidate set. Describe the result as the recommended returned alternative, not the globally optimal route. Compare against fastest, shortest returned candidate, and simple consumption baselines.

### 7. Measured outcome versus counterfactual — remains

A fuel receipt or sensor reading for the selected route does not reveal what the same vehicle would have consumed on an untraveled alternative. Signed predicted savings improve honesty but are still predictions. Record prediction error on observed trips separately from estimated avoided emissions. Validate savings with matched repeated journeys or a carefully designed controlled study, accounting for traffic, cargo, driver and weather differences.

### 8. Telemetry trust and arrival — remains

GPS currently validates numeric coordinates but lacks device timestamp/accuracy storage, replay detection and impossible-jump checks. Completion is driver-confirmed, not verified arrival. Phone GPS alone is noisy and not tamper-proof. Add sequence IDs, received/device times, accuracy, duplicate rejection and plausibility checks. Flag questionable data for review rather than silently treating it as a trustworthy fuel-training label. Deviation detection needs route geometry distance, multiple consecutive samples and cooldowns.

### 9. Cross-workflow consistency and scale — remains

Trip start validates assignment and capacity, but administrators can still change vehicle properties during active trips. Introduce active-trip guards on assignment/deletion, transactional lifecycle updates and immutable input snapshots. Paginate history beyond the current latest-100 limit. Avoid full geometry transfer on every dashboard poll, bound GPS retention, and index latest positions. Production also needs authentication hardening and persistent rate-limit storage.

## Improved target workflow

1. Validate account, vehicle/fuel profile, capacity, routing restrictions and supported model domain.
2. Request candidate routes with provider timestamps, routing profile and feature provenance.
3. Construct only features available at departure time; mark assumptions and missing inputs.
4. Predict energy and uncertainty with a versioned model; reject invalid outputs.
5. Apply feasibility constraints before ranking; retain fastest when improvement lacks sufficient evidence.
6. Save immutable route geometry, features, baseline, chosen route, policy and model identifiers.
7. Recheck freshness and assignment before reserving driver/vehicle and starting once.
8. Collect quality-checked telemetry; show freshness, deviations and connectivity without fabricated positions.
9. Complete once, recording measured energy separately from predictions and missing values separately from zero.
10. Reconcile reports using signed comparisons; publish coverage and measured prediction error.
11. Review data quality before training; compare a challenger with the deployed baseline on untouched data.
12. Promote only after explicit evaluation, with rollback and model-version traceability. Do not automatically retrain on every unverified trip.

## Evaluation plan and measurable acceptance criteria

- Dataset audit: document license, provenance, vehicle classes, time range, missingness and units; identify actual energy/fuel targets.
- Grouped evaluation: hold out vehicles/journeys and a later time period. Keep nearby telemetry rows from the same trip out of both train and test partitions.
- Baselines: distance times vehicle-average consumption, then linear regression, then Random Forest. Complexity must earn a measurable improvement.
- Metrics: fuel/energy MAE and RMSE; per-vehicle errors; interval coverage; recommendation stability; latency and provider failure rate. Avoid percentage error around zero emissions.
- Routing experiment: fixed origin/destination/vehicle/load/departure scenarios with persisted provider responses, so competing methods receive the same candidates.
- Ablation: compare distance-only with load, traffic, grade and weather additions; only claim benefit from features actually available.
- Failure tests: invalid model outputs, no alternative, equal estimates, negative net savings, stale plan, repeated completion, concurrent reservation, unauthorized access, provider outage and bad GPS.
- Deployment gate: one end-to-end driver/admin browser journey, real-device GPS check, report reconciliation, supported-domain documentation and reproducible model evaluation.

## Implemented now versus proposed

Implemented in this iteration: signed emissions accounting, conservative versioned recommendation decisions, prediction-value validation, a 30-minute start freshness gate, clearer frontend labels and regression tests. No new dataset was downloaded or trained. No calibrated uncertainty, live traffic, multi-vehicle optimizer or production certification is claimed.

The strongest defensible project contribution is an auditable decision-and-feedback workflow with measured evaluation. Its novelty must be established against a fuller literature review, not assumed from combining a map API and Random Forest.
