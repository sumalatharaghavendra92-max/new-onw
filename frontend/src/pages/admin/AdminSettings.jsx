import React, { useState, useEffect } from 'react';
import { Save, Database, HardDrive, Loader } from 'lucide-react';
import Card from '../../components/Card';
import Button from '../../components/Button';
import api from '../../api/api';
import { PageHeader, Loading } from '../../components/Operations';

export default function AdminSettings() {
  const [settings, setSettings] = useState({
    auto_approve_drivers: false,
    strict_routing: true,
    ml_retrain_interval_days: 7
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState('');

  useEffect(() => {
    api.get('/admin/settings').then(res => {
      setSettings(res.data);
      setLoading(false);
    });
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.patch('/admin/settings', settings);
      setNotice('Settings saved.');
    } catch {
      setNotice('Settings could not be saved. Try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleAction = async (action) => {
    try {
      if (action === 'backup') {
        const res = await api.post('/admin/backup', {}, {responseType: 'blob'});
        const url = URL.createObjectURL(res.data);
        const link = document.createElement('a'); link.href = url; link.download = 'gogreen-backup.db'; link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        setNotice('Database backup downloaded. Keep it private; it contains account information.');
      } else {
        setNotice('Stop the backend and follow the restore instructions in SETUP_EXPO.md.');
      }
    } catch {
      setNotice(`The ${action} request failed.`);
    }
  };

  if (loading) return <Loading />;

  return (
    <div className="op-page">
      <PageHeader
        eyebrow="Admin · settings"
        title="Settings"
        description="Settings are saved in your database. Manual approval is recommended."
      />
      {notice && <p className="op-success" role="status">{notice}</p>}

      <Card className="flex flex-col gap-6">
        <h2>Business rules</h2>
        
        <div className="flex items-center justify-between">
          <div>
            <p className="font-medium text-sm text-neutral-textMain">Auto-approve drivers</p>
            <p className="text-xs text-neutral-textMuted">Automatically approve new driver registrations</p>
          </div>
          <input type="checkbox" className="w-5 h-5 rounded border-neutral-border accent-[#1b6a45]" 
            checked={settings.auto_approve_drivers} 
            onChange={e => setSettings({...settings, auto_approve_drivers: e.target.checked})} />
        </div>

        <div className="flex items-center justify-between">
          <div>
            <p className="font-medium text-sm text-neutral-textMain">Strict routing</p>
            <p className="text-xs text-neutral-textMuted">Stored fleet preference; automatic enforcement is not implemented.</p>
          </div>
          <input type="checkbox" className="w-5 h-5 rounded border-neutral-border accent-[#1b6a45]" 
            checked={settings.strict_routing} 
            onChange={e => setSettings({...settings, strict_routing: e.target.checked})} />
        </div>

        <div className="flex items-center justify-between">
          <div>
            <p className="font-medium text-sm text-neutral-textMain">Calibration review interval (days)</p>
            <p className="text-xs text-neutral-textMuted">Review reminder preference; no automatic retraining is scheduled.</p>
          </div>
          <input type="number" className="op-input w-24" 
            value={settings.ml_retrain_interval_days} 
            onChange={e => setSettings({...settings, ml_retrain_interval_days: parseInt(e.target.value)})} />
        </div>

        <div className="pt-4 flex justify-end">
          <Button variant="primary" onClick={handleSave} disabled={saving}>
            {saving ? <Loader size={16} className="animate-spin" /> : <><Save size={16} className="mr-2"/> Save settings</>}
          </Button>
        </div>
      </Card>

      <Card className="flex flex-col gap-6">
        <h2>Data management</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="p-4 rounded-lg" style={{ background: 'var(--gg-paper)' }}>
            <h3 className="font-semibold text-sm mb-1">Back up database</h3>
            <p className="op-note mb-4">Create a manual snapshot of the current database state.</p>
            <Button variant="outline" className="w-full text-sm" onClick={() => handleAction('backup')}>
              <HardDrive size={14} className="mr-2"/> Start backup
            </Button>
          </div>
          <div className="p-4 rounded-lg" style={{ background: 'var(--gg-risk-tint)' }}>
            <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--gg-risk)' }}>Restore database</h3>
            <p className="op-note mb-4">Restore from the latest available snapshot. This will overwrite current data.</p>
            <Button variant="danger" className="w-full" onClick={() => handleAction('restore')}>
              <Database size={14} className="mr-2"/> Start restore
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
