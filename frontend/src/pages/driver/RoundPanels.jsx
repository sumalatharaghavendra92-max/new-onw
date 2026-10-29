import { useMemo, useState } from 'react';
import { Navigation, PackageCheck, Play, Flag } from 'lucide-react';
import api from '../../api/api';
import MapView from '../../components/MapView';
import { ErrorNotice, amount, errorMessage, formatDate } from '../../components/Operations';
import {
  navigateUrl, roundMapLayers, lastPosition, RoundProgress, StopList, RoundFigures, RoundSummaryLine,
} from '../../components/RoundViews';
import useGpsSharing from '../../components/useGpsSharing';

/** The round the driver is driving right now. */
export function ActiveRound({ round, onChange }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const { position, status } = useGpsSharing(`/rounds/${round.id}/log`, true);
  const { markers, lines } = useMemo(() => roundMapLayers(round), [round]);
  const current = position || lastPosition(round);
  const allDelivered = !round.next_stop;

  async function run(action) {
    setBusy(true);
    setError('');
    try {
      await action();
      await onChange();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function markDelivered() {
    return run(() => api.post(`/rounds/${round.id}/stops/${round.next_stop.position}/deliver`));
  }

  return (
    <section className="op-panel gg-round">
      <div className="op-panel-heading">
        <div>
          <h2>Today’s round</h2>
          <p className="op-num">
            Round #{round.id} · started {formatDate(round.started_at)}
          </p>
        </div>
        <span className={`op-live ${status.state === 'sharing' ? '' : 'stale'}`}>
          <i />{status.state === 'sharing' ? 'Sharing location' : status.state === 'blocked' ? 'Location blocked' : 'Waiting for GPS'}
        </span>
      </div>

      <RoundProgress round={round} />
      <div className="gg-round-figures">
        <Figure value={`${round.delivered_count} / ${round.stop_count}`} label="stops delivered" />
        <Figure value={amount(round.load_now_kg)} unit="kg" label="load left in the truck" />
        <Figure value={amount(round.co2_kg)} unit="kg" label="planned CO₂" />
      </div>
      <ErrorNotice>{error}</ErrorNotice>

      <div className="gg-round-body">
        <div className="op-stack">
          {allDelivered
            ? <AllDelivered />
            : <NextStop stop={round.next_stop} busy={busy} onDelivered={markDelivered} />}
          <StopList round={round} />
          <FinishRound round={round} busy={busy} onFinish={(body) => run(() => api.post(`/rounds/${round.id}/end`, body))} />
        </div>
        <div className="op-stack">
          <div className="op-map gg-round-map">
            <MapView markers={markers} lines={lines} currentLocation={current} />
          </div>
          <p className="op-note" role="status">{status.text}</p>
        </div>
      </div>
    </section>
  );
}

function Figure({ value, unit, label }) {
  return (
    <div>
      <b className="op-num">{value}{unit && <small> {unit}</small>}</b>
      <span>{label}</span>
    </div>
  );
}

function NextStop({ stop, busy, onDelivered }) {
  return (
    <div className="gg-next-stop">
      <p className="op-eyebrow">Next stop · {stop.position + 1}</p>
      <h3>{stop.label}</h3>
      <p className="op-num">Drop {amount(stop.drop_kg)} kg</p>
      <div className="gg-next-actions">
        <a className="op-button secondary" href={navigateUrl(stop.lat, stop.lng)} target="_blank" rel="noopener noreferrer">
          <Navigation size={16} /> Navigate
        </a>
        <button className="op-button gg-big-button" onClick={onDelivered} disabled={busy}>
          <PackageCheck size={18} /> {busy ? 'Saving…' : 'Mark delivered'}
        </button>
      </div>
    </div>
  );
}

function AllDelivered() {
  return (
    <div className="gg-next-stop">
      <p className="op-eyebrow">All stops done</p>
      <h3>Drive back and finish the round</h3>
      <p>Enter the fuel you used below, then press Finish round.</p>
    </div>
  );
}

function FinishRound({ round, busy, onFinish }) {
  const [fuel, setFuel] = useState('');
  const unit = round.fuel_unit || 'L';

  function submit(event) {
    event.preventDefault();
    onFinish(fuel === '' ? {} : { actual_fuel_l: Number(fuel) });
  }

  return (
    <form className="op-form gg-finish" onSubmit={submit}>
      <label>
        Fuel used ({unit}) · optional
        <input
          className="op-input"
          type="number"
          min="0"
          step="0.1"
          value={fuel}
          onChange={(e) => setFuel(e.target.value)}
          placeholder={`Planned about ${amount(round.fuel)} ${unit}`}
        />
      </label>
      <p className="op-note">Your number teaches the app how much fuel this vehicle really uses.</p>
      <button className="op-button secondary" disabled={busy}>
        <Flag size={16} /> Finish round
      </button>
    </form>
  );
}

/** A dispatched round waiting to start. */
export function UpcomingRound({ round, onChange }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const { markers, lines } = useMemo(() => roundMapLayers(round), [round]);

  async function start() {
    setBusy(true);
    setError('');
    try {
      await api.post(`/rounds/${round.id}/start`);
      await onChange();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <section className="op-panel gg-round">
      <div className="op-panel-heading">
        <div>
          <h2>Your next round</h2>
          <p className="op-num">Round #{round.id} · sent {formatDate(round.created_at)}</p>
        </div>
      </div>
      <RoundFigures round={round} />
      <RoundSummaryLine round={round} />
      <ErrorNotice>{error}</ErrorNotice>
      <div className="gg-round-body">
        <div className="op-stack">
          <StopList round={round} />
          <button className="op-button gg-big-button" onClick={start} disabled={busy}>
            <Play size={18} /> {busy ? 'Starting…' : 'Start round'}
          </button>
          <p className="op-note">Start when you leave the depot. Your location is shared while you drive.</p>
        </div>
        <div className="op-map gg-round-map">
          <MapView markers={markers} lines={lines} />
        </div>
      </div>
    </section>
  );
}
