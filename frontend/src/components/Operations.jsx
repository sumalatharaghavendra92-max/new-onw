import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, RefreshCw, Route, AlertCircle } from 'lucide-react';
import api from '../api/api';
import './operations.css';

export const errorMessage = (error) =>
  error.response?.data?.message || 'Unable to connect. Check the server and try again.';

// The server stores UTC; some endpoints omit the timezone, so a bare timestamp is read as UTC.
const asUtc = (value) =>
  typeof value === 'string' && /T\d{2}:\d{2}/.test(value) && !/(Z|[+-]\d{2}:?\d{2})$/.test(value) ? `${value}Z` : value;

export const formatDate = (value) =>
  value
    ? new Date(asUtc(value)).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : 'Not recorded';

export const amount = (value) =>
  value == null || !Number.isFinite(Number(value))
    ? '—'
    : Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 });

/** Fetch `path` now and every `interval` ms until the component unmounts. */
export function usePolling(path, interval = 15000) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision((value) => value + 1), []);

  useEffect(() => {
    let live = true;
    let timer;
    const controller = new AbortController();

    async function load() {
      try {
        const res = await api.get(path, { signal: controller.signal });
        if (live) {
          setData(res.data);
          setError('');
        }
      } catch (err) {
        if (live) setError(errorMessage(err));
      } finally {
        if (live) {
          setLoading(false);
          timer = setTimeout(load, interval);
        }
      }
    }

    load();
    return () => {
      live = false;
      clearTimeout(timer);
      controller.abort();
    };
  }, [path, interval, revision]);

  return { data, error, loading, reload };
}

export function PageHeader({ eyebrow = 'Operations', title, description, action }) {
  return (
    <header className="op-header">
      <div>
        <p className="op-eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        {description && <p className="op-description">{description}</p>}
      </div>
      {action}
    </header>
  );
}

export function RefreshButton({ onClick }) {
  return (
    <button className="op-button secondary" onClick={onClick}>
      <RefreshCw size={15} /> Refresh
    </button>
  );
}

export function ErrorNotice({ children }) {
  if (!children) return null;
  return (
    <div className="op-error" role="alert">
      <AlertCircle size={18} />
      <span>{children}</span>
    </div>
  );
}

export function Empty({ title, children }) {
  return (
    <div className="op-empty">
      <Route size={28} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}

export function Loading() {
  return (
    <div className="op-loading" role="status">
      <RefreshCw size={18} className="animate-spin" /> Loading saved activity…
    </div>
  );
}

/** One figure in a metrics strip. `lead` marks the figure that matters most. */
export function Metric({ label, value, unit, note, icon: Icon, lead = false }) {
  return (
    <article className={`op-metric ${lead ? 'lead' : ''}`}>
      <div className="op-metric-top">
        <span>{label}</span>
        {Icon && <Icon size={17} />}
      </div>
      <div className="op-value">
        {value}
        {unit && <small>{unit}</small>}
      </div>
      {note && <p>{note}</p>}
    </article>
  );
}

const STATUS_LABELS = { in_progress: 'On the road' };

export function Status({ status }) {
  return <span className={`op-status ${status}`}>{STATUS_LABELS[status] || status}</span>;
}

/** Bar per day: completed trips with a saved route comparison. */
export function ActivityChart({ days = [] }) {
  const max = Math.max(1, ...days.map((day) => day.trips));
  return (
    <div className="op-chart" aria-label="Completed comparable trips over the last seven UTC days">
      {days.map((day) => (
        <div className="op-bar-col" key={day.date}>
          <span>{day.trips}</span>
          <div className="op-bar-track">
            <div
              className="op-bar"
              style={{ height: `${(day.trips / max) * 100}%` }}
              title={`${day.date}: ${day.trips} trips, ${day.savings} kg estimated savings`}
            />
          </div>
          <small>{day.label}</small>
        </div>
      ))}
    </div>
  );
}

function tripLink(trip) {
  return trip.status === 'planned' ? `/driver/new-trip?trip=${trip.id}` : `/driver/active-trip/${trip.id}`;
}

function TripRow({ trip, driver }) {
  const distance = trip.selectedRoute ? `${amount(trip.selectedRoute.distanceKm)} km` : 'Route pending';
  const canOpen = driver && ['planned', 'in_progress'].includes(trip.status);
  return (
    <article className="op-trip-row">
      <div className="op-route-icon"><Route size={18} /></div>
      <div className="op-trip-main">
        <strong>
          {trip.origin} <span className="op-muted">→</span> {trip.destination}
        </strong>
        <p>#{trip.id} · {trip.driverName} · {trip.vehicleId}</p>
      </div>
      <div className="op-trip-detail">
        <strong>{distance}</strong>
        <p>{formatDate(trip.completedAt || trip.startedAt || trip.createdAt)}</p>
      </div>
      <Status status={trip.status} />
      {canOpen && (
        <Link aria-label={`Open trip ${trip.id}`} className="op-icon-button" to={tripLink(trip)}>
          <ArrowUpRight size={19} />
        </Link>
      )}
    </article>
  );
}

export function TripList({ trips = [], driver = false }) {
  if (!trips.length) {
    return <Empty title="No trips yet">Trips show here once a driver plans one.</Empty>;
  }
  return (
    <div className="op-trip-list">
      {trips.map((trip) => <TripRow key={trip.id} trip={trip} driver={driver} />)}
    </div>
  );
}
