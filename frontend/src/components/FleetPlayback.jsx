import { useEffect, useMemo, useRef, useState } from 'react';
import api from '../api/api';
import MapView from './MapView';
import { ErrorNotice } from './Operations';
import { sampleFleetAt } from './sampleFleetMotion';

export default function FleetPlayback() {
  const [vehicles, setVehicles] = useState([]);
  const [started, setStarted] = useState(false);
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const [speed, setSpeed] = useState(1);
  const [selected, setSelected] = useState(null);
  const lastTick = useRef(null);

  useEffect(() => {
    if (!running) return undefined;
    lastTick.current = performance.now();
    const timer = setInterval(() => {
      const now = performance.now();
      const delta = (now - lastTick.current) / 1000;
      lastTick.current = now;
      setElapsed(value => value + delta * speed);
    }, 500);
    return () => clearInterval(timer);
  }, [running, speed]);

  const fleet = useMemo(() => sampleFleetAt(vehicles, elapsed), [vehicles, elapsed]);
  const dots = useMemo(() => fleet.map(v => ({lat: v.lat, lng: v.lng, color: v.color, radius: 7,
    title: `SIMULATED · ${v.plate} · ${v.status} · ${v.fuelPercent}% · ${v.loadKg} kg`})), [fleet]);
  const chosen = fleet.find(v => v.id === selected);
  const lines = useMemo(() => chosen ? [{points: chosen.path, color: '#326fa0'}] : [], [chosen]);

  async function start() {
    setLoading(true); setError('');
    try {
      const {data} = await api.get('/vehicles');
      const samples = data.filter(v => /^SAMPLE-\d+$/.test(v.vehicle_no)).slice(0, 25);
      if (!samples.length) throw new Error('No SAMPLE vehicles found. Run import-sample-fleet in your backend terminal first.');
      setVehicles(samples); setElapsed(0); setSelected(null); setStarted(true); setRunning(true);
    } catch (err) {
      setError(err.response?.data?.message || err.message || 'Could not load sample vehicles.');
    } finally { setLoading(false); }
  }

  return (
    <section className="op-panel" aria-label="Fleet simulation">
      <div className="op-panel-heading">
        <div>
          <h2>25-vehicle delivery simulation</h2>
          <p><strong>SIMULATION — fictional activity, not live GPS.</strong> Uses your SAMPLE vehicles only.</p>
        </div>
        <button className="pub-btn pub-btn-primary" disabled={loading} onClick={start}>
          {loading ? 'Loading fleet…' : started ? 'Restart simulation' : 'Run 25-vehicle simulation'}
        </button>
      </div>
      <ErrorNotice>{error}</ErrorNotice>
      {!started && <p className="op-note">Animate deliveries for your presentation: moving markers, unloading, returning and reloading. Real trips and reports stay separate.</p>}
      {started && <>
        <div className="op-row" style={{gap: 16, flexWrap: 'wrap', marginBottom: 16}}>
          <button className="pub-btn pub-btn-ghost" onClick={() => setRunning(value => !value)}>{running ? 'Pause simulation' : 'Resume simulation'}</button>
          <label>Playback speed <select className="op-input" value={speed} onChange={e => setSpeed(Number(e.target.value))}>
            <option value="1">1×</option><option value="5">5×</option><option value="10">10×</option>
          </select></label>
          <span role="status">{running ? 'Running' : 'Paused'} · {fleet.length} simulated vehicles · {Math.floor(elapsed)} simulated seconds</span>
        </div>
        <div className="op-metrics" aria-label="Simulation totals">
          <p><strong>{fleet.filter(v => v.status === 'Driving' || v.status === 'Returning').length}</strong> moving (simulated)</p>
          <p><strong>{fleet.filter(v => v.status === 'Delivering').length}</strong> unloading (simulated)</p>
          <p><strong>{fleet.reduce((sum, v) => sum + v.delivered, 0)}</strong> deliveries (simulated)</p>
          <p><strong>{fleet.reduce((sum, v) => sum + v.loadKg, 0).toLocaleString()}</strong> kg on board (simulated)</p>
        </div>
        <div style={{height: 440, marginBottom: 16}}><MapView dots={dots} lines={lines} fitOnUpdate={false} /></div>
        <p className="op-note">Select a vehicle to show its schematic delivery loop. Paths are straight-line illustrations, not road navigation. Values are synthetic; fuel/battery and load reset at each depot cycle. Imported maintenance vehicles participate only as fictional simulation actors. Nothing is written to GPS, inventory readings, completed trips, savings or reports. Playback resets when you leave this page.</p>
        <div className="op-table-wrap"><table className="op-table">
          <thead><tr>{['Vehicle', 'Type', 'Fuel', 'Action', 'Speed km/h', 'Fuel / battery %', 'Load kg', 'Capacity kg', 'Odometer km', 'Drops', 'Next stop'].map(label => <th key={label}>{label}</th>)}</tr></thead>
          <tbody>{fleet.map(v => <tr key={v.id}>
            <td><button className="pub-btn pub-btn-ghost" onClick={() => setSelected(v.id)}>{v.plate}</button></td>
            <td>{v.type}</td><td>{v.fuelType}</td><td>{v.status}</td><td>{v.speedKmh}</td>
            <td>{v.fuelPercent}</td><td>{v.loadKg}</td><td>{v.capacity}</td><td>{v.odometerKm}</td><td>{v.delivered}</td><td>{v.nextStop}</td>
          </tr>)}</tbody>
        </table></div>
      </>}
    </section>
  );
}
