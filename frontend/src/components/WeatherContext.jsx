import { useState } from 'react';
import { usePolling, ErrorNotice, Metric, amount, formatDate } from './Operations';

const LOCATIONS = {
  Bengaluru: [12.972, 77.594],
  Mysuru: [12.296, 76.639],
  Chennai: [13.083, 80.271],
  Mumbai: [19.076, 72.878],
  Delhi: [28.614, 77.209],
  Hyderabad: [17.385, 78.487],
};

function statusLabel(data, loading, error) {
  if (loading) return 'Fetching weather…';
  if (error) return 'Connection lost';
  if (data?.status === 'available') return 'Current';
  if (data?.status === 'stale') return 'Stale';
  return 'Unavailable';
}

function WeatherReading({ city }) {
  const [lat, lon] = LOCATIONS[city];
  const { data, loading, error, reload } = usePolling(`/context/weather?latitude=${lat}&longitude=${lon}`, 600000);
  const current = data?.current;
  const stale = Boolean(error || data?.status !== 'available');

  return (
    <>
      <div className="op-row my-4">
        <span className={`op-live ${stale ? 'stale' : ''}`}><i />{statusLabel(data, loading, error)}</span>
        <button type="button" className="op-small-link" onClick={reload}>Check again</button>
      </div>
      <ErrorNotice>{error || data?.warning}</ErrorNotice>

      {current && (
        <div className="op-metrics">
          <Metric label="Air temperature" value={amount(current.temperature_2m)} unit={data.units.temperature_2m} note="Sets air density and AC load" />
          <Metric label="Precipitation" value={amount(current.precipitation)} unit={data.units.precipitation} note="Over 0.2 mm/h = wet road" />
          <Metric label="Wind speed" value={amount(current.wind_speed_10m)} unit={data.units.wind_speed_10m} note="Shown only; not in the model" />
          <Metric
            label="Data age"
            value={amount(Math.max(0, data.source_age_seconds) / 60)}
            unit="min"
            note={data.cached ? 'From server cache' : 'Fetched from provider'}
          />
        </div>
      )}

      <p className="op-note mt-4">
        Valid at <span className="op-num">{formatDate(data?.valid_at)}</span> · fetched{' '}
        <span className="op-num">{formatDate(data?.fetched_at)}</span> · city centre{' '}
        <span className="op-num">{lat}, {lon}</span>
      </p>
      <p className="op-note">
        <a href="https://open-meteo.com/" target="_blank" rel="noreferrer" className="op-small-link">
          Weather data by Open-Meteo (CC BY 4.0)
        </a>{' '}
        · weather-model estimates, not station readings.
      </p>
    </>
  );
}

export default function WeatherContext() {
  const [city, setCity] = useState('Bengaluru');

  return (
    <section className="op-panel">
      <div className="op-panel-heading">
        <div>
          <h2>Live weather</h2>
          <p>The fuel model uses this weather when you plan a trip.</p>
        </div>
        <label className="op-note">
          City
          <select className="op-input" value={city} onChange={(event) => setCity(event.target.value)}>
            {Object.keys(LOCATIONS).map((name) => <option key={name}>{name}</option>)}
          </select>
        </label>
      </div>
      <p className="op-description">
        Temperature changes air density and air-conditioning load; rain raises rolling resistance. Live traffic is not part of this feed.
      </p>
      <WeatherReading key={city} city={city} />
    </section>
  );
}
