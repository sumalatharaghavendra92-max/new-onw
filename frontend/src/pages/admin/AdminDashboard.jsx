import { Link } from 'react-router-dom';
import { ArrowUpRight, Boxes, Car, Leaf, Route, Users, Download, Navigation } from 'lucide-react';
import {
  usePolling, PageHeader, RefreshButton, ErrorNotice, Loading, Metric, ActivityChart, TripList, amount, formatDate,
} from '../../components/Operations';

function signed(value) {
  if (value == null) return '—';
  return `${value > 0 ? '+' : ''}${amount(value)}`;
}

function FleetStrip({ data }) {
  return (
    <div className="op-metrics">
      <Metric
        lead
        label="Net CO₂ avoided"
        value={signed(data.co2_saved_kg)}
        unit="kg"
        note={`Modelled, vs the fastest route · ${data.comparable_trips} comparable trips`}
        icon={Leaf}
      />
      <Metric
        label="On the road now"
        value={data.active_trips}
        note={`${data.planned_trips} planned, not started`}
        icon={Navigation}
      />
      <Metric
        label="Completed trips"
        value={data.total_trips}
        note={`${data.total_vehicles} vehicles · ${data.total_drivers} approved drivers`}
        icon={Route}
      />
      <Metric
        label="Distance driven"
        value={amount(data.distance_km)}
        unit="km"
        note="Selected routes of comparable trips"
        icon={Car}
      />
    </div>
  );
}

function ActionLink({ to, icon: Icon, title, text }) {
  return (
    <Link className="op-action-row" to={to}>
      <div className="op-route-icon"><Icon size={18} /></div>
      <div>
        <strong>{title}</strong>
        <p>{text}</p>
      </div>
      <ArrowUpRight size={17} />
    </Link>
  );
}

export default function AdminDashboard() {
  const { data, error, loading, reload } = usePolling('/admin/stats');
  const rounds = usePolling('/rounds');
  const roundList = rounds.data?.rounds || [];
  const roundsOnRoad = roundList.filter((round) => round.status === 'in_progress').length;
  const roundsWaiting = roundList.filter((round) => round.status === 'planned').length;

  return (
    <div className="op-page">
      <PageHeader
        eyebrow="Admin · overview"
        title="Fleet overview"
        description="Your whole fleet at a glance. Updates every 15 seconds."
        action={<RefreshButton onClick={reload} />}
      />
      <Link className="pub-btn pub-btn-primary" to="/admin/fleet-map">Run 25-vehicle simulation →</Link>
      <ErrorNotice>{error && `${error} Displayed data may be out of date.`}</ErrorNotice>

      {loading ? <Loading /> : data && (
        <>
          <FleetStrip data={data} />

          <div className="op-columns">
            <section className="op-panel">
              <div className="op-panel-heading">
                <div>
                  <h2>Completed trips, last 7 days</h2>
                  <p>Trips with a saved route comparison · UTC days</p>
                </div>
                <span className={`op-live ${error ? 'stale' : ''}`}>
                  <i />{error ? 'Connection lost' : 'Live'}
                </span>
              </div>
              <ActivityChart days={data.daily} />
            </section>

            <section className="op-panel">
              <div className="op-panel-heading"><h2>Needs attention</h2></div>
              <ActionLink
                to="/admin/fleet-map"
                icon={Navigation}
                title={`${data.active_trips} trip${data.active_trips === 1 ? '' : 's'} on the road`}
                text="Last GPS position and route on the live map"
              />
              <ActionLink
                to="/admin/rounds"
                icon={Boxes}
                title={`${roundsOnRoad} round${roundsOnRoad === 1 ? '' : 's'} on the road · ${roundsWaiting} waiting`}
                text="Plan a round and send it to a driver"
              />
              <ActionLink
                to="/admin/approvals"
                icon={Users}
                title={`${data.pending_approvals} driver approval${data.pending_approvals === 1 ? '' : 's'}`}
                text="Approve or reject new driver accounts"
              />
              <ActionLink to="/admin/vehicles" icon={Car} title="Vehicle assignments" text="Assign vehicles to approved drivers" />
              <ActionLink to="/admin/reports" icon={Download} title="Fleet report" text="Excel and PDF of completed trips" />
            </section>
          </div>

          <section className="op-panel">
            <div className="op-panel-heading">
              <div>
                <h2>Latest trips</h2>
                <p>Planned, active and completed, newest first</p>
              </div>
            </div>
            <TripList trips={data.recent_trips} />
          </section>

          <footer className="op-footer">
            <span>Updated {formatDate(data.updated_at)}</span>
            <span>Savings are estimates compared with the fastest road, not measured.</span>
          </footer>
        </>
      )}
    </div>
  );
}
