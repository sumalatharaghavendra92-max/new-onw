import React, { useState, useEffect } from 'react';
import { CheckCircle, XCircle, User, Loader } from 'lucide-react';
import Button from '../../components/Button';
import Card from '../../components/Card';
import Modal from '../../components/Modal';
import api from '../../api/api';
import { PageHeader, ErrorNotice, Loading, Empty } from '../../components/Operations';

// Approval status mapped onto the shared status chips.
const STATUS_CHIP = { pending: 'planned', approved: 'in_progress', rejected: 'cancelled', blocked: '' };

export default function DriverApprovals() {
  const [drivers, setDrivers] = useState([]);
  const [filter, setFilter] = useState('pending');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(null);
  const [rejectReason, setRejectReason] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState('');

  const fetchDrivers = async () => {
    setLoading(true); setError('');
    try {
      const res = await api.get(`/drivers?status=${filter}`);
      setDrivers(res.data);
    } catch {
      setError('Failed to load drivers');
    } finally { setLoading(false); }
  };

  useEffect(() => { fetchDrivers(); }, [filter]);

  const handleAction = async (action) => {
    setActionLoading(true); setActionMsg('');
    try {
      await api.patch(`/drivers/${selected.id}/approval`, {
        action,
        reason: action === 'reject' ? rejectReason : undefined
      });
      setActionMsg(`Driver ${action}d successfully`);
      setSelected(null); setRejectReason('');
      fetchDrivers();
    } catch (err) {
      setActionMsg(err.response?.data?.message || `Failed to ${action}`);
    } finally { setActionLoading(false); }
  };

  return (
    <div className="op-page">
      <PageHeader
        eyebrow="Admin · driver approvals"
        title="Driver approvals"
        description="New drivers wait here. Approve them, then give them a vehicle."
      />
      {actionMsg && <p className="op-success" role="status">{actionMsg}</p>}

      <div className="op-segment" role="tablist" aria-label="Application status">
        {['pending', 'approved', 'rejected'].map((status) => (
          <button
            key={status}
            role="tab"
            aria-selected={filter === status}
            onClick={() => setFilter(status)}
            className={filter === status ? 'active' : ''}
          >
            {status}
          </button>
        ))}
      </div>

      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorNotice>{error}</ErrorNotice>
      ) : drivers.length === 0 ? (
        <Card><Empty title={`No ${filter} applications`}>Applications appear here as drivers register.</Empty></Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {drivers.map((driver) => (
            <Card key={driver.id} className="flex flex-col gap-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="op-route-icon"><User size={18} /></div>
                  <div className="min-w-0">
                    <p className="font-semibold truncate">{driver.name}</p>
                    <p className="op-note truncate">{driver.email}</p>
                  </div>
                </div>
                <span className={`op-status ${STATUS_CHIP[driver.approval_status] || ''}`}>{driver.approval_status}</span>
              </div>

              <dl className="grid grid-cols-2 gap-2 text-sm">
                <div><dt className="op-note">Licence</dt><dd className="op-num">{driver.license_no || '—'}</dd></div>
                <div><dt className="op-note">Experience</dt><dd className="op-num">{driver.experience_years || 0} yrs</dd></div>
              </dl>

              {driver.rejection_reason && (
                <p className="op-error">Rejected: {driver.rejection_reason}</p>
              )}

              {driver.approval_status === 'pending' && (
                <Button variant="outline" className="w-full" onClick={() => setSelected(driver)}>Review application</Button>
              )}
            </Card>
          ))}
        </div>
      )}

      {/* Review Modal */}
      <Modal isOpen={!!selected} onClose={() => { setSelected(null); setRejectReason(''); }} title="Review application">
        {selected && (
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div><span className="op-note">Name</span><p className="font-medium">{selected.name}</p></div>
              <div><span className="op-note">Email</span><p className="font-medium op-num">{selected.email}</p></div>
              <div><span className="op-note">Phone</span><p className="font-medium op-num">{selected.phone || 'N/A'}</p></div>
              <div><span className="op-note">Licence</span><p className="font-medium op-num">{selected.license_no || 'N/A'}</p></div>
              <div><span className="op-note">Experience</span><p className="font-medium op-num">{selected.experience_years || 0} yrs</p></div>
            </div>

            <hr className="border-neutral-border" />

            <div>
              <label className="block text-sm font-semibold" htmlFor="reject-reason">
                Reason for rejection <span className="op-note font-normal">(required to reject)</span>
              </label>
              <textarea id="reject-reason" rows={3} className="op-input resize-none"
                placeholder="Tell the driver what is missing"
                value={rejectReason} onChange={e => setRejectReason(e.target.value)} />
            </div>

            <div className="flex gap-3">
              <Button variant="danger" className="flex-1" disabled={actionLoading || !rejectReason.trim()}
                onClick={() => handleAction('reject')}>
                {actionLoading ? <Loader className="animate-spin" size={16} /> : <><XCircle size={16} /> Reject</>}
              </Button>
              <Button variant="primary" className="flex-1" disabled={actionLoading}
                onClick={() => handleAction('approve')}>
                {actionLoading ? <Loader className="animate-spin" size={16} /> : <><CheckCircle size={16} /> Approve</>}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
