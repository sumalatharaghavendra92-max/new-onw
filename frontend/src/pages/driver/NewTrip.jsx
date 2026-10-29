import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowRight, Check } from 'lucide-react';
import api from '../../api/api';
import MapView from '../../components/MapView';
import { PageHeader, ErrorNotice, errorMessage, amount } from '../../components/Operations';
import { BreakdownBar, BreakdownLegend, breakdownTotal, fuelText } from '../../components/ModelViews';

export default function NewTrip() {
  const [params, setParams] = useSearchParams();
  const savedId = params.get('trip');
  const navigate = useNavigate();
  const [source, setSource] = useState('Bengaluru');
  const [destination, setDestination] = useState('Mysuru');
  const [weight, setWeight] = useState('0');
  const [trip, setTrip] = useState(null);
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!savedId) return;
    let live = true;
    setBusy(true);
    api.get(`/trips/${savedId}`).then(({ data }) => {
      if (!live) return;
      if (data.status === 'in_progress') { navigate(`/driver/active-trip/${data.id}`, { replace: true }); return; }
      setTrip(data); setSelected(data.selectedRouteId || data.routes.find(r => r.isDefault)?.id || data.routes.find(r => r.isAiRecommended)?.id || data.routes[0]?.id);
      setSource(data.origin); setDestination(data.destination); setWeight(String(data.loadWeight));
    }).catch(err => { if (live) setError(errorMessage(err)); }).finally(() => { if (live) setBusy(false); });
    return () => { live = false; };
  }, [savedId, navigate]);
  async function plan(event) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const { data } = await api.post('/trips', { source, destination, load_weight_kg: Number(weight) });
      setTrip(data); setSelected(data.routes.find(r => r.isDefault)?.id || data.routes.find(r => r.isAiRecommended)?.id || data.routes[0]?.id); setParams({ trip: data.id });
    } catch (err) { setError(errorMessage(err)); } finally { setBusy(false); }
  }
  async function start() {
    setBusy(true); setError('');
    try {
      await api.patch(`/trips/${trip.id}/select-route`, { route_id: selected });
      await api.post(`/trips/${trip.id}/start`);
      navigate(`/driver/active-trip/${trip.id}`);
    } catch (err) { setError(errorMessage(err)); } finally { setBusy(false); }
  }
  async function discard() {
    setBusy(true); setError('');
    try { await api.post(`/trips/${trip.id}/cancel`); setTrip(null); setSelected(null); setParams({}); }
    catch (err) { setError(errorMessage(err)); } finally { setBusy(false); }
  }

  const routes = trip?.routes || [];
  const scaleMax = Math.max(0, ...routes.map((route) => breakdownTotal(route.breakdown)));
  const editable = trip?.status === 'planned';

  return (
    <div className="op-page">
      <PageHeader
        eyebrow="Driver · plan a trip"
        title="Plan a trip"
        description="Up to three real roads. Each shows its fuel and CO₂, and what causes it. Pick one and start."
      />
      <ErrorNotice>{error}</ErrorNotice>

      <div className="op-planner">
        <div className="op-stack">
          <section className="op-panel">
            <form onSubmit={plan} className="op-form">
              <label>Origin<input className="op-input" value={source} onChange={e => setSource(e.target.value)} required disabled={!!trip || busy} /></label>
              <label>Destination<input className="op-input" value={destination} onChange={e => setDestination(e.target.value)} required disabled={!!trip || busy} /></label>
              <label>Cargo weight · kg<input className="op-input" type="number" min="0" step="0.1" value={weight} onChange={e => setWeight(e.target.value)} required disabled={!!trip || busy} /></label>
              <p className="op-note">
                Type a city (Bengaluru, Mysuru, Hosur, Chennai…) or a latitude,longitude.
              </p>
              <PlanActions trip={trip} busy={busy} onDiscard={discard} />
            </form>
          </section>

          {routes.length > 0 && (
            <>
              <section className="op-panel">
                <h2>Why this route?</h2>
                <p className="op-description">{routes[0]?.decisionPolicy?.reason}</p>
                <p className="op-note">
                  {trip.predictionMode}. We pick the road with the least CO₂ that is at most 15% slower than the fastest. If the saving is tiny, we keep the fastest road. CO₂ comes from speed, hills, weight and weather. Plans expire after 30 minutes.
                </p>
                <BreakdownLegend />
              </section>

              {routes.map(route => (
                <RouteOption
                  key={route.id}
                  route={route}
                  scaleMax={scaleMax}
                  selected={selected === route.id}
                  disabled={busy || !editable}
                  onSelect={() => setSelected(route.id)}
                />
              ))}

              {editable && (
                <button disabled={busy || !selected} onClick={start} className="op-button">
                  {busy ? 'Starting…' : 'Start trip'} <ArrowRight size={16} />
                </button>
              )}
            </>
          )}
        </div>

        <div className="op-stack">
          <div className="op-map">
            <MapView routes={routes} selectedRouteId={selected} origin={source} destination={destination} />
          </div>
          <p className="op-note">Your plan is saved. If the map service is down, no trip is created.</p>
        </div>
      </div>
    </div>
  );
}

function PlanActions({ trip, busy, onDiscard }) {
  if (!trip) {
    return (
      <button disabled={busy} className="op-button">
        {busy ? 'Finding road alternatives…' : 'Compare routes'} <ArrowRight size={15} />
      </button>
    );
  }
  if (trip.status === 'planned') {
    return (
      <button type="button" className="op-button secondary" disabled={busy} onClick={onDiscard}>
        Cancel this plan and start again
      </button>
    );
  }
  return <p className="op-note">This trip is {trip.status}. Open a new plan from the dashboard.</p>;
}

// One road alternative. Physics fields (breakdown, climb, speed) are absent on older saved trips.
function RouteOption({ route, scaleMax, selected, disabled, onSelect }) {
  return (
    <button disabled={disabled} className={`op-route-card ${selected ? 'selected' : ''}`} onClick={onSelect} aria-pressed={selected}>
      <div className="op-row">
        <strong>{route.title}</strong>
        {selected && <Check size={16} />}
      </div>

      <div className="op-route-values">
        <div><b>{amount(route.distanceKm)}</b><span>kilometres</span></div>
        <div><b>{amount(route.durationMin)}</b><span>minutes</span></div>
        <div>
          <b>{amount(route.co2Kg)}</b>
          <span>kg CO₂{route.uncertaintyPct != null && ` ± ${amount(route.uncertaintyPct)}%`}</span>
        </div>
      </div>

      <BreakdownBar breakdown={route.breakdown} scaleMax={scaleMax} />

      {route.evidence?.limitations?.map(note => <p className="op-note" key={note}>{note}</p>)}

      <p className="op-note">
        {fuelText(route.fuelLiters, route.fuelUnit)} predicted
        {route.climbM != null && ` · climb ${amount(route.climbM)} m`}
        {route.avgSpeedKmh != null && ` · avg ${amount(route.avgSpeedKmh)} km/h`}
        {' · '}{route.isFastest ? 'Fastest alternative' : 'Alternative road route'}
      </p>
      {route.ecoScore != null && (
        <p className="op-note">Eco score {amount(route.ecoScore)} · 50 = typical mixed driving for this vehicle class, 100 = zero CO₂</p>
      )}
    </button>
  );
}
