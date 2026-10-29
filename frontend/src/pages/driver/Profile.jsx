import { useNavigate } from 'react-router-dom';
import { LogOut } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { usePolling, PageHeader, ErrorNotice, Loading, Status, amount } from '../../components/Operations';

export default function Profile() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const { data: me, error, loading } = usePolling('/drivers/me', 60000);
  const history = usePolling('/trips/history', 60000);

  // Eco score of the latest finished trip (50 = typical for the vehicle type).
  const lastScored = (history.data?.trips || []).find((trip) => trip.status === 'completed' && trip.selectedRoute?.ecoScore != null);

  function signOut() {
    logout();
    navigate('/login');
  }

  return (
    <div className="op-page">
      <PageHeader
        eyebrow="Driver"
        title="Profile"
        description="Your account and the vehicle you drive."
        action={<button className="op-button secondary" onClick={signOut}><LogOut size={16} /> Log out</button>}
      />
      <ErrorNotice>{error}</ErrorNotice>

      {loading ? <Loading /> : me && (
        <div className="op-columns">
          <section className="op-panel">
            <div className="op-panel-heading">
              <h2>{me.name}</h2>
              <Status status={me.approval_status} />
            </div>
            <dl className="gg-facts">
              <div><dt>Email</dt><dd>{me.email}</dd></div>
              <div><dt>Phone</dt><dd className="op-num">{me.phone}</dd></div>
              <div><dt>Licence</dt><dd className="op-num">{me.license_no || '—'}</dd></div>
              <div><dt>Experience</dt><dd>{me.experience_years != null ? `${me.experience_years} years` : '—'}</dd></div>
              <div><dt>Latest eco score</dt><dd className="op-num">{lastScored ? amount(lastScored.selectedRoute.ecoScore) : '—'}</dd></div>
            </dl>
            <p className="op-note">Eco score: 50 is normal for your vehicle type. Higher is greener.</p>
          </section>

          <section className="op-panel">
            <h2>Vehicle</h2>
            {me.vehicle ? (
              <>
                <p className="gg-plate">{me.vehicle.vehicle_no}</p>
                <dl className="gg-facts">
                  <div><dt>Type</dt><dd className="cap">{me.vehicle.type}</dd></div>
                  <div><dt>Fuel</dt><dd className="cap">{me.vehicle.fuel_type}</dd></div>
                  <div><dt>Capacity</dt><dd className="op-num">{amount(me.vehicle.load_capacity_kg)} kg</dd></div>
                  <div><dt>Status</dt><dd className="cap">{me.vehicle.status}</dd></div>
                </dl>
              </>
            ) : (
              <p className="op-description">No vehicle yet. Ask your admin to assign one.</p>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
