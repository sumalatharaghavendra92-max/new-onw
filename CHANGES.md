# Delivered changes

- Real SMTP TLS / Resend email-code delivery; failures return 503 without pretending success.
- Password plus emailed code at login; no token before successful verification.
- Database-backed hashed codes separated for registration and login, expiry, failed-attempt cap, resend cooldown and endpoint rate limiting.
- Local interactive personal-admin creation and Gmail configuration; no predefined accounts or displayed OTPs.
- Removed demo startup/seed scripts and sandbox frontend pages, route, navigation and live-map overlay; simulation API is no longer registered.
- Idempotent optional import of 25 fictional fleet profiles; clearly labelled sample readings, with manual update form and validated audited API.
- Persistent settings, real SQLite backup download, honest unsupported automatic restore.
- Same-origin development API proxy for local use and optional HTTPS phone testing.
- SETUP_EXPO.md gives full setup, personal-account, email delivery and actual-device GPS steps. README and WORKFLOW_SETUP now point to it.
- Added backend tests and exercised the browser flow with a mocked email boundary outside the delivered app.

Original research/audit documents remain as background material. Their historical demo commands are superseded by SETUP_EXPO.md. No claim is made that sample inventory is live telemetry or that public route predictions are measured performance.


## Delivery animation update

Added a browser-only simulation for the 25 existing SAMPLE vehicles on Live fleet, with an overview shortcut, moving map markers, delivery/load/fuel state, pause, resume, replay speed and per-vehicle loops. Real GPS remains in a separate section. No backend data or dependencies change. See SETUP_EXPO.md for updating only frontend/src while keeping your account and email settings.
