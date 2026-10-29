# GoGreen — setup for your expo

Your uploaded application is a React website with a Python Flask backend. “Expo” here means your project exhibition; this is not an Expo React Native app.

## What changed

- No demo account shortcuts or predefined accounts; create your own administrator locally.
- Admin dashboard, driver approvals, reports, routing, and real phone GPS tracking remain.
- Both sign-in and driver registration send real email verification codes. Sign-in requires the password and email code before issuing tokens. Codes expire after 10 minutes, allow five wrong attempts, and are not shown in the browser or logs. Requests have a 60-second resend cooldown and IP rate limits. Hashed codes persist in the database.
- A provider failure returns an error; it never pretends a message was sent.
- Sandbox UI, simulation API registration, and demo startup scripts are removed.
- 25 optional sample vehicles with varied fuel/battery percentages, fuel types, capacities, current loads, odometers and statuses. They have SAMPLE plates and no invented live locations. Electric percentages mean battery charge. Their emission factors are illustrative values; do not present them as manufacturer specifications.
- Admins can record timestamped manual vehicle readings. Manual entries are not sensor measurements and do not automatically train the fuel model.
- Settings persist; SQLite backup downloads an actual database file. Restore requires stopping the backend and replacing the database, not a fake success button. Strict-routing/review preferences do not implement automatic enforcement or training.

**You have no fleet feed:** 25 vehicles are fictional inventory for demonstration, not 25 real trucks. Live GPS requires real people/devices. Fuel level, load and fuel use require manual observations or a later sensor integration. Predictions must not be presented as measured savings.

## 1. Install prerequisites

Install **Python 3.12** and **Node.js 22.12+** (Node 24 LTS also works). Windows: enable “Add Python to PATH” in the installer. Unzip this project into a new folder, e.g. `Documents/GoGreen`, and open that folder in VS Code. Do not overlay an old copy with demo databases or credentials.

Open a VS Code terminal at the project root.

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
cd backend
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in this terminal, then activate again. This affects this terminal only. Alternatively use Command Prompt and `.venv\Scripts\activate.bat` from the project root.

macOS/Linux:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
cd backend
python -m pip install -r requirements.txt
```

Keep this terminal in `backend` with the environment activated.

## 2. Connect real email OTP (Gmail, easiest for tomorrow)

1. Use a Gmail account you own as the sender.
2. Open your Google Account → Security → enable **2-Step Verification**.
3. Open Google Account → search for **App passwords**, or visit `https://myaccount.google.com/apppasswords` while signed in.
4. Create an app password named GoGreen. This is separate from your normal Google password. Some school/work accounts and security policies do not allow app passwords; use another permitted account or the Resend alternative below.
5. In your backend terminal run:

```bash
python -m scripts.configure_email
```

6. Enter your sender Gmail address and that 16-character app password. The password is hidden while typing. This creates `backend/.env` with private email credentials and two random application secrets. Do not upload, screenshot, email, or commit `.env`.

No Google API key is needed. Gmail SMTP uses TLS on port 465. Google controls sending limits and delivery; check Spam if a code is delayed. OTPs can be sent to your own real email, including a different recipient email. Keep the backend online and connected to the internet.

Alternative: copy `backend/.env.example` to `backend/.env`, set two different random secrets, set `EMAIL_PROVIDER=resend`, `RESEND_API_KEY` to your private Resend API key, and `EMAIL_FROM` to your verified sender. Resend requires a verified domain to send freely to other users; its testing sender has recipient restrictions. Do not put provider secrets into frontend files.

**SMS is not configured.** The phone number is a contact field, not a verified phone identity. This version uses the email option. Real SMS needs a paid/approved delivery provider, sender setup and, where applicable, India DLT compliance. No SMS-delivery claim is made.

## 3. Create tables, your administrator, and the 25 vehicles

In the same backend terminal:

```bash
python -m flask --app run init-db
python -m flask --app run create-admin
python -m flask --app run import-sample-fleet
```

`create-admin` asks for **your email, name, phone, password and password confirmation**. Use an email you can open; sign-in codes go there. Password must be at least eight characters (up to 72 UTF-8 bytes). No default password exists. This command is local administration, not a public role-selection form.

The sample import is repeatable: importing again skips existing SAMPLE plates and preserves their edits. It creates no accounts, fake GPS, completed trips or fake savings. Skip the import if you want an empty fleet and add only your own vehicles in Admin → Vehicles.

Now start the backend:

```bash
python run.py
```

Leave that terminal open. The backend listens on port 5000 with debug off. Use this command, not an old `run_demo` instruction.

## 4. Start the website

Open a **second terminal**, at the project root:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173` in your laptop browser. Vite forwards `/api` requests to the backend, so no API URL environment variable is needed for local development. If you copied an old frontend `.env`, remove an old `VITE_API_BASE_URL` that points at demo port 5002, then restart Vite.

Sign in using the administrator email and password you just created → **Send sign-in code** → check your actual inbox → enter the six-digit code → **Verify and sign in**. The admin dashboard remains available. If delivery is unconfigured, you will get an explicit error instead of a displayed OTP.

Admin → Vehicles shows the 25 profiles. SAMPLE readings say “Sample · not live”. “Record reading” saves values you actually observed, with a manual label and timestamp. For real vehicles, add their real registration numbers and specifications instead of renaming sample data as actual observations.

## 5. Register your own driver account and get actual GPS

1. Open an incognito/private window or a second browser, so the admin session stays signed in.
2. Choose **Register for approval**, enter another email you own, request the code, and read it in that inbox.
3. Verify the code; enter your driver details, a different phone number, licence and password; submit within the code's 10-minute lifetime. If it expires, restart registration and request a fresh code.
4. In the admin window, open **Driver approvals** and approve your registration. Note the driver ID.
5. In **Vehicles**, edit one active vehicle and put that driver ID in **Driver ID**. Save. Prefer adding your real vehicle for real tracking; samples remain fictional.
6. In the driver window sign in with the new driver's password and emailed code.
7. Create a trip, select a road route, start the trip, and allow location access. Keep that driver page open in the foreground. Check Admin → Live fleet in the admin window; it refreshes every 15 seconds.
8. The location comes from that device. A laptop can report coarse location. Waiting/stale GPS means no fresh fix was received; the app does not invent movement. Only a real drive produces a moving vehicle marker. Enter observed fuel used when finishing the trip; route estimates are predictions.

For your first expo rehearsal, do this on your laptop using `localhost`, which browsers allow for geolocation. Do not enter invented completed-trip fuel as measured performance.

### Tracking from a phone

A plain `http://192.168...` address normally cannot use browser GPS: it needs **HTTPS**. Do not disable browser security to work around this.

One option is ngrok (requires your own ngrok account and installed CLI):

1. Follow ngrok's official account setup and configure its token privately on your laptop.
2. With both application terminals running, open a third terminal and run `ngrok http 5173`.
3. Copy the HTTPS hostname it assigns, e.g. `your-name.ngrok-free.app`.
4. Stop the frontend only with Ctrl+C. In that frontend terminal set the actual assigned hostname and restart:

Windows PowerShell:

```powershell
$env:VITE_ALLOWED_HOSTS="your-name.ngrok-free.app"
npm run dev
```

macOS/Linux:

```bash
VITE_ALLOWED_HOSTS=your-name.ngrok-free.app npm run dev
```

5. Open your assigned **HTTPS** address on the phone, sign in as the approved driver, start a trip and grant location. The Vite proxy sends API calls through the same HTTPS address. The laptop must remain running. Keep credentials private and close the tunnel after the exhibition. This is temporary development access, not a production deployment. HTTPS through a tunnel requires an internet connection and provider access; it was not validated with your phone here.

## Troubleshooting

- **Code not received:** check Spam, sender account, app password, outbound SMTP ports, internet and provider limits. Wait 60 seconds before resending. A new code invalidates the old code for the same purpose. Use the newest message. Restart the backend after `.env` changes.
- **Email delivery failed:** no code was exposed as a fallback. Gmail: verify 2-Step Verification and the app password; use Resend HTTPS if your network blocks SMTP. Read the provider dashboard privately; do not share credentials in logs.
- **Five wrong codes:** wait until 60 seconds after the previous send and request a new one. Codes expire after 10 minutes.
- **Pending approval:** approve in the admin portal. Registration does not grant admin access.
- **Vehicle not in live map:** inventory is not GPS. Assign an approved driver and start a trip/round on a device granting GPS.
- **Route/weather unavailable:** internet access is required for `router.project-osrm.org` and `api.open-meteo.com`; map tiles use `tile.openstreetmap.org`. These public services can throttle or fail. No fake live road/weather values are substituted.
- **Port busy:** stop an old process you started on port 5000/5173; do not run the previous demo server at the same time.
- **Need another admin:** run `create-admin` again with a new unique email/phone. Never expose this as unrestricted public registration.

## Backups and restarting

Database records survive restarts in `backend/instance/gogreen.db`. Admin → Settings → Backup downloads a real SQLite backup containing private account information. Store it securely. To restore, stop the backend, retain a copy of the current database, replace `backend/instance/gogreen.db` with the trusted backup, then run `python -m flask --app run init-db` and restart. Restoring is intentionally not done by the old fake restore endpoint.

Tomorrow, reactivate `.venv`, go to `backend`, run `python run.py`; in another terminal go to `frontend`, run `npm run dev`. You do not recreate your account or import vehicles each time. Never share `.env`, database backups, or `.venv` in your project ZIP.

## Verification and production limits

Run from backend with the environment active: `python -m pytest -q`. Email tests mock the delivery boundary; they do not prove inbox delivery. From frontend: `npm run build` and `npm run lint`. See VALIDATION.md for the checks executed on this delivered version.

Before relying on this commercially, add deployment TLS/reverse proxy, production WSGI hosting, shared persistent rate limiting (current default is per-process memory), operational monitoring, verified fleet/sensor integrations, account recovery and full device/browser tests. Do not describe this exhibition build as production certified. The email provider and phone location permissions must be tested using your own accounts/devices before the expo.


## Show all 25 vehicles in action at the expo

Open **Admin → Live fleet**, then click **Run 25-vehicle simulation**. A shortcut is also on the admin overview. The same SAMPLE-001 through SAMPLE-025 inventory vehicles appear as animated markers with changing delivery status, speed, fuel/battery percentage, cargo load, odometer and drop counts. Use **Pause/Resume**, select **5× or 10×** playback, or click a plate to see its illustrative loop. Restart begins a new playback; leaving the page stops it. The animation works without a routing API; the background map tiles still need internet.

This is explicitly **SIMULATION**, not live GPS. The loops are schematic straight-line paths, not navigable road routes; values are synthetic presentation data. Sample maintenance vehicles participate as fictional actors. It writes no trips, GPS, inventory readings, fuel reports, savings or accounts. Actual driver GPS appears separately below the simulation; real reports remain unchanged.

### Updating an already installed copy without losing your account

1. Download the latest repository ZIP and extract it into a separate folder.
2. Stop the **frontend** terminal with Ctrl+C. Keep the backend running.
3. Copy the new `frontend/src` folder into your existing project's `frontend` folder. Choose **Replace files** when asked. Do not replace `backend`, `.env`, `.venv` or the database.
4. In your existing frontend terminal run `npm.cmd run dev` again.
5. Refresh the browser with Ctrl+F5, sign in if necessary, and open Admin → Live fleet.

No dependency or database changes are needed for this animation update. If you cloned using Git rather than downloading a ZIP, `git pull` updates the files while ignored local credentials/databases remain in place.
