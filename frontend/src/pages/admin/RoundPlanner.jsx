import { useCallback, useEffect, useMemo, useState } from 'react';
import { Route as RouteIcon, Send, Trash2 } from 'lucide-react';
import api from '../../api/api';
import MapView from '../../components/MapView';
import { PageHeader, ErrorNotice, Empty, errorMessage, amount } from '../../components/Operations';
import { fuelText } from '../../components/ModelViews';

// A realistic Bengaluru delivery round so the page can be demonstrated immediately.
const EXAMPLE_DEPOT = '13.0285,77.5197'; // Peenya Industrial Area warehouse
const EXAMPLE_STOPS = [
  { label: 'Malleshwaram', place: '13.0035,77.5710', drop_kg: 120 },
  { label: 'Indiranagar', place: '12.9784,77.6408', drop_kg: 80 },
  { label: 'Koramangala', place: '12.9352,77.6245', drop_kg: 450 },
  { label: 'Jayanagar', place: '12.9308,77.5838', drop_kg: 60 },
  { label: 'Rajajinagar', place: '12.9910,77.5520', drop_kg: 90 },
];

const PLAN_TITLES = {
  fastest: 'Fastest',
  greenest: 'Greenest',
  balanced: 'Balanced',
};

// "12.97,77.59" -> { lat, lng }; city names cannot be pinned on the map.
function parseLatLng(place) {
  const parts = String(place || '').split(',').map(Number);
  if (parts.length !== 2 || !parts.every(Number.isFinite)) return null;
  return { lat: parts[0], lng: parts[1] };
}

function formatPoint(lat, lng) {
  return `${lat.toFixed(5)},${lng.toFixed(5)}`;
}

export default function RoundPlanner() {
  const [vehicles, setVehicles] = useState([]);
  const [vehicleId, setVehicleId] = useState('');
  const [depot, setDepot] = useState(EXAMPLE_DEPOT);
  const [stops, setStops] = useState(EXAMPLE_STOPS);
  const [returnToDepot, setReturnToDepot] = useState(true);
  const [result, setResult] = useState(null);
  const [selectedPlanKey, setSelectedPlanKey] = useState('balanced');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [dispatch, setDispatch] = useState(null); // { ok, text } after "Send to driver"

  useEffect(() => {
    api.get('/vehicles')
      .then(({ data }) => {
        const active = data.filter((vehicle) => vehicle.status === 'active');
        setVehicles(active);
        // Start with the largest vehicle so the example round fits its capacity.
        const largest = [...active].sort((a, b) => (b.load_capacity_kg || 0) - (a.load_capacity_kg || 0))[0];
        if (largest) setVehicleId(String(largest.id));
      })
      .catch((err) => setError(errorMessage(err)));
  }, []);

  // First click places the depot, every later click adds a stop.
  const handleMapClick = useCallback((lat, lng) => {
    const place = formatPoint(lat, lng);
    setResult(null);
    if (!depot) {
      setDepot(place);
      return;
    }
    setStops((current) => [...current, { label: `Stop ${current.length + 1}`, place, drop_kg: 100 }]);
  }, [depot]);

  function updateStop(index, field, value) {
    setResult(null);
    setStops((current) => current.map((stop, i) => (i === index ? { ...stop, [field]: value } : stop)));
  }

  function removeStop(index) {
    setResult(null);
    setStops((current) => current.filter((_, i) => i !== index));
  }

  function resetRound() {
    setResult(null);
    setDepot('');
    setStops([]);
  }

  // The same inputs go to /plan and /dispatch, so the driver gets exactly the round shown here.
  function roundRequest() {
    return {
      vehicle_id: Number(vehicleId),
      depot,
      stops: stops.map((stop) => ({ label: stop.label, place: stop.place, drop_kg: Number(stop.drop_kg) })),
      return_to_depot: returnToDepot,
    };
  }

  async function optimise(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setDispatch(null);
    try {
      const { data } = await api.post('/rounds/plan', roundRequest());
      setResult(data);
      setSelectedPlanKey(data.plans.some((plan) => plan.key === 'balanced') ? 'balanced' : data.plans[0]?.key);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function sendToDriver() {
    setBusy(true);
    setDispatch(null);
    try {
      const { data } = await api.post('/rounds/dispatch', { ...roundRequest(), plan_key: selectedPlanKey });
      const round = data.round || data;
      setDispatch({ ok: true, text: `Sent to ${round.driver?.name || 'the driver'} as round #${round.id}. They have been notified.` });
    } catch (err) {
      setDispatch({ ok: false, text: errorMessage(err) });
    } finally {
      setBusy(false);
    }
  }

  const selectedVehicle = vehicles.find((vehicle) => String(vehicle.id) === String(vehicleId));
  const selectedPlan = result?.plans.find((plan) => plan.key === selectedPlanKey);
  const { markers, lines } = useMemo(
    () => mapLayers(depot, stops, result, selectedPlan),
    [depot, stops, result, selectedPlan],
  );
  const totalDrop = stops.reduce((sum, stop) => sum + (Number(stop.drop_kg) || 0), 0);

  return (
    <div className="op-page">
      <PageHeader
        eyebrow="Admin · round planner"
        title="Round planner"
        description="Find the best order for up to 10 stops. The truck gets lighter after each drop, so the order changes fuel, not just time."
      />
      <ErrorNotice>{error}</ErrorNotice>

      <div className="op-planner">
        <div className="op-stack">
          <section className="op-panel">
            <form className="op-form" onSubmit={optimise}>
              <label>
                Vehicle
                <select className="op-input" value={vehicleId} onChange={(e) => setVehicleId(e.target.value)} required>
                  {!vehicles.length && <option value="">No active vehicles</option>}
                  {vehicles.map((vehicle) => (
                    <option key={vehicle.id} value={vehicle.id}>
                      {vehicle.vehicle_no} · {vehicle.type} · {vehicle.fuel_type} · {amount(vehicle.load_capacity_kg)} kg
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Depot · latitude,longitude
                <input className="op-input" value={depot} onChange={(e) => { setResult(null); setDepot(e.target.value); }} placeholder="Click the map to place the depot" required />
              </label>

              <div>
                <p className="op-note">Stops · total drop {amount(totalDrop)} kg. Click the map to add a stop.</p>
                {stops.map((stop, index) => (
                  <StopRow
                    key={index}
                    index={index}
                    stop={stop}
                    onChange={updateStop}
                    onRemove={removeStop}
                  />
                ))}
              </div>

              <label className="op-row" style={{ fontWeight: 600 }}>
                <input type="checkbox" checked={returnToDepot} onChange={(e) => { setResult(null); setReturnToDepot(e.target.checked); }} />
                Return to the depot at the end
              </label>

              <button className="op-button" disabled={busy || !stops.length || !vehicleId}>
                {busy ? 'Optimising round…' : 'Optimise round'}
              </button>
              <button type="button" className="op-button secondary" onClick={resetRound} disabled={busy}>
                Clear and place points on the map
              </button>
            </form>
          </section>
        </div>

        <div className="op-stack">
          <div className="op-map">
            <MapView markers={markers} lines={lines} onMapClick={handleMapClick} />
          </div>
          <p className="op-note">Numbers show the order of stops. The yellow pin is the depot.</p>
        </div>
      </div>

      {result ? (
        <RoundResult
          result={result}
          selectedPlanKey={selectedPlanKey}
          onSelectPlan={(key) => { setSelectedPlanKey(key); setDispatch(null); }}
          dispatchPanel={(
            <DispatchPanel
              vehicle={selectedVehicle}
              planTitle={PLAN_TITLES[selectedPlanKey] || selectedPlanKey}
              busy={busy}
              outcome={dispatch}
              onSend={sendToDriver}
            />
          )}
        />
      ) : (
        <section className="op-panel">
          <Empty title="No round optimised yet">A Bengaluru example is ready. Press Optimise round.</Empty>
        </section>
      )}
    </div>
  );
}

function StopRow({ index, stop, onChange, onRemove }) {
  return (
    <div className="op-stop-row" style={{ marginTop: 10 }}>
      <label>
        {index + 1}. Label
        <input className="op-input" value={stop.label} onChange={(e) => onChange(index, 'label', e.target.value)} required />
      </label>
      <label>
        Location
        <input className="op-input" value={stop.place} onChange={(e) => onChange(index, 'place', e.target.value)} placeholder="lat,lng" required />
      </label>
      <label>
        Drop kg
        <input className="op-input" type="number" min="0" step="1" value={stop.drop_kg} onChange={(e) => onChange(index, 'drop_kg', e.target.value)} required />
      </label>
      <button type="button" className="op-icon-button" aria-label={`Remove ${stop.label}`} onClick={() => onRemove(index)}>
        <Trash2 size={16} />
      </button>
    </div>
  );
}

// Pins and the drawn path. Before optimising, pins follow the input list;
// afterwards they are numbered in the selected plan's visiting order.
function mapLayers(depot, stops, result, selectedPlan) {
  const markers = [];
  const depotPoint = result?.depot || parseLatLng(depot);
  if (depotPoint) markers.push({ ...depotPoint, label: 'D', title: 'Depot', className: 'depot' });

  if (result && selectedPlan) {
    selectedPlan.order.forEach((stopIndex, position) => {
      const stop = result.stops.find((item) => item.index === stopIndex);
      if (stop) markers.push({ lat: stop.lat, lng: stop.lng, label: String(position + 1), title: `${position + 1}. ${stop.label} · drop ${stop.drop_kg} kg` });
    });
    const lines = selectedPlan.path_points?.length ? [{ points: selectedPlan.path_points, color: '#1b6a45' }] : [];
    return { markers, lines };
  }

  stops.forEach((stop, index) => {
    const point = parseLatLng(stop.place);
    if (point) markers.push({ ...point, label: String(index + 1), title: stop.label });
  });
  return { markers, lines: [] };
}

/** Send the selected plan to the driver of the chosen vehicle. */
function DispatchPanel({ vehicle, planTitle, busy, outcome, onSend }) {
  const driver = vehicle?.assigned_driver_name;
  return (
    <div className="gg-dispatch">
      <div>
        <strong>Send this round to the driver</strong>
        <p className="op-note">
          {driver
            ? `${vehicle.vehicle_no} is driven by ${driver}. They will see the stops in this order.`
            : 'This vehicle has no driver. Assign one on the Vehicles page first.'}
        </p>
        {outcome && <p className={outcome.ok ? 'op-success' : 'op-error-text'} role="status">{outcome.text}</p>}
      </div>
      <button className="op-button" onClick={onSend} disabled={busy || !driver || outcome?.ok}>
        <Send size={16} /> {outcome?.ok ? 'Sent' : `Send ${planTitle.toLowerCase()} plan to ${driver || 'driver'}`}
      </button>
    </div>
  );
}

function RoundResult({ result, selectedPlanKey, onSelectPlan, dispatchPanel }) {
  const selectedPlan = result.plans.find((plan) => plan.key === selectedPlanKey);
  const savings = result.savings_vs_fastest;

  return (
    <>
      <section className="op-panel">
        <div className="op-panel-heading">
          <div>
            <h2>
              {savings && savings.co2_kg > 0
                ? `Greenest saves ${amount(savings.co2_kg)} kg CO₂ (${amount(savings.percent)}%) for ${amount(savings.extra_minutes)} extra min`
                : 'For this round, the fastest order is also the greenest'}
            </h2>
            <p>
              {result.vehicle.vehicle_no} · {result.vehicle.class_label} · {result.vehicle.fuel} · model {result.model}
            </p>
          </div>
        </div>
        <div className="op-plan-grid">
          {result.plans.map((plan) => (
            <PlanCard
              key={plan.key}
              plan={plan}
              selected={plan.key === selectedPlanKey}
              onSelect={() => onSelectPlan(plan.key)}
            />
          ))}
        </div>
        {dispatchPanel}
      </section>

      <div className="op-columns">
        <section className="op-panel">
          <div className="op-panel-heading">
            <h2>{PLAN_TITLES[selectedPlan?.key] || 'Selected'} plan · leg by leg</h2>
            <p>Load falls after each delivery</p>
          </div>
          {selectedPlan && <LegsTable legs={selectedPlan.legs} stops={result.stops} />}
        </section>
        <section className="op-panel">
          <div className="op-panel-heading">
            <div>
              <h2>Time versus CO₂</h2>
              <p>Each point is the optimal order for one time/CO₂ weighting</p>
            </div>
          </div>
          <ParetoChart points={result.pareto} />
        </section>
      </div>

      <section className="op-panel">
        <h2>Inputs and assumptions</h2>
        <p className="op-description">
          Terrain elevation: <strong>{result.elevation_status}</strong>
          {' · '}Weather: <strong>{result.weather?.status || 'unknown'}</strong>
          {result.weather?.temp_c != null && ` (${amount(result.weather.temp_c)} °C${result.weather.wet_road ? ', wet road' : ''})`}
        </p>
        <ul className="op-note" style={{ paddingLeft: 18, marginTop: 10 }}>
          {(result.assumptions || []).map((item) => <li key={item}>{item}</li>)}
        </ul>
      </section>
    </>
  );
}

function PlanCard({ plan, selected, onSelect }) {
  return (
    <button type="button" className={`op-route-card ${selected ? 'selected' : ''}`} onClick={onSelect} aria-pressed={selected}>
      <div className="op-row">
        <RouteIcon size={16} />
        <strong>{PLAN_TITLES[plan.key] || plan.key}</strong>
      </div>
      <div className="op-route-values">
        <div><b>{amount(plan.duration_min)}</b><span>minutes</span></div>
        <div><b>{amount(plan.distance_km)}</b><span>kilometres</span></div>
        <div><b>{amount(plan.co2_kg)}</b><span>kg CO₂</span></div>
      </div>
      <p className="op-note">Fuel {fuelText(plan.fuel, plan.fuel_unit)}</p>
    </button>
  );
}

function stopName(value, stops) {
  if (typeof value === 'string') return value;
  return stops.find((stop) => stop.index === value)?.label || 'Depot';
}

function LegsTable({ legs, stops }) {
  return (
    <div className="op-table-wrap">
      <table className="op-table">
        <thead>
          <tr>
            <th>Leg</th>
            <th>Distance</th>
            <th>Time</th>
            <th>Load carried</th>
            <th>CO₂</th>
          </tr>
        </thead>
        <tbody>
          {legs.map((leg, index) => (
            <tr key={index}>
              <td>{stopName(leg.from, stops)} → {stopName(leg.to, stops)}</td>
              <td>{amount(leg.distance_km)} km</td>
              <td>{amount(leg.duration_min)} min</td>
              <td>{amount(leg.load_kg)} kg</td>
              <td>{amount(leg.co2_kg)} kg</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Scatter of the optimal orders: x = minutes, y = kg CO2, one shared scale per axis.
function ParetoChart({ points = [] }) {
  if (!points.length) return <p className="op-note">No trade-off points returned.</p>;
  const width = 420, height = 240;
  const pad = { left: 52, right: 16, top: 16, bottom: 40 };
  const xs = points.map((p) => p.duration_min);
  const ys = points.map((p) => p.co2_kg);
  const [xMin, xMax] = paddedRange(xs);
  const [yMin, yMax] = paddedRange(ys);
  const x = (value) => pad.left + ((value - xMin) / (xMax - xMin)) * (width - pad.left - pad.right);
  const y = (value) => height - pad.bottom - ((value - yMin) / (yMax - yMin)) * (height - pad.top - pad.bottom);

  return (
    <svg className="op-scatter" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Trade-off between round duration in minutes and CO2 in kilograms">
      <line x1={pad.left} y1={height - pad.bottom} x2={width - pad.right} y2={height - pad.bottom} style={{ stroke: 'var(--gg-line-strong)' }} />
      <line x1={pad.left} y1={pad.top} x2={pad.left} y2={height - pad.bottom} style={{ stroke: 'var(--gg-line-strong)' }} />
      {[xMin, xMax].map((value) => (
        <text key={`x${value}`} x={x(value)} y={height - pad.bottom + 16} fontSize="10" fontFamily="IBM Plex Mono, monospace" style={{ fill: 'var(--gg-faint)' }} textAnchor="middle">{amount(value)}</text>
      ))}
      {[yMin, yMax].map((value) => (
        <text key={`y${value}`} x={pad.left - 6} y={y(value) + 3} fontSize="10" fontFamily="IBM Plex Mono, monospace" style={{ fill: 'var(--gg-faint)' }} textAnchor="end">{amount(value)}</text>
      ))}
      <text x={(pad.left + width - pad.right) / 2} y={height - 6} fontSize="11" style={{ fill: 'var(--gg-muted)' }} textAnchor="middle">Round time (min)</text>
      <text x={14} y={(pad.top + height - pad.bottom) / 2} fontSize="11" style={{ fill: 'var(--gg-muted)' }} textAnchor="middle" transform={`rotate(-90 14 ${(pad.top + height - pad.bottom) / 2})`}>CO₂ (kg)</text>
      {points.map((point, index) => (
        <g key={index}>
          <circle cx={x(point.duration_min)} cy={y(point.co2_kg)} r="5" style={{ fill: 'var(--gg-sign)' }} stroke="#ffffff" strokeWidth="1.5">
            <title>{`Weight ${point.weight}: ${amount(point.duration_min)} min, ${amount(point.co2_kg)} kg CO₂`}</title>
          </circle>
        </g>
      ))}
    </svg>
  );
}

// Axis range with a little room so points never sit on the frame.
function paddedRange(values) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const margin = (max - min) * 0.1 || Math.max(1, Math.abs(max) * 0.05);
  return [min - margin, max + margin];
}
