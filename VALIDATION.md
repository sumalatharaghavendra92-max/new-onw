# Validation of this delivered version

Executed using Python 3.12.14 and Node 24.19.0.

- Backend: `python -m pytest -q` — **121 passed** in 22.82 seconds.
- Frontend: `npm ci` and `npm run build` — passed. Vite reports the existing bundle-size advisory (main bundle about 567 kB before gzip).
- Frontend: `npm run lint` — passed with warnings about Fast Refresh exports and an existing driver-approval effect dependency; no lint errors.
- Chromium: actual browser forms passed for password + emailed-code sign-in, admin dashboard, 25 sample vehicles, manual fuel/load/odometer update, absence of sandbox navigation, and personal driver registration. No JavaScript page errors were observed. This used a temporary database and mocked email transport in a harness outside the delivered project.
- SMTP tests assert verified TLS, recipient, email content and authenticated send calls. Resend tests assert the provider URL, payload and response-status checking. Provider failures, code expiry, attempt exhaustion, resend cooldown, purpose separation, replay, and approval gating are covered.
- Tests verify repeatable 25-vehicle import, sample source labels, empty actual live fleet without trips, validated manual readings and authorization. Database backup begins with the SQLite file signature.

Warnings from existing dependencies include Requests' optional chardet compatibility warning and ReportLab/OpenPyXL deprecations. They did not fail the tests. No TLS or checksum verification was disabled.

Not verified: delivery into your real inbox (you must configure your own provider), SMS (not implemented), GPS on your phone, externally hosted HTTPS access, or availability/accuracy of public route/weather services. Public API boundaries are mocked in automated workflow tests. The project contains no real fleet source and no invented live vehicle readings.

The included fleet-updated.png is a screenshot of isolated browser-test data, not evidence of a deployed fleet.


## Delivery animation validation

- Frontend build passed; lint passed with existing warnings.
- `node tests/sampleFleetMotion.test.mjs` from frontend executed **4 tests, all passed**: inventory isolation, movement of all 25 vehicles, value bounds, unload/return/reload cycles and deterministic pause state.
- Chromium verified 25 map markers move, pause freezes markers and table values, 10× resumes playback, and selecting a plate draws its loop. No non-GET fleet API requests or JavaScript page errors were observed.
- No backend code, database schema, credentials or dependencies changed. Existing 121 backend results above apply to the unchanged backend.
- The screenshot fleet-simulation.png shows synthetic test data only.
