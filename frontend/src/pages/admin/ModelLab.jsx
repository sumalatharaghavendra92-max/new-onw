import { useState } from 'react';
import { FlaskConical } from 'lucide-react';
import api from '../../api/api';
import MapView from '../../components/MapView';
import { usePolling, PageHeader, ErrorNotice, Loading, Empty, errorMessage, amount } from '../../components/Operations';
import { BreakdownBar, BreakdownLegend, CalibrationTable, breakdownTotal, fuelText } from '../../components/ModelViews';

const VEHICLE_TYPES = [
  { value: 'car', label: 'Car' },
  { value: 'van', label: 'Van / light truck' },
  { value: 'truck', label: 'Medium truck' },
  { value: 'heavy truck', label: 'Heavy truck' },
];
const FUEL_TYPES = ['diesel', 'petrol', 'cng', 'electric'];

export default function ModelLab() {
  return (
    <div className="op-page">
      <PageHeader
        eyebrow="Admin · model lab"
        title="Model lab"
        description="Try any vehicle on real roads. See how much CO₂ each road makes, and why. Nothing is saved."
      />
      <RouteExperiment />
      <ModelCard />
    </div>
  );
}

function RouteExperiment() {
  const [form, setForm] = useState({
    source: 'Bengaluru',
    destination: 'Hosur',
    vehicle_type: 'truck',
    fuel_type: 'diesel',
    load_kg: 3000,
    capacity_kg: 6000,
  });
  const [result, setResult] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const update = (field) => (event) => setForm((current) => ({ ...current, [field]: event.target.value }));

  async function run(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const { data } = await api.post('/ai/model-lab', {
        ...form,
        load_kg: Number(form.load_kg),
        capacity_kg: Number(form.capacity_kg),
      });
      setResult(data);
      const recommended = data.routes.find((route) => route.isRecommended) || data.routes[0];
      setSelectedId(recommended?.id ?? null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  // MapView colours routes by their type: green for the recommendation, blue for fastest.
  const mapRoutes = (result?.routes || []).map((route) => ({
    ...route,
    type: route.isRecommended ? 'eco' : route.isFastest ? 'fast' : 'alternative',
  }));
  const scaleMax = Math.max(0, ...(result?.routes || []).map((route) => breakdownTotal(route.breakdown)));

  return (
    <>
      <ErrorNotice>{error}</ErrorNotice>
      <div className="op-planner">
        <div className="op-stack">
          <section className="op-panel">
            <form className="op-form" onSubmit={run}>
              <label>Origin<input className="op-input" value={form.source} onChange={update('source')} required /></label>
              <label>Destination<input className="op-input" value={form.destination} onChange={update('destination')} required /></label>
              <label>
                Vehicle type
                <select className="op-input" value={form.vehicle_type} onChange={update('vehicle_type')}>
                  {VEHICLE_TYPES.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}
                </select>
              </label>
              <label>
                Fuel
                <select className="op-input" value={form.fuel_type} onChange={update('fuel_type')}>
                  {FUEL_TYPES.map((fuel) => <option key={fuel} value={fuel}>{fuel === 'cng' ? 'CNG' : fuel[0].toUpperCase() + fuel.slice(1)}</option>)}
                </select>
              </label>
              <label>Load · kg<input className="op-input" type="number" min="0" step="1" value={form.load_kg} onChange={update('load_kg')} required /></label>
              <label>Capacity · kg<input className="op-input" type="number" min="0" step="1" value={form.capacity_kg} onChange={update('capacity_kg')} required /></label>
              <p className="op-note">Type a city (Bengaluru, Hosur, Mysuru…) or a latitude,longitude.</p>
              <button className="op-button" disabled={busy}>
                <FlaskConical size={15} /> {busy ? 'Fetching roads, terrain and weather…' : 'Run the model'}
              </button>
            </form>
          </section>
          {result && <ExperimentContext result={result} />}
        </div>
        <div className="op-map">
          <MapView routes={mapRoutes} selectedRouteId={selectedId} origin={form.source} destination={form.destination} />
        </div>
      </div>

      {result && (
        <section className="op-panel">
          <div className="op-panel-heading">
            <div>
              <h2>Where the CO₂ comes from</h2>
              <p>{result.decision?.reason}</p>
            </div>
          </div>
          <BreakdownLegend />
          {result.routes.map((route) => (
            <ExperimentRoute
              key={route.id}
              route={route}
              scaleMax={scaleMax}
              selected={route.id === selectedId}
              onSelect={() => setSelectedId(route.id)}
            />
          ))}
        </section>
      )}
    </>
  );
}

function ExperimentContext({ result }) {
  const weather = result.weather || {};
  return (
    <section className="op-panel">
      <h2>Inputs the model used</h2>
      <p className="op-description">
        {result.vehicle?.label} · {result.vehicle?.fuel} · total mass {amount(result.vehicle?.mass_kg)} kg
      </p>
      <p className="op-description">
        Weather: {weather.status || 'unknown'}
        {weather.temp_c != null && ` · ${amount(weather.temp_c)} °C`}
        {weather.wet_road ? ' · wet road' : ''}
      </p>
      <p className="op-description">Terrain elevation: {result.elevation_status}</p>
    </section>
  );
}

function ExperimentRoute({ route, scaleMax, selected, onSelect }) {
  return (
    <button
      type="button"
      className={`op-route-card ${selected ? 'selected' : ''}`}
      style={{ marginTop: 14 }}
      onClick={onSelect}
      aria-pressed={selected}
    >
      <div className="op-row">
        <strong>{route.title}</strong>
        {route.isRecommended && <span className="op-badge">Recommended</span>}
        {route.isFastest && <span className="op-badge warn">Fastest</span>}
      </div>
      <div className="op-route-values">
        <div><b>{amount(route.co2Kg)}</b><span>kg CO₂</span></div>
        <div><b>{amount(route.durationMin)}</b><span>minutes</span></div>
        <div><b>{amount(route.distanceKm)}</b><span>kilometres</span></div>
      </div>
      <BreakdownBar breakdown={route.breakdown} scaleMax={scaleMax} />
      <p className="op-note">
        Fuel {fuelText(route.fuelLiters, route.fuelUnit)} · climb {amount(route.climbM)} m · avg {amount(route.avgSpeedKmh)} km/h
        {' · '}{route.turns ?? '—'} turns · eco score {amount(route.ecoScore)} (50 = class reference)
      </p>
    </button>
  );
}

function ModelCard() {
  const { data, error, loading } = usePolling('/ai/model-card', 300000);
  if (loading) return <Loading />;
  if (error) return <ErrorNotice>{error}</ErrorNotice>;
  if (!data) return null;

  return (
    <>
      <section className="op-panel">
        <div className="op-panel-heading">
          <div>
            <h2>The model</h2>
            <p>{data.model_version}</p>
          </div>
        </div>
        <p className="op-description">
          In simple words: a vehicle burns fuel to fight four things. Its tyres on the road, the wind, the hills,
          and speeding up again after every turn. Heavier and faster means more fuel. We add AC on hot days,
          then turn fuel into CO₂.
        </p>
        <div className="op-equation">{data.equation}</div>
        <ul className="op-note" style={{ paddingLeft: 18, marginTop: 14 }}>
          {(data.assumptions || []).map((item) => <li key={item}>{item}</li>)}
        </ul>
      </section>

      <div className="op-columns">
        <section className="op-panel">
          <h2>Vehicle profiles</h2>
          <ProfilesTable profiles={data.profiles} />
        </section>
        <section className="op-panel">
          <h2>Fuel emission factors</h2>
          <FuelsTable fuels={data.fuels} />
        </section>
      </div>

      <section className="op-panel">
        <h2>Tested on real car trips</h2>
        <RealTripTest validation={data.ved_validation} />
      </section>

      <div className="op-columns">
        <section className="op-panel">
          <h2>Validated on real EPA data (vehicle efficiency)</h2>
          <BenchmarkSummary benchmark={data.public_benchmark} />
        </section>
        <section className="op-panel">
          <h2>Data sources</h2>
          <ul className="op-note" style={{ paddingLeft: 18, marginTop: 10 }}>
            {(data.data_sources || []).map((source) => (
              <li key={source.name}>
                <a href={source.url} target="_blank" rel="noreferrer" className="op-small-link">{source.name}</a> · {source.use}
              </li>
            ))}
          </ul>
        </section>
      </div>

      <section className="op-panel">
        <div className="op-panel-heading">
          <h2>Per-vehicle calibration</h2>
          <p>Learned from driver-reported fuel</p>
        </div>
        <CalibrationTable rows={data.calibration} />
      </section>
    </>
  );
}

function ProfilesTable({ profiles = {} }) {
  return (
    <div className="op-table-wrap">
      <table className="op-table">
        <thead>
          <tr><th>Class</th><th>Curb kg</th><th>CdA m²</th><th>Crr</th><th>Aux kW</th><th>AC kW</th></tr>
        </thead>
        <tbody>
          {Object.entries(profiles).map(([key, profile]) => (
            <tr key={key}>
              <td>{profile.label}</td>
              <td>{amount(profile.curb_kg)}</td>
              <td>{profile.cda_m2}</td>
              <td>{profile.crr}</td>
              <td>{profile.aux_kw}</td>
              <td>{profile.ac_kw}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FuelsTable({ fuels = {} }) {
  return (
    <div className="op-table-wrap">
      <table className="op-table">
        <thead>
          <tr><th>Fuel</th><th>kg CO₂ / unit</th><th>MJ / unit</th><th>Source</th></tr>
        </thead>
        <tbody>
          {Object.entries(fuels).map(([key, fuel]) => (
            <tr key={key}>
              <td>{key} ({fuel.unit})</td>
              <td>{fuel.co2_kg_per_unit}</td>
              <td>{amount(fuel.mj_per_unit)}</td>
              <td>{fuel.source}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const BEST_ROW = { background: 'var(--gg-sign-tint)', fontWeight: 600 };

// Real-trip check on the Vehicle Energy Dataset: cars the model never saw.
function RealTripTest({ validation }) {
  if (!validation) {
    return <Empty title="Not run yet">Run backend/scripts/validate_ved.py to test the model on real trips.</Empty>;
  }
  const rows = [...validation.rows, ...validation.post_trip];
  const best = Math.min(...rows.map((row) => row.mae_pct));
  return (
    <>
      <p className="op-description">
        {amount(validation.holdout_trips)} real trips by {validation.holdout_vehicles} cars the model never saw
        (Vehicle Energy Dataset, USA). Lower error is better.
      </p>
      <div className="op-table-wrap">
      <table className="op-table">
        <thead>
          <tr>
            <th>Method</th>
            <th>Average error</th>
            <th>Bias</th>
            <th>R²</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key} style={row.mae_pct === best ? BEST_ROW : undefined}>
              <td>{row.name}</td>
              <td className="op-num">{row.mae_pct.toFixed(1)}%</td>
              <td className="op-num">{row.bias_pct == null ? '—' : `${row.bias_pct > 0 ? '+' : ''}${row.bias_pct.toFixed(0)}%`}</td>
              <td className="op-num">{row.r2 == null ? '—' : row.r2.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
      <p className="op-note">
        What this means: before a trip, the model does not know the stop-and-go driving, so on its own it
        guesses too little fuel. Learning per vehicle fixes the bias. With the real speed trace the physics is good.
        These are US petrol cars, not Indian trucks.
      </p>
    </>
  );
}

function BenchmarkSummary({ benchmark }) {
  if (!benchmark) {
    return <Empty title="No benchmark file">Run backend/scripts/evaluate_public_data.py to produce the EPA evaluation.</Empty>;
  }
  const model = benchmark.random_forest || {};
  const baseline = benchmark.train_median_baseline || {};
  const years = (benchmark.test_years || []).join('–');
  return (
    <>
      <div className="op-route-values">
        <div><b>{amount(model.mae_l_per_100km)}</b><span>model MAE · L/100 km</span></div>
        <div><b>{amount(baseline.mae_l_per_100km)}</b><span>baseline MAE · L/100 km</span></div>
        <div><b>{model.r2 == null ? '—' : model.r2.toFixed(2)}</b><span>R² on held-out years</span></div>
      </div>
      <p className="op-note">
        Random forest trained on {amount(benchmark.train_rows)} vehicles, tested on {amount(benchmark.test_rows)} vehicles from model years {years}.
        This checks fuel ratings of vehicles, not single trips.
      </p>
    </>
  );
}
