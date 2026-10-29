> Historical reference from the original upload. For this updated build, use [SETUP_EXPO.md](SETUP_EXPO.md); old demo startup instructions no longer apply.

# Live context: what is real and what remains unvalidated

> **Update, 23 Oct 2026:** the synthetic Random Forest has been replaced by a physics road-load model with live weather, terrain and per-vehicle calibration. See `docs/MODEL.md`. Sections below that describe the synthetic model or display-only weather are historical.

The authenticated `/api/v1/context/weather?latitude=12.97&longitude=77.59` endpoint fetches current weather-model output from [Open-Meteo](https://open-meteo.com/en/docs). This is public external data, not generated demo weather. It is **model-derived current weather, not an on-site sensor observation**. The provider timestamp (`valid_at`) and our retrieval timestamp (`fetched_at`) are separate. India may use interpolation of hourly model data; a short frontend refresh does not create higher-resolution observations.

The response includes temperature in Celsius, precipitation in millimetres, wind speed in km/h and WMO weather code. Coordinates are validated and rounded to three decimals for cache keys. Data is cached ten minutes in a bounded 256-entry process-local cache. If the provider fails, cached data up to one hour old is explicitly marked stale; beyond this, the API returns 503 with no invented values. Provider timestamps older than 30 minutes or more than 15 minutes into the future also trigger a stale label. Requests have connection/read timeouts and an authenticated rate limit.

This endpoint does **not** add live traffic. OSRM routes still lack traffic and certified truck-restriction coverage. It also does **not** feed weather into the existing synthetic fuel model: that model has no established weather calibration from measured fuel data. Displaying fresh context is useful for a demonstration, but does not improve or establish model accuracy by itself.

For a non-commercial student demonstration, the public endpoint needs no API key. [Open-Meteo pricing](https://open-meteo.com/en/pricing) describes the free tier's non-commercial restriction, request limits and absence of an uptime guarantee. Retain the response attribution in the UI. Commercial deployment needs an appropriate plan or self-hosted provider; distributed deployment also needs shared cache/rate-limit storage instead of these per-process facilities.

## Integration and verification

Register `context_bp` from `app.blueprints.context.routes` at `/api/v1/context`. Poll at no faster than the returned `refresh_interval_seconds`. Render available/stale/unavailable separately, with the valid time and source. A 503 is an expected provider-outage state, not permission to show synthetic numbers.

Tests in `backend/tests/test_live_context.py` cover invalid coordinates, authentication, cache reuse, preserved provenance, stale fallback, expiration and malformed responses. They mock provider HTTP so normal test runs do not consume public API quotas. A real external request must be checked separately to verify connectivity; unit tests alone cannot establish provider availability.

An actual public API request was verified on 23 October 2026 at 15:04:31 UTC for Bengaluru (12.970, 77.590). Open-Meteo returned a valid time of 15:00 UTC, 21.8°C, 0.1 mm precipitation and 5.9 km/h wind. This is a connectivity/provenance check at that instant, not a continuing availability or weather-accuracy guarantee. The restricted sandbox request was unavailable; the approved external-network request succeeded. Ten focused endpoint/service tests passed.

To train a weather-aware predictor, collect measured trip fuel with vehicle identity, timestamps, location and aligned historical weather; split evaluation by vehicle and time before fitting. Preserve a baseline model and report held-out MAE/bias by operating domain. No live weather query should be described as measured fuel ground truth or as verified emission savings.
