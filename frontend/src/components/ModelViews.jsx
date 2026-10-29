import { Empty, amount, formatDate } from './Operations';

// The five ways a vehicle spends energy in the physics model, plus energy
// recovered by regenerative braking (electric vehicles only).
export const BREAKDOWN_PARTS = [
  { key: 'rolling', label: 'Rolling resistance', color: 'var(--gg-roll)' },
  { key: 'aero', label: 'Air drag', color: 'var(--gg-aero)' },
  { key: 'grade', label: 'Climbing', color: 'var(--gg-grade)' },
  { key: 'stops', label: 'Turns and stops', color: 'var(--gg-stops)' },
  { key: 'auxiliary', label: 'Accessories and AC', color: 'var(--gg-aux)' },
];

export function fuelText(quantity, unit) {
  return `${amount(quantity)} ${unit || 'L'}`;
}

// Total positive CO2 across all parts; used to scale several bars to one axis.
export function breakdownTotal(breakdown) {
  if (!breakdown) return 0;
  return BREAKDOWN_PARTS.reduce((sum, part) => sum + Math.max(0, breakdown[part.key] || 0), 0);
}

/**
 * Stacked horizontal bar of CO2 (kg) by cause.
 * scaleMax lets a list of routes share one axis so their lengths compare.
 */
export function BreakdownBar({ breakdown, scaleMax }) {
  if (!breakdown) return null;
  const total = breakdownTotal(breakdown);
  const max = scaleMax || total || 1;
  const recovered = Math.abs(Math.min(0, breakdown.regen || 0));
  const description = BREAKDOWN_PARTS
    .map((part) => `${part.label} ${amount(breakdown[part.key])} kg`)
    .join(', ');

  return (
    <div>
      <div className="op-breakdown" role="img" aria-label={`CO2 by cause: ${description}`} style={{ width: `${(total / max) * 100}%` }}>
        {BREAKDOWN_PARTS.map((part) => {
          const value = Math.max(0, breakdown[part.key] || 0);
          if (!value) return null;
          return (
            <span
              key={part.key}
              title={`${part.label}: ${amount(value)} kg CO₂`}
              style={{ width: `${(value / total) * 100}%`, background: part.color }}
            />
          );
        })}
      </div>
      {recovered > 0 && (
        <p className="op-note">−{amount(recovered)} kg recovered by regenerative braking</p>
      )}
    </div>
  );
}

export function BreakdownLegend() {
  return (
    <div className="op-legend">
      {BREAKDOWN_PARTS.map((part) => (
        <span key={part.key}>
          <i style={{ background: part.color }} />
          {part.label}
        </span>
      ))}
    </div>
  );
}

// Per-vehicle correction factors learned from driver-reported fuel.
export function CalibrationTable({ rows = [] }) {
  if (!rows.length) {
    return <Empty title="No calibrated vehicles yet">Every trip with reported fuel teaches the app about that vehicle.</Empty>;
  }
  return (
    <div className="op-table-wrap">
      <table className="op-table">
        <thead>
          <tr><th>Vehicle</th><th>Class · fuel</th><th>Trips</th><th>Factor</th><th>Uncertainty</th><th>Updated</th></tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.vehicle_no}>
              <td>{row.vehicle_no}</td>
              <td>{row.class} · {row.fuel}</td>
              <td>{row.trips}</td>
              <td>× {Number(row.factor).toFixed(2)}</td>
              <td>± {amount(row.uncertainty_pct)}%</td>
              <td>{formatDate(row.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
