import { Bell } from 'lucide-react';
import api from '../../api/api';
import { usePolling, PageHeader, ErrorNotice, Loading, Empty, formatDate } from '../../components/Operations';

export default function Notifications() {
  const { data, error, loading, reload } = usePolling('/notifications', 30000);
  const items = data || [];

  async function markRead(item) {
    if (item.is_read) return;
    try {
      await api.patch(`/notifications/${item.id}/read`);
    } finally {
      reload();
      window.dispatchEvent(new Event('gg:notifications-read')); // lets the nav badge update now
    }
  }

  return (
    <div className="op-page">
      <PageHeader
        eyebrow="Driver"
        title="Notifications"
        description="Messages from your admin. Tap one to mark it as read."
      />
      <ErrorNotice>{error}</ErrorNotice>

      {loading ? <Loading /> : (
        <section className="op-panel">
          {!items.length ? (
            <Empty title="No messages yet">New rounds and approvals show up here.</Empty>
          ) : (
            <ul className="gg-notifications">
              {items.map((item) => (
                <li key={item.id}>
                  <button className={item.is_read ? '' : 'unread'} onClick={() => markRead(item)}>
                    <span className="op-route-icon"><Bell size={17} /></span>
                    <span className="gg-notification-text">
                      <strong>{item.title}</strong>
                      <span>{item.message}</span>
                    </span>
                    <span className="op-num gg-notification-time">{formatDate(item.created_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
