import { Link } from 'react-router-dom';
import './public.css';

// The GoGreen mark: a small highway-sign plate with a "G".
export function BrandMark({ onDark = false, size = 'md' }) {
  const box = size === 'lg' ? 'w-11 h-11' : 'w-9 h-9';
  const text = size === 'lg' ? 'text-3xl' : 'text-2xl';
  return (
    <Link to="/" className="inline-flex items-center gap-2.5" aria-label="GoGreen home">
      <svg viewBox="0 0 64 64" className={box} aria-hidden="true">
        <rect width="64" height="64" rx="14" style={{ fill: onDark ? '#ffffff' : 'var(--gg-sign)' }} />
        <rect x="5" y="5" width="54" height="54" rx="10" fill="none" strokeWidth="3"
              style={{ stroke: onDark ? 'var(--gg-sign-deep)' : '#ffffff' }} />
        <path d="M43 24a13 13 0 1 0 1 13H33" fill="none" strokeWidth="6"
              strokeLinecap="round" strokeLinejoin="round"
              style={{ stroke: onDark ? 'var(--gg-sign-deep)' : '#ffffff' }} />
      </svg>
      <span className={`font-display font-bold tracking-wide ${text} ${onDark ? 'text-white' : 'text-[color:var(--gg-ink)]'}`}>
        GoGreen
      </span>
    </Link>
  );
}

// Split layout for sign-in and registration: a sign panel on the left, the form on the right.
// On phones the sign shrinks to a compact header above the form.
export function AuthShell({ sign, children }) {
  return (
    <div className="pub-contours min-h-[100dvh] grid lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
      <aside className="p-3 lg:p-5">
        <div className="pub-sign h-full">
          <div className="pub-sign-inner flex flex-col justify-between gap-8 px-6 py-6 lg:px-10 lg:py-10">
            <BrandMark onDark />
            {sign}
          </div>
        </div>
      </aside>
      <main className="flex items-center justify-center px-5 py-10 lg:px-12">
        <div className="w-full max-w-[440px]">{children}</div>
      </main>
    </div>
  );
}

// Label + input pair used by both forms.
export function Field({ label, hint, id, className = '', ...inputProps }) {
  return (
    <div className={className}>
      <label htmlFor={id} className="pub-label">{label}</label>
      <input id={id} className="pub-input" {...inputProps} />
      {hint && <p className="mt-1.5 text-xs text-[color:var(--gg-muted)]">{hint}</p>}
    </div>
  );
}

// Barlow Condensed has no subscript-two glyph, so headings set the 2 themselves.
export function CO2() {
  return <>CO<sub className="font-sans text-[0.5em] font-semibold" style={{ verticalAlign: '-0.05em' }}>2</sub></>;
}
