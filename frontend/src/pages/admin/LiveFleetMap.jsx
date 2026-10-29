import { useMemo, useState } from 'react';
import FleetPlayback from '../../components/FleetPlayback';
import MapView from '../../components/MapView';
import { usePolling, PageHeader, ErrorNotice, Loading, Empty, RefreshButton, formatDate, amount } from '../../components/Operations';
import { roundMapLayers, lastPosition, RoundProgress, StopList } from '../../components/RoundViews';

const FRESH_MS = 60000;

function isFresh(location) {
  return location && Date.now() - new Date(location.timestamp).getTime() < FRESH_MS;
}

function gpsLabel(location, error) {
  if (error) return 'Connection lost';
  if (!location) return 'Waiting for GPS';
  return isFresh(location) ? 'Live GPS' : 'Location stale';
}

function GpsState({ location, error }) {
  return (
    <span className={`op-live ${!isFresh(location) || error ? 'stale' : ''}`}>
      <i />{gpsLabel(location, error)}
    </span>
  );
}

function TripCard({ trip, selected, error, onSelect }) {
  return (
    <button onClick={onSelect} className={`op-fleet-card ${selected ? 'selected' : ''}`}>
      <strong>{trip.driverName}</strong>
      <GpsState location={trip.lastLocation} error={error} />
      <p>Trip · {trip.origin} → {trip.destination}</p>
      <p className="op-num">#{trip.id} · {trip.vehicleId}</p>
      <p className="op-num">Last fix {formatDate(trip.lastLocation?.timestamp)}</p>
    </button>
  );
}

function RoundCard({ round, selected, error, onSelect }) {
  return (
    <button onClick={onSelect} className={`op-fleet-card ${selected ? 'selected' : ''}`}>
      <strong>{round.driver?.name}</strong>
      <GpsState location={round.last_location} error={error} />
      <p>Round · {round.delivered_count} of {round.stop_count} stops delivered</p>
      <p className="op-num">#{round.id} · {round.vehicle?.vehicle_no} · {amount(round.load_now_kg)} kg left</p>
      <p className="op-num">Last fix {formatDate(round.last_location?.timestamp)}</p>
    </button>
  );
}

function TripMap({ trip, dots }) {
  return (
    <>
      <div className="op-map">
        <MapView
          routes={trip.routes}
          selectedRouteId={trip.selectedRouteId}
          origin={trip.origin}
          destination={trip.destination}
          currentLocation={trip.lastLocation ? [trip.lastLocation.lat, trip.lastLocation.lng] : null}
          dots={dots}
        />
      </div>
      <p className="op-note">
        {trip.lastLocation ? 'The pulsing dot is where the phone last sent its location.' : 'No location yet. Showing the planned road.'}
      </p>
    </>
  );
}

function RoundMap({ round, dots }) {
  const { markers, lines } = useMemo(() => roundMapLayers(round), [round]);
  return (
    <>
      <div className="op-map">
        <MapView markers={markers} lines={lines} currentLocation={lastPosition(round)} dots={dots} />
      </div>
      <section className="op-panel">
        <div className="op-panel-heading">
          <h2>Round #{round.id}</h2>
          <p className="op-num">{round.delivered_count} / {round.stop_count} delivered</p>
        </div>
        <RoundProgress round={round} />
        <StopList round={round} />
      </section>
    </>
  );
}

export default function LiveFleetMap() {
  const { data, error, loading, reload } = usePolling('/admin/fleet', 15000);
  const [selectedKey, setSelectedKey] = useState(null);
  const dots = [];
  // One list for both kinds of work on the road; keys keep trip #3 and round #3 apart.
  const items = [
    ...(data?.rounds || []).map((round) => ({ key: `round-${round.id}`, round })),
    ...(data?.trips || []).map((trip) => ({ key: `trip-${trip.id}`, trip })),
  ];
  const selected = items.find((item) => item.key === selectedKey) || items[0];

  return (
    <div className="op-page">
      <PageHeader
        eyebrow="Admin · live fleet"
        title="Live fleet"
        description="Rounds and trips on the road right now, from each driver's phone GPS. Updates every 15 seconds."
        action={<RefreshButton onClick={reload} />}
      />
      <FleetPlayback />
      <h2>Actual driver GPS</h2>
      <ErrorNotice>{error}</ErrorNotice>


      {loading ? <Loading /> : !items.length ? (
        <section className="op-panel">
          <Empty title="Nothing on the road">A round or trip shows here when a driver starts it.</Empty>
        </section>
      ) : (
        <div className="op-fleet-grid">
          <div className="op-stack">
            {items.map((item) => (item.round ? (
              <RoundCard key={item.key} round={item.round} selected={item.key === selected.key} error={error} onSelect={() => setSelectedKey(item.key)} />
            ) : (
              <TripCard key={item.key} trip={item.trip} selected={item.key === selected.key} error={error} onSelect={() => setSelectedKey(item.key)} />
            )))}
          </div>
          <div className="op-stack">
            {selected.round ? <RoundMap round={selected.round} dots={dots} /> : <TripMap trip={selected.trip} dots={dots} />}
          </div>
        </div>
      )}
    </div>
  );
}
