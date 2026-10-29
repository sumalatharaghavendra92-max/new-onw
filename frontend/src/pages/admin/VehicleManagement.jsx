import React, { useState, useEffect } from 'react';
import { Plus, Pencil, Trash2, Loader } from 'lucide-react';
import Button from '../../components/Button';
import Card from '../../components/Card';
import Modal from '../../components/Modal';
import api from '../../api/api';
import { PageHeader, ErrorNotice, Loading, Empty } from '../../components/Operations';

const EMPTY_FORM = { vehicle_no: '', type: '', fuel_type: 'Diesel', load_capacity_kg: 1000, emission_factor_g_per_km: 120, assigned_driver_id: '', status: 'active' };
const FUEL_TYPES = ['Diesel', 'Petrol', 'Electric', 'Hybrid', 'CNG'];
const STATUSES = ['active', 'maintenance', 'retired'];

export default function VehicleManagement() {
  const [vehicles, setVehicles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editVehicle, setEditVehicle] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');
  const [readingVehicle, setReadingVehicle] = useState(null);
  const [reading, setReading] = useState({fuel_percent: '', load_kg: '', odometer_km: ''});

  const set = (f) => (e) => setForm(v => ({ ...v, [f]: e.target.value }));

  const fetchVehicles = async () => {
    setLoading(true); setError('');
    try {
      const res = await api.get('/vehicles');
      setVehicles(res.data);
    } catch { setError('Failed to load vehicles'); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchVehicles(); }, []);

  const openCreate = () => { setForm(EMPTY_FORM); setEditVehicle(null); setShowModal(true); setMsg(''); };
  const openEdit = (v) => {
    setForm({ vehicle_no: v.vehicle_no, type: v.type, fuel_type: v.fuel_type, load_capacity_kg: v.load_capacity_kg, emission_factor_g_per_km: v.emission_factor_g_per_km, assigned_driver_id: v.assigned_driver_id || '', status: v.status });
    setEditVehicle(v); setShowModal(true); setMsg('');
  };

  const handleSave = async (e) => {
    e.preventDefault(); setSaving(true); setMsg('');
    try {
      if (editVehicle) {
        await api.patch(`/vehicles/${editVehicle.id}`, { ...form, assigned_driver_id: form.assigned_driver_id || null });
      } else {
        await api.post('/vehicles', { ...form, assigned_driver_id: form.assigned_driver_id || null });
      }
      setShowModal(false); fetchVehicles(); setMsg(editVehicle ? 'Vehicle updated' : 'Vehicle created');
    } catch (err) { setMsg(err.response?.data?.message || 'Operation failed'); }
    finally { setSaving(false); }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this vehicle?')) return;
    try {
      await api.delete(`/vehicles/${id}`);
      fetchVehicles(); setMsg('Vehicle deleted');
    } catch { setMsg('Failed to delete vehicle'); }
  };

  const inputClass = 'op-input';
  const labelClass = 'block text-xs font-semibold text-neutral-textMain';

  // Map vehicle status onto the shared status chips.
  const STATUS_CHIP = { active: 'in_progress', maintenance: 'planned', retired: '' };

  return (
    <div className="op-page">
      <PageHeader
        eyebrow="Admin · vehicles"
        title="Vehicles"
        description="Fleet inventory. SAMPLE plates and sample readings are fictional. Manual readings show their recording time; live GPS is available during active trips."
        action={<Button variant="primary" onClick={openCreate}><Plus size={16} />Add vehicle</Button>}
      />
      {msg && !showModal && <p className="op-success" role="status">{msg}</p>}

      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorNotice>{error}</ErrorNotice>
      ) : vehicles.length === 0 ? (
        <Card>
          <Empty title="No vehicles yet">Add a vehicle and give it to a driver.</Empty>
        </Card>
      ) : (
        <Card className="flush">
          <div className="op-table-wrap">
            <table className="op-table">
              <thead>
                <tr>
                  {['Plate', 'Type', 'Fuel', 'Capacity kg', 'Factor g/km', 'Fuel / battery %', 'Load kg', 'Odometer km', 'Reading source', 'Driver', 'Status', ''].map((heading) => (
                    <th key={heading}>{heading}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {vehicles.map((v) => (
                  <tr key={v.id}>
                    <td className="op-num font-semibold">{v.vehicle_no}</td>
                    <td>{v.type}</td>
                    <td>{v.fuel_type}</td>
                    <td>{v.load_capacity_kg?.toLocaleString()}</td>
                    <td>{v.emission_factor_g_per_km ?? '—'}</td>
                    <td>{v.reading?.fuel_percent ?? '—'}</td>
                    <td>{v.reading?.load_kg ?? '—'}</td>
                    <td>{v.reading?.odometer_km ?? '—'}</td>
                    <td>{v.reading?.source === 'sample' ? 'Sample · not live' : v.reading ? `Manual · ${new Date(v.reading.recorded_at).toLocaleString()}` : 'No readings'}</td>
                    <td>{v.assigned_driver_name || '—'}</td>
                    <td><span className={`op-status ${STATUS_CHIP[v.status] || ''}`}>{v.status}</span></td>
                    <td>
                      <div className="flex gap-1 justify-end">
                        <button className="op-icon-button" onClick={() => { setReadingVehicle(v); setReading({fuel_percent: v.reading?.fuel_percent ?? '', load_kg: v.reading?.load_kg ?? '', odometer_km: v.reading?.odometer_km ?? ''}); setMsg(''); }}>Record reading</button>
                        <button onClick={() => openEdit(v)} className="op-icon-button" aria-label={`Edit ${v.vehicle_no}`}><Pencil size={15} /></button>
                        <button onClick={() => handleDelete(v.id)} className="op-icon-button" aria-label={`Delete ${v.vehicle_no}`}><Trash2 size={15} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Modal isOpen={!!readingVehicle} onClose={() => setReadingVehicle(null)} title={`Record reading · ${readingVehicle?.vehicle_no || ''}`}>
        <form className="grid gap-4" onSubmit={async (e) => {
          e.preventDefault(); setSaving(true);
          try { await api.put(`/vehicles/${readingVehicle.id}/reading`, reading); setReadingVehicle(null); setMsg('Manual reading saved.'); fetchVehicles(); }
          catch (err) { setMsg(err.response?.data?.message || 'Could not save reading.'); }
          finally { setSaving(false); }
        }}>
          <p>Enter readings observed on the vehicle. This records a manual update, not sensor telemetry.</p>
          {msg && <ErrorNotice>{msg}</ErrorNotice>}
          {[['fuel_percent', 'Fuel / battery (%)', 100], ['load_kg', 'Current load (kg)', readingVehicle?.load_capacity_kg], ['odometer_km', 'Odometer (km)', undefined]].map(([key, label, max]) => (
            <label key={key}>{label}<input className="op-input" type="number" min="0" max={max} step="0.1" required value={reading[key]} onChange={(e) => setReading({...reading, [key]: e.target.value})} /></label>
          ))}
          <Button type="submit" disabled={saving}>Save reading</Button>
        </form>
      </Modal>
      {/* Create / Edit Modal */}
      <Modal isOpen={showModal} onClose={() => setShowModal(false)} title={editVehicle ? 'Edit vehicle' : 'Add vehicle'}>
        <form onSubmit={handleSave} className="flex flex-col gap-4">
          {msg && <ErrorNotice>{msg}</ErrorNotice>}
          <div>
            <label className={labelClass}>Plate number</label>
            <input className={inputClass} value={form.vehicle_no} onChange={set('vehicle_no')} required disabled={!!editVehicle} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelClass}>Type</label>
              <input className={inputClass} placeholder="Van, truck, heavy truck" value={form.type} onChange={set('type')} required />
            </div>
            <div>
              <label className={labelClass}>Fuel</label>
              <select className={inputClass} value={form.fuel_type} onChange={set('fuel_type')}>
                {FUEL_TYPES.map(f => <option key={f}>{f}</option>)}
              </select>
            </div>
            <div>
              <label className={labelClass}>Load capacity (kg)</label>
              <input type="number" className={inputClass} value={form.load_capacity_kg} onChange={set('load_capacity_kg')} />
            </div>
            <div>
              <label className={labelClass}>Legacy emission factor (g/km)</label>
              <input type="number" className={inputClass} value={form.emission_factor_g_per_km} onChange={set('emission_factor_g_per_km')} />
            </div>
            <div>
              <label className={labelClass}>Driver ID (optional)</label>
              <input type="number" className={inputClass} placeholder="Driver ID" value={form.assigned_driver_id} onChange={set('assigned_driver_id')} />
            </div>
            {editVehicle && (
              <div>
                <label className={labelClass}>Status</label>
                <select className={inputClass} value={form.status} onChange={set('status')}>
                  {STATUSES.map(s => <option key={s}>{s}</option>)}
                </select>
              </div>
            )}
          </div>
          <div className="flex gap-3 mt-2">
            <Button type="button" variant="ghost" className="flex-1" onClick={() => setShowModal(false)}>Cancel</Button>
            <Button type="submit" variant="primary" className="flex-1" disabled={saving}>
              {saving ? <Loader className="animate-spin" size={16} /> : editVehicle ? 'Save changes' : 'Create vehicle'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
