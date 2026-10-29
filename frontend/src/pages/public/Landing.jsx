import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { BrandMark, CO2 } from './PublicKit';

// Every number on this page comes from a live run of the model on 23 Oct 2026
// (OSRM roads, Open-Meteo terrain and weather, 21.5 °C).
const HOSUR_ROUTES = [
  { name: 'Route A', km: 39.5, minutes: 45, climb: 233, co2: 18.3,
    parts: { rolling: 4.5, drag: 4.2, climbing: 5.4, turns: 2.7, accessories: 1.6 } },
  { name: 'Route B', km: 52.6, minutes: 51, climb: 307, co2: 29.1,
    parts: { rolling: 6.6, drag: 9.3, climbing: 7.1, turns: 4.3, accessories: 1.8 } },
];

const PART_STYLES = [
  { key: 'rolling', label: 'Rolling', className: 'pub-c-roll' },
  { key: 'drag', label: 'Air drag', className: 'pub-c-aero' },
  { key: 'climbing', label: 'Climbing', className: 'pub-c-grade' },
  { key: 'turns', label: 'Turns', className: 'pub-c-turns' },
  { key: 'accessories', label: 'AC & accessories', className: 'pub-c-aux' },
];

// Load on the truck (tonnes) for each leg of the live 5-stop Bengaluru round.
const ROUND_LOADS = {
  greenest: [6.5, 4.0, 3.7, 2.2, 0.4],
  fastest: [6.5, 6.1, 4.3, 2.8, 2.5],
};

const STEPS = [
  { source: 'OSRM', title: 'Real roads', text: 'We get 2–3 real roads, with their speed and turns.' },
  { source: 'Open-Meteo', title: 'Terrain and weather', text: 'We add the hills on the road and today’s weather.' },
  { source: 'Road-load physics', title: 'Fuel and CO₂', text: 'Physics turns tyres, wind, hills, turns and AC into fuel, then CO₂.' },
  { source: 'Your trips', title: 'Per-vehicle calibration', text: 'Drivers report fuel after each trip. The app learns each vehicle.' },
];

const SOURCES = [
  { name: 'OSRM', use: 'roads, speeds, turns' },
  { name: 'Open-Meteo', use: 'terrain and weather' },
  { name: 'IPCC 2006', use: 'fuel CO₂ factors' },
  { name: 'CEA v19', use: 'grid 0.716 kg/kWh' },
  { name: 'FuelEconomy.gov', use: 'real-data validation' },
];

export default function Landing() {
  return (
    <div className="pub-contours min-h-[100dvh] text-[color:var(--gg-ink)]">
      <TopBar />
      <main className="mx-auto max-w-[1200px] px-5 lg:px-8">
        <Hero />
        <HowItWorks />
        <RoundOrder />
        <Proof />
        <Sources />
      </main>
      <Footer />
    </div>
  );
}

function TopBar() {
  return (
    <header className="mx-auto flex max-w-[1200px] items-center justify-between px-5 py-5 lg:px-8">
      <BrandMark />
      <nav className="flex items-center gap-2 sm:gap-3">
        <Link to="/login" className="pub-btn pub-btn-ghost">Sign in</Link>
        <Link to="/register" className="pub-btn pub-btn-primary hidden sm:inline-flex">Register as a driver</Link>
      </nav>
    </header>
  );
}

function Hero() {
  return (
    <section className="grid gap-6 pt-4 pb-16 lg:grid-cols-12 lg:gap-0 lg:pt-8 lg:pb-24">
      <div className="pub-sign lg:col-span-7">
        <div className="pub-sign-inner px-6 py-8 sm:px-10 sm:py-10 lg:pr-24">
          <p className="font-mono text-xs uppercase tracking-[0.16em] text-white/70">Fleet eco-routing · Bengaluru</p>
          <h1 className="mt-4 font-display text-[44px] leading-[0.95] font-bold sm:text-6xl lg:text-[72px]">
            Plan every delivery for time and <CO2 />.
          </h1>
          <p className="mt-5 max-w-[52ch] text-[15px] leading-relaxed text-white/80">
            GoGreen finds the road and the stop order that use the least fuel, using real roads, hills and weather.
          </p>

          <div className="mt-8">
            {HOSUR_ROUTES.map((route) => (
              <div key={route.name} className="pub-sign-row">
                <span className="font-display text-2xl font-semibold">Hosur · {route.name}</span>
                <span className="font-mono text-sm text-white/85">
                  {route.km} km · {route.co2} kg CO₂
                </span>
              </div>
            ))}
          </div>

          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/login" className="pub-btn pub-btn-light">
              Sign in <ArrowRight size={16} />
            </Link>
            <Link to="/register" className="pub-btn pub-btn-on-dark">Register as a driver</Link>
          </div>
        </div>
      </div>

      <div className="relative z-10 lg:col-span-5 lg:-ml-14 lg:mt-28">
        <BreakdownFigure />
      </div>
    </section>
  );
}

// Stacked bars drawn to one scale: 13.33 px per kg of CO₂.
function BreakdownFigure() {
  const left = 20;
  const pxPerKg = 400 / 30;
  return (
    <figure className="pub-card p-5 sm:p-6">
      <p className="pub-eyebrow">Live run · medium diesel truck, 5 t</p>
      <h2 className="mt-2 font-display text-[28px] leading-tight font-bold">
        Route B burns 59% more, and the model can say why.
      </h2>

      <svg viewBox="0 0 472 190" className="mt-4 w-full h-auto" role="img"
           aria-label="CO2 by cause. Route A 18.3 kg, route B 29.1 kg. Route B is faster, so air drag is higher, and it climbs 307 metres instead of 233.">
        {[0, 10, 20, 30].map((kg) => (
          <g key={kg}>
            <line x1={left + kg * pxPerKg} x2={left + kg * pxPerKg} y1="8" y2="150" style={{ stroke: 'var(--gg-line)' }} />
            <text x={left + kg * pxPerKg} y="168" textAnchor="middle" className="font-mono" fontSize="11" style={{ fill: 'var(--gg-muted)' }}>
              {kg} kg
            </text>
          </g>
        ))}
        {HOSUR_ROUTES.map((route, row) => (
          <StackedBar key={route.name} route={route} y={22 + row * 66} left={left} pxPerKg={pxPerKg} />
        ))}
      </svg>

      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-[color:var(--gg-muted)]">
        {PART_STYLES.map((part) => (
          <li key={part.key} className="inline-flex items-center gap-1.5">
            <svg width="10" height="10" aria-hidden="true"><rect width="10" height="10" rx="2" className={part.className} /></svg>
            {part.label}
          </li>
        ))}
      </ul>
      <figcaption className="mt-4 text-[13px] leading-relaxed text-[color:var(--gg-muted)]">
        Road B is faster, and faster means more wind resistance. It also climbs more hills: 307 m vs 233 m.
      </figcaption>
    </figure>
  );
}

function StackedBar({ route, y, left, pxPerKg }) {
  let x = left;
  const segments = PART_STYLES.map((part) => {
    const width = route.parts[part.key] * pxPerKg;
    const segment = { ...part, x, width };
    x += width;
    return segment;
  });
  return (
    <g>
      <text x={left} y={y - 6} fontSize="12" fontWeight="600" style={{ fill: 'var(--gg-ink)' }}>
        {route.name} · <tspan className="font-mono" fontWeight="400" style={{ fill: 'var(--gg-muted)' }}>{route.km} km, {route.minutes} min</tspan>
      </text>
      {segments.map((s) => (
        <rect key={s.key} x={s.x} y={y} width={s.width} height="28" className={s.className} />
      ))}
      <text x={x + 6} y={y + 19} className="font-mono" fontSize="12" fontWeight="600" style={{ fill: 'var(--gg-ink)' }}>
        {route.co2} kg
      </text>
    </g>
  );
}

function HowItWorks() {
  return (
    <section className="grid gap-10 py-16 lg:grid-cols-12 lg:py-20">
      <div className="lg:col-span-4">
        <p className="pub-eyebrow">How a prediction is made</p>
        <h2 className="mt-3 font-display text-4xl leading-none font-bold sm:text-5xl">
          Four milestones from a road to a kilogram of <CO2 />.
        </h2>
        <p className="mt-4 max-w-[46ch] text-[15px] leading-relaxed text-[color:var(--gg-muted)]">
          All of this is ready before the truck leaves. If a data source is down, the app tells you.
        </p>
      </div>

      <ol className="relative grid gap-7 lg:col-span-8 lg:pl-6">
        <span aria-hidden="true" className="absolute left-[19px] top-4 bottom-4 w-px border-l-2 border-dashed border-[color:var(--gg-line-strong)] lg:left-[43px]" />
        {STEPS.map((step, index) => (
          <li key={step.title} className="relative flex gap-5">
            <div className="pub-stone">
              <span className="pub-stone-cap">KM</span>
              <span className="pub-stone-num">{index + 1}</span>
            </div>
            <div className="pt-1">
              <p className="font-mono text-xs uppercase tracking-[0.12em] text-[color:var(--gg-sign)]">{step.source}</p>
              <h3 className="mt-1 text-lg font-semibold">{step.title}</h3>
              <p className="mt-1 max-w-[60ch] text-[14.5px] leading-relaxed text-[color:var(--gg-muted)]">{step.text}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function RoundOrder() {
  return (
    <section className="pub-card grid gap-8 overflow-hidden p-6 sm:p-10 lg:grid-cols-12">
      <div className="lg:col-span-5">
        <p className="pub-eyebrow">Multi-stop rounds</p>
        <h2 className="mt-3 font-display text-4xl leading-none font-bold sm:text-5xl">
          Drop the heavy load first.
        </h2>
        <p className="mt-4 text-[15px] leading-relaxed text-[color:var(--gg-muted)]">
          A truck gets lighter after each delivery. So drop the heaviest load first and the truck burns less fuel. GoGreen finds the best order for up to 10 stops.
        </p>
        <dl className="mt-7 grid grid-cols-3 gap-4 border-t border-[color:var(--gg-line)] pt-5">
          <Stat value="4.9%" label="less CO₂" />
          <Stat value="+4.2" unit="min" label="extra time" />
          <Stat value="27.5" unit="kg" label="vs 29.0 kg fastest" />
        </dl>
      </div>
      <div className="lg:col-span-7">
        <LoadChart />
      </div>
    </section>
  );
}

function Stat({ value, unit, label }) {
  return (
    <div>
      <dt className="sr-only">{label}</dt>
      <dd className="font-mono text-2xl font-semibold text-[color:var(--gg-ink)] sm:text-[28px]">
        {value}{unit && <span className="ml-1 text-sm font-normal text-[color:var(--gg-muted)]">{unit}</span>}
      </dd>
      <dd className="mt-1 text-xs text-[color:var(--gg-muted)]">{label}</dd>
    </div>
  );
}

// Step chart: tonnes carried on each leg. Plot area x 44–420 (5 legs), y 7 t at top, 0 t at the base.
function LoadChart() {
  const legWidth = 75.2;
  const x = (leg) => 44 + leg * legWidth;
  const y = (tonnes) => 190 - tonnes * (160 / 7);
  const stepPath = (loads) =>
    loads.map((t, leg) => `${leg === 0 ? 'M' : 'L'}${x(leg)},${y(t)} H${x(leg + 1)}`).join(' ');
  const greenest = stepPath(ROUND_LOADS.greenest);

  return (
    <figure>
      <svg viewBox="0 0 440 232" className="w-full h-auto" role="img"
           aria-label="Load carried on each leg. Greenest order: 6.5, 4.0, 3.7, 2.2, 0.4 tonnes. Fastest order: 6.5, 6.1, 4.3, 2.8, 2.5 tonnes.">
        {[0, 2, 4, 6].map((t) => (
          <g key={t}>
            <line x1="44" x2="420" y1={y(t)} y2={y(t)} style={{ stroke: 'var(--gg-line)' }} />
            <text x="36" y={y(t) + 4} textAnchor="end" className="font-mono" fontSize="11" style={{ fill: 'var(--gg-muted)' }}>{t} t</text>
          </g>
        ))}
        <path d={`${greenest} V${y(0)} H${x(0)} Z`} style={{ fill: 'var(--gg-sign-tint)' }} />
        <path d={stepPath(ROUND_LOADS.fastest)} fill="none" strokeWidth="2" strokeDasharray="6 5" style={{ stroke: 'var(--gg-faint)' }} />
        <path d={greenest} fill="none" strokeWidth="3" style={{ stroke: 'var(--gg-sign)' }} />
        {ROUND_LOADS.greenest.map((_, leg) => (
          <text key={leg} x={x(leg) + legWidth / 2} y="210" textAnchor="middle" className="font-mono" fontSize="11" style={{ fill: 'var(--gg-muted)' }}>
            leg {leg + 1}
          </text>
        ))}
        <text x="226" y="228" textAnchor="middle" fontSize="11" style={{ fill: 'var(--gg-muted)' }}>tonnes carried on each leg</text>
      </svg>
      <figcaption className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-[color:var(--gg-muted)]">
        <span className="inline-flex items-center gap-2">
          <span className="inline-block h-[3px] w-5 bg-[color:var(--gg-sign)]" /> Greenest: 2.5 t to MG Road first
        </span>
        <span className="inline-flex items-center gap-2">
          <span className="inline-block w-5 border-t-2 border-dashed border-[color:var(--gg-faint)]" /> Fastest order
        </span>
      </figcaption>
    </figure>
  );
}

function Proof() {
  return (
    <section className="grid items-start gap-6 py-16 lg:grid-cols-12 lg:py-20">
      <div className="pub-card p-6 sm:p-8 lg:col-span-5">
        <p className="pub-eyebrow">Learns each vehicle</p>
        <p className="mt-4 font-mono text-4xl font-semibold">
          ×1.000 <span className="text-[color:var(--gg-faint)]">→</span> <span className="text-[color:var(--gg-sign)]">×1.038</span>
        </p>
        <p className="mt-4 text-[15px] leading-relaxed text-[color:var(--gg-muted)]">
          A driver reported 15% more fuel than we predicted. The app adjusted a little, not fully, because one trip is not enough. Clearly wrong reports are ignored.
        </p>
      </div>

      <div className="pub-card p-6 sm:p-8 lg:col-span-7 lg:mt-12">
        <p className="pub-eyebrow">Checked against real data</p>
        <h2 className="mt-3 font-display text-3xl leading-tight font-bold">
          On 2,097 EPA-rated vehicles from 2023–24, our efficiency model is four times closer than a baseline.
        </h2>
        <div className="mt-6 grid gap-3">
          <ErrorBar label="Our model" value={0.52} max={2.18} strong />
          <ErrorBar label="Median baseline" value={2.18} max={2.18} />
        </div>
        <p className="mt-4 text-xs text-[color:var(--gg-muted)]">
          Mean absolute error in L/100 km, trained on 24,593 vehicles from 2000–2022. R² 0.91.
        </p>
      </div>
    </section>
  );
}

function ErrorBar({ label, value, max, strong = false }) {
  return (
    <div className="grid grid-cols-[110px_minmax(0,1fr)] items-center gap-3 text-sm">
      <span className="text-[color:var(--gg-muted)]">{label}</span>
      <div className="flex items-center gap-3">
        <div className="h-3 rounded-sm" style={{
          width: `${(value / max) * 80}%`,
          background: strong ? 'var(--gg-sign)' : 'var(--gg-line-strong)',
        }} />
        <span className="font-mono text-sm font-semibold">{value}</span>
      </div>
    </div>
  );
}

function Sources() {
  return (
    <section className="border-t border-[color:var(--gg-line)] py-10">
      <p className="pub-eyebrow">Data sources, all public</p>
      <ul className="mt-4 grid gap-x-8 gap-y-3 sm:grid-cols-2 lg:grid-cols-5">
        {SOURCES.map((source) => (
          <li key={source.name}>
            <p className="font-semibold">{source.name}</p>
            <p className="font-mono text-xs text-[color:var(--gg-muted)]">{source.use}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Footer() {
  return (
    <footer className="bg-[color:var(--gg-sign-deep)] text-white/75">
      <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-4 px-5 py-6 text-sm lg:px-8">
        <BrandMark onDark />
        <p>Numbers are estimates from public road, hill and weather data, not measured savings.</p>
      </div>
    </footer>
  );
}
