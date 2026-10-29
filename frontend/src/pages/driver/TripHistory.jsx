import { Link } from 'react-router-dom';
import { usePolling, PageHeader, ErrorNotice, Loading, TripList, RefreshButton } from '../../components/Operations';

export default function TripHistory() {
  const { data, error, loading, reload } = usePolling('/trips/history');

  return (
    <div className="op-page">
      <PageHeader
        eyebrow="Driver · history"
        title="Trip history"
        description="Your last 100 trips."
        action={<RefreshButton onClick={reload} />}
      />
      <ErrorNotice>{error}</ErrorNotice>

      {loading ? <Loading /> : (
        <section className="op-panel">
          <div className="op-panel-heading">
            <h2>All trips</h2>
            <Link className="op-button" to="/driver/new-trip">Plan a trip</Link>
          </div>
          <TripList trips={data?.trips} driver />
        </section>
      )}
    </div>
  );
}
