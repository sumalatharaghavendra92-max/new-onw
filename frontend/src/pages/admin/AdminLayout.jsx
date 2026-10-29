import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import {
  Leaf, LayoutDashboard, Users, Car, Map, BarChart2, FlaskConical, Route, Settings, LogOut,
  ChevronLeft, ChevronRight, FileDown,
} from 'lucide-react';
import '../../components/operations.css';

// Grouped like the work itself: running the fleet, then judging its emissions.
const NAV_GROUPS = [
  {
    title: 'Operations',
    items: [
      { label: 'Overview', to: '/admin', icon: LayoutDashboard },
      { label: 'Live fleet', to: '/admin/fleet-map', icon: Map },
      { label: 'Round planner', to: '/admin/rounds', icon: Route },
      { label: 'Vehicles', to: '/admin/vehicles', icon: Car },
      { label: 'Driver approvals', to: '/admin/approvals', icon: Users },
    ],
  },
  {
    title: 'Emissions and model',
    items: [
      { label: 'Emissions', to: '/admin/sustainability', icon: Leaf },
      { label: 'Evidence and feedback', to: '/admin/learning', icon: BarChart2 },
      { label: 'Model lab', to: '/admin/ai', icon: FlaskConical },
      { label: 'Reports', to: '/admin/reports', icon: FileDown },
    ],
  },
  {
    title: 'Simulation',
    items: [
    ],
  },
];

function NavItem({ item, collapsed }) {
  const Icon = item.icon;
  return (
    <NavLink
      title={item.label}
      to={item.to}
      end={item.to === '/admin'}
      className={({ isActive }) => `gg-nav-link ${isActive ? 'active' : ''}`}
    >
      <Icon size={17} className="flex-shrink-0" />
      {!collapsed && <span className="hidden md:inline truncate">{item.label}</span>}
    </NavLink>
  );
}

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="flex min-h-screen bg-neutral-bg">
      <aside
        className={`sticky top-0 h-screen self-start flex flex-col text-white transition-all duration-300 flex-shrink-0 z-20 ${
          collapsed ? 'w-16' : 'w-16 md:w-64'
        }`}
        style={{ background: 'var(--gg-sign-deep)' }}
      >
        <div className="flex items-center gap-3 px-4 py-5 border-b border-white/10 overflow-hidden">
          <span className="gg-sign-mark" aria-hidden="true">G</span>
          {!collapsed && <span className="hidden md:inline gg-wordmark">GoGreen</span>}
        </div>

        <nav className="flex-1 py-2 px-3 overflow-y-auto" aria-label="Admin">
          {NAV_GROUPS.map((group) => (
            <div key={group.title}>
              {!collapsed && <p className="gg-nav-group hidden md:block">{group.title}</p>}
              <div className="flex flex-col gap-0.5">
                {group.items.map((item) => <NavItem key={item.to} item={item} collapsed={collapsed} />)}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-white/10 px-3 py-3 flex flex-col gap-0.5">
          <NavItem item={{ label: 'Settings', to: '/admin/settings', icon: Settings }} collapsed={collapsed} />
          <button onClick={handleLogout} className="gg-nav-link w-full" title="Log out">
            <LogOut size={17} className="flex-shrink-0" />
            {!collapsed && <span className="hidden md:inline truncate">Log out</span>}
          </button>
          {!collapsed && (
            <p className="hidden md:block px-3 pt-2 text-xs text-white/50 truncate">
              {user?.name || user?.email || 'Administrator'}
            </p>
          )}
        </div>

        <button
          onClick={() => setCollapsed((value) => !value)}
          className="absolute bottom-24 -right-3 w-6 h-6 rounded-full border border-white/20 flex items-center justify-center text-white/70 hover:text-white z-30"
          style={{ background: 'var(--gg-sign-deep)' }}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
        </button>
      </aside>

      <main className="flex-1 min-w-0 overflow-y-auto px-4 py-6 md:px-8 lg:px-10">

        <Outlet />
      </main>
    </div>
  );
}
