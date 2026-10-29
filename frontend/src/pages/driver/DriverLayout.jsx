import { useEffect } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { LayoutDashboard, Plus, History, Bell, User, LogOut } from 'lucide-react';
import { usePolling } from '../../components/Operations';
import '../../components/operations.css';

const NAV = [
  { label: 'Home', to: '/driver', icon: LayoutDashboard },
  { label: 'Plan a trip', to: '/driver/new-trip', icon: Plus },
  { label: 'History', to: '/driver/history', icon: History },
  { label: 'Notifications', to: '/driver/notifications', icon: Bell },
  { label: 'Profile', to: '/driver/profile', icon: User },
];

export default function DriverLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { data: notifications, reload: reloadNotifications } = usePolling('/notifications', 30000);
  useEffect(() => {
    window.addEventListener('gg:notifications-read', reloadNotifications);
    return () => window.removeEventListener('gg:notifications-read', reloadNotifications);
  }, [reloadNotifications]);
  const unread = (notifications || []).filter((item) => !item.is_read).length;
  const badge = (to) => (to === '/driver/notifications' && unread ? <b className="gg-badge">{unread}</b> : null);
  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-neutral-bg flex flex-col">
      {/* Top bar (desktop) */}
      <header className="hidden md:flex items-center justify-between px-8 bg-white border-b border-neutral-border sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <span className="gg-sign-mark" aria-hidden="true">G</span>
          <span className="gg-wordmark" style={{ color: 'var(--gg-sign-deep)' }}>GoGreen</span>
        </div>
        <nav className="flex items-center gap-6" aria-label="Driver">
          {NAV.map(({ label, to, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/driver'}
              className={({ isActive }) => `gg-top-link ${isActive ? 'active' : ''}`}
            >
              <Icon size={15} />
              {label}
              {badge(to)}
            </NavLink>
          ))}
        </nav>
        <div className="flex items-center gap-3">
          <span className="text-sm text-neutral-textMuted">{user?.name}</span>
          <button aria-label="Log out" onClick={handleLogout} className="op-icon-button">
            <LogOut size={18} />
          </button>
        </div>
      </header>

      <main className="flex-1 px-4 py-6 md:px-8 pb-24 md:pb-8">

        <Outlet />
      </main>

      {/* Bottom tab bar (mobile) */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-neutral-border flex justify-around py-2 z-10" aria-label="Driver">
        {NAV.map(({ label, to, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/driver'}
            className={({ isActive }) =>
              `flex flex-col items-center gap-0.5 text-xs font-medium ${isActive ? 'text-primary' : 'text-neutral-textMuted'}`
            }
          >
            <span className="relative">
              <Icon size={20} />
              {badge(to)}
            </span>
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
