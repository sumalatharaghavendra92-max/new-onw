import { Check, MapPin } from 'lucide-react';
import { amount, formatDate } from './Operations';
import { fuelText } from './ModelViews';

/** Google Maps turn-by-turn directions to one point (opens the app on phones). */
export function navigateUrl(lat, lng) {
  return `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`;
}

/** Pins and path for a dispatched round: depot, stops in visiting order, delivered stops greyed. */
export function roundMapLayers(round) {
  if (!round) return { markers: [], lines: [] };
  const nextPosition = round.next_stop?.position;
  const markers = [];
  if (round.depot) {
    markers.push({ lat: round.depot.lat, lng: round.depot.lng, label: 'D', title: 'Depot', className: 'depot' });
  }
  round.stops.forEach((stop) => {
    let className = '';
    if (stop.delivered_at) className = 'done';
    else if (stop.position === nextPosition) className = 'next';
    markers.push({
      lat: stop.lat,
      lng: stop.lng,
      label: String(stop.position + 1),
      title: `${stop.position + 1}. ${stop.label} · ${amount(stop.drop_kg)} kg`,
      className,
    });
  });
  const lines = round.path_points?.length ? [{ points: round.path_points }] : [];
  return { markers, lines };
}

export function lastPosition(round) {
  return round?.last_location ? [round.last_location.lat, round.last_location.lng] : null;
}

/** Thin bar: share of stops delivered. */
export function RoundProgress({ round }) {
  const total = round.stop_count || round.stops.length;
  const done = round.delivered_count || 0;
  const percent = total ? Math.round((done / total) * 100) : 0;
  return (
    <div className="gg-progress" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={done}>
      <div className="gg-progress-bar" style={{ width: `${percent}%` }} />
    </div>
  );
}

/** Ordered stop list with done / next / waiting states. */
export function StopList({ round }) {
  const nextPosition = round.next_stop?.position;
  return (
    <ol className="gg-stop-list">
      {round.stops.map((stop) => {
        const done = Boolean(stop.delivered_at);
        const isNext = !done && stop.position === nextPosition;
        return (
          <li key={stop.position} className={done ? 'done' : isNext ? 'next' : ''}>
            <span className="gg-stop-number">{done ? <Check size={14} /> : stop.position + 1}</span>
            <div>
              <strong>{stop.label}</strong>
              <p className="op-num">
                {amount(stop.drop_kg)} kg
                {done && ` · delivered ${formatDate(stop.delivered_at)}`}
                {isNext && ' · next'}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/** Distance, time, CO₂ and fuel of a round, in one line of numbers. */
export function RoundFigures({ round }) {
  return (
    <div className="op-route-values four">
      <div><b>{round.stop_count || round.stops.length}</b><span>stops</span></div>
      <div><b>{amount(round.distance_km)}</b><span>km</span></div>
      <div><b>{amount(round.duration_min)}</b><span>min</span></div>
      <div><b>{amount(round.co2_kg)}</b><span>kg CO₂</span></div>
    </div>
  );
}

export function RoundSummaryLine({ round }) {
  return (
    <p className="op-note">
      <MapPin size={13} style={{ display: 'inline', verticalAlign: '-2px' }} />{' '}
      {round.vehicle?.vehicle_no} · {round.plan_key} order · fuel {fuelText(round.fuel, round.fuel_unit)}
    </p>
  );
}
