import { useState } from 'react';
import { FileSpreadsheet, FileText, Download } from 'lucide-react';
import api from '../../api/api';
import { PageHeader, ErrorNotice } from '../../components/Operations';

const REPORTS = [
  {
    type: 'excel',
    title: 'Trip workbook (.xlsx)',
    icon: FileSpreadsheet,
    description: 'One row per finished trip, with its road, times and fuel.',
  },
  {
    type: 'pdf',
    title: 'Fleet summary (.pdf)',
    icon: FileText,
    description: 'A short summary of finished trips and CO₂.',
  },
];

export default function Reports() {
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  async function download(type) {
    setBusy(type); setError('');
    try {
      const { data } = await api.get(`/reports/export/${type}`, { responseType: 'blob' });
      const url = URL.createObjectURL(data);
      const link = document.createElement('a');
      link.href = url; link.download = `gogreen-report.${type === 'excel' ? 'xlsx' : 'pdf'}`;
      document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch { setError('The report could not be downloaded. Check your connection and try again.'); }
    finally { setBusy(''); }
  }
  return (
    <div className="op-page">
      <PageHeader
        eyebrow="Admin · reports"
        title="Reports"
        description="Download finished trips. Predicted and reported fuel are in separate columns."
      />
      <ErrorNotice>{error}</ErrorNotice>
      <div className="op-columns">
        {REPORTS.map(({ type, title, icon: Icon, description }) => (
          <section className="op-panel op-stack" key={type}>
            <div className="op-route-icon"><Icon size={18} /></div>
            <h2>{title}</h2>
            <p className="op-description">{description}</p>
            <button onClick={() => download(type)} disabled={!!busy} className="op-button self-start">
              <Download size={16} />
              {busy === type ? 'Preparing report…' : `Download ${type === 'excel' ? 'Excel' : 'PDF'}`}
            </button>
          </section>
        ))}
      </div>
    </div>
  );
}
