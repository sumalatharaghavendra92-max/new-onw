import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';

// Public pages
import Landing from './pages/public/Landing';
import Login from './pages/public/Login';
import Register from './pages/public/Register';

// Admin pages
import AdminLayout from './pages/admin/AdminLayout';
import AdminDashboard from './pages/admin/AdminDashboard';
import DriverApprovals from './pages/admin/DriverApprovals';
import VehicleManagement from './pages/admin/VehicleManagement';
import LiveFleetMap from './pages/admin/LiveFleetMap';
import Sustainability from './pages/admin/Sustainability';
import ModelLab from './pages/admin/ModelLab';
import RoundPlanner from './pages/admin/RoundPlanner';
import AdminSettings from './pages/admin/AdminSettings';
import Reports from './pages/admin/Reports';
import Learning from './pages/admin/Learning';

// Driver pages
import DriverLayout from './pages/driver/DriverLayout';
import DriverDashboard from './pages/driver/DriverDashboard';

import NewTrip from './pages/driver/NewTrip';

import ActiveTrip from './pages/driver/ActiveTrip';
import TripHistory from './pages/driver/TripHistory';
import Notifications from './pages/driver/Notifications';
import Profile from './pages/driver/Profile';

// ── Route Guards ──────────────────────────────────────────────────────────────

function ProtectedRoute({ children, allowedRoles }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-neutral-bg">
        <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to={user.role === 'admin' ? '/admin' : '/driver'} replace />;
  }
  return children;
}

// Redirect logged-in users away from public login/register
function PublicOnlyRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to={user.role === 'admin' ? '/admin' : '/driver'} replace />;
  return children;
}

// ── App ───────────────────────────────────────────────────────────────────────

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          {/* Public */}
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<PublicOnlyRoute><Login /></PublicOnlyRoute>} />
          <Route path="/register" element={<PublicOnlyRoute><Register /></PublicOnlyRoute>} />

          {/* Admin */}
          <Route path="/admin" element={<ProtectedRoute allowedRoles={['admin']}><AdminLayout /></ProtectedRoute>}>
            <Route index element={<AdminDashboard />} />
            <Route path="approvals" element={<DriverApprovals />} />
            <Route path="vehicles" element={<VehicleManagement />} />
            {/* Phase 5 pages */}
            <Route path="fleet-map" element={<LiveFleetMap />} />
            <Route path="rounds" element={<RoundPlanner />} />
            <Route path="sustainability" element={<Sustainability />} />
            <Route path="reports" element={<Reports />} />
            <Route path="learning" element={<Learning />} />
            <Route path="ai" element={<ModelLab />} />
            <Route path="settings" element={<AdminSettings />} />
          </Route>

          {/* Driver */}
          <Route path="/driver" element={<ProtectedRoute allowedRoles={['driver']}><DriverLayout /></ProtectedRoute>}>
            <Route index element={<DriverDashboard />} />
            <Route path="new-trip" element={<NewTrip />} />
            <Route path="active-trip/:id" element={<ActiveTrip />} />
            <Route path="history" element={<TripHistory />} />
            <Route path="notifications" element={<Notifications />} />
            <Route path="profile" element={<Profile />} />
          </Route>

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
