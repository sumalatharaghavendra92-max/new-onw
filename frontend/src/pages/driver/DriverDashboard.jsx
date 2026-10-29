import { Link } from 'react-router-dom';
import { ArrowUpRight, Bell, Boxes, Car, Plus } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import {
  usePolling, PageHeader, ErrorNotice, Loading, Empty, Status, TripList, amount, formatDate,
} from '../../components/Operations';
import { ActiveRound, UpcomingRound } from './RoundPanels';

/**
 * The driver's working screen. What it shows depends on the day:
 * a round in progress → a round waiting to start → a single trip → nothing yet.
 */
export default function DriverDashboard() {
  const { user } = useAuth();
  const rounds = usePolling('/rounds/mine', 10000);
  const history = usePolling('/trips/history');
  const notifications = usePolling('/notifications', 30000);

  const trips = history.data?.trips || [];
  const activeTrip = trips.find((trip) => trip.status === 'in_progress');
  const activeRound = rounds.data?.active || null;
  const upcoming = rounds.data?.upcoming || [];
  const recentRounds = rounds.data?.recent || [];
  const vehicle = rounds.data?.vehicle || toVehicle(user?.driver?.vehicle);
  const unread = (notifications.data || []).filter((item) => !item.is_read).length;

  return (
    <div className="op-page">
      <PageHeader
        eyebrow="Driver"
        title={`Hello, ${user?.name?.split(' ')[0] || 'driver'}`}
        description={headline({ activeRound, upcoming, activeTrip, vehicle })}
        action={<NotificationsLink unread={unread} />}
      />
      <ErrorNotice>{history.error}</ErrorNotice>

      {rounds.loading && history.loading ? <Loading /> : (
        <>
          <TodayPanel
            activeRound={activeRound}
            upcoming={upcoming}
            activeTrip={activeTrip}
            vehicle={vehicle}
            onChange={() => { rounds.reload(); history.reload(); }}
          />

          <div className="op-columns">
            <RecentActivity rounds={recentRounds} trips={trips} />
            <MyVehicle vehicle={vehicle} />
          </div>
        </>
      )}
    </div>
  );
}

// /auth/me gives the vehicle in a different shape; use it until /rounds/mine answers.
function toVehicle(raw) {
  if (!raw) return null;
  return { id: raw.id, vehicle_no: raw.vehicle_no, class: raw.type, fuel: raw.fuel_type, capacity_kg: raw.load_capacity_kg };
}

function headline({ activeRound, upcoming, activeTrip, vehicle }) {
  if (activeRound) return `You are on round #${activeRound.id}. ${activeRound.stop_count - activeRound.delivered_count} stops left.`;
  if (upcoming.length) return `You have ${upcoming.length} round${upcoming.length === 1 ? '' : 's'} waiting. Start when you leave the depot.`;
  if (activeTrip) return `Trip #${activeTrip.id} is in progress.`;
  if (vehicle) return 'No round today. You can plan your own trip.';
  return 'Ask your admin to give you a vehicle first.';
}

function NotificationsLink({ unread }) {
  return (
    <Link className="op-button secondary" to="/driver/notifications">
      <Bell size={16} /> {unread ? `${unread} new` : 'Notifications'}
    </Link>
  );
}

/** The one big panel at the top: what to do right now. */
function TodayPanel({ activeRound, upcoming, activeTrip, vehicle, onChange }) {
  if (activeRound) return <ActiveRound round={activeRound} onChange={onChange} />;
  if (upcoming.length) {
    return (
      <>
        <UpcomingRound round={upcoming[0]} onChange={onChange} />
        {upcoming.length > 1 && <p className="op-note">{upcoming.length - 1} more round(s) after this one.</p>}
      </>
    );
  }
  if (activeTrip) {
    return (
      <section className="op-panel gg-today-empty">
        <div>
          <h2>Trip in progress</h2>
          <p className="op-description">{activeTrip.origin} → {activeTrip.destination} · trip #{activeTrip.id}</p>
        </div>
        <Link className="op-button gg-big-button" to={`/driver/active-trip/${activeTrip.id}`}>
          Resume trip <ArrowUpRight size={17} />
        </Link>
      </section>
    );
  }
  return (
    <section className="op-panel gg-today-empty">
      <div>
        <h2>No round assigned yet</h2>
        <p className="op-description">
          When your admin sends you a round, it shows here with every stop in order.
        </p>
      </div>
      {vehicle && (
        <Link className="op-button" to="/driver/new-trip">
          <Plus size={16} /> Plan a single trip
        </Link>
      )}
    </section>
  );
}

function MyVehicle({ vehicle }) {
  if (!vehicle) {
    return (
      <section className="op-panel">
        <h2>My vehicle</h2>
        <Empty title="No vehicle yet">Ask your admin to assign one.</Empty>
      </section>
    );
  }
  const calibration = vehicle.calibration;
  return (
    <section className="op-panel">
      <div className="op-panel-heading">
        <h2>My vehicle</h2>
        <Car size={18} />
      </div>
      <p className="gg-plate">{vehicle.vehicle_no}</p>
      <dl className="gg-facts">
        <div><dt>Type</dt><dd className="cap">{vehicle.class || '—'}</dd></div>
        <div><dt>Fuel</dt><dd className="cap">{vehicle.fuel || '—'}</dd></div>
        <div><dt>Capacity</dt><dd className="op-num">{amount(vehicle.capacity_kg)} kg</dd></div>
      </dl>
      {calibration && <LearnedFuel calibration={calibration} />}
    </section>
  );
}

/** "Uses 4% more fuel than expected · learned from 3 trips · ±12%". */
function LearnedFuel({ calibration }) {
  const percent = Math.round((calibration.factor - 1) * 100);
  let text = 'Uses fuel as the model expected';
  if (percent > 0) text = `Uses ${percent}% more fuel than expected`;
  if (percent < 0) text = `Uses ${Math.abs(percent)}% less fuel than expected`;
  if (!calibration.trips) text = 'Not learned yet. Report fuel after your trips.';
  return (
    <div className="gg-learned">
      <strong>{text}</strong>
      <p className="op-num">
        Learned from {calibration.trips} trip{calibration.trips === 1 ? '' : 's'} · ±{amount(calibration.uncertainty_pct)}%
        {calibration.rejected ? ` · ${calibration.rejected} report(s) ignored` : ''}
      </p>
    </div>
  );
}

function RecentActivity({ rounds, trips }) {
  return (
    <section className="op-panel">
      <div className="op-panel-heading">
        <div>
          <h2>Recent work</h2>
          <p>Finished rounds and trips</p>
        </div>
        <Link className="op-small-link" to="/driver/history">All trips <ArrowUpRight size={15} /></Link>
      </div>
      {rounds.length > 0 && (
        <div className="op-trip-list">
          {rounds.slice(0, 3).map((round) => <RoundRow key={round.id} round={round} />)}
        </div>
      )}
      <TripList trips={trips.slice(0, rounds.length ? 3 : 5)} driver />
    </section>
  );
}

function RoundRow({ round }) {
  return (
    <article className="op-trip-row">
      <div className="op-route-icon"><Boxes size={18} /></div>
      <div className="op-trip-main">
        <strong>Round #{round.id} · {round.stop_count} stops</strong>
        <p className="op-num">{amount(round.distance_km)} km · {amount(round.co2_kg)} kg CO₂</p>
      </div>
      <div className="op-trip-detail">
        <strong className="op-num">{round.actual_fuel_l != null ? `${amount(round.actual_fuel_l)} ${round.fuel_unit}` : '—'}</strong>
        <p>{formatDate(round.ended_at || round.started_at || round.created_at)}</p>
      </div>
      <Status status={round.status} />
    </article>
  );
}

