import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle, AlertCircle, Loader, ArrowLeft } from 'lucide-react';
import api from '../../api/api';
import { AuthShell, Field } from './PublicKit';

const STEPS = ['Verify email', 'Driver details', 'Set password'];

export default function Register() {
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [form, setForm] = useState({
    email: '', otp: '',
    name: '', phone: '', dob: '', address: '',
    license_no: '', experience_years: '', emergency_contact: '',
    password: '', confirm_password: ''
  });

  const set = (field) => (e) => setForm(f => ({ ...f, [field]: e.target.value }));

  // ── Step 0: request and verify the email OTP ──────────────────────────────
  async function requestOtp(e) {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      await api.post('/auth/request-otp', { email: form.email });
      setStep(0.5); // OTP sent — show verify sub-step
    } catch (err) {
      setError(err.response?.data?.message || 'Could not send the code. Please try again.');
    } finally { setLoading(false); }
  }

  async function verifyOtp(e) {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      await api.post('/auth/verify-otp', { email: form.email, otp: form.otp });
      setStep(1);
    } catch (err) {
      setError(err.response?.data?.message || 'That code is not valid.');
    } finally { setLoading(false); }
  }

  // ── Step 1: driver details ────────────────────────────────────────────────
  function submitPersonal(e) {
    e.preventDefault();
    setError('');
    if (!form.name || !form.phone || !form.license_no) {
      setError('Name, phone and licence number are required.'); return;
    }
    setStep(2);
  }

  // ── Step 2: password, then submit the application ─────────────────────────
  async function submitRegistration(e) {
    e.preventDefault();
    setError('');
    if (form.password !== form.confirm_password) {
      setError('Passwords do not match.'); return;
    }
    if (form.password.length < 8) {
      setError('Password must be at least 8 characters.'); return;
    }
    setLoading(true);
    try {
      await api.post('/auth/register', {
        email: form.email,
        otp: form.otp,
        name: form.name,
        phone: form.phone,
        dob: form.dob || undefined,
        address: form.address || undefined,
        license_no: form.license_no,
        experience_years: form.experience_years ? parseInt(form.experience_years) : undefined,
        emergency_contact: form.emergency_contact || undefined,
        password: form.password,
      });
      setStep(3);
    } catch (err) {
      setError(err.response?.data?.message || 'Registration failed. Please try again.');
    } finally { setLoading(false); }
  }

  const displayStep = step === 0.5 ? 0 : Math.floor(step);

  return (
    <AuthShell sign={<RegisterSign />}>
      {step < 3 && <StepMilestones current={displayStep} />}

      {error && (
        <div className="pub-alert pub-alert-error mt-6" role="alert">
          <AlertCircle size={16} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {step === 0 && (
        <form onSubmit={requestOtp} className="mt-6 grid gap-4">
          <FormTitle title="Create your driver account" text="We will email you a one-time code to confirm the address." />
          <Field id="reg-email" label="Email address" type="email" autoComplete="email"
                 value={form.email} onChange={set('email')} required />
          <SubmitButton loading={loading} label="Send code" />
          <p className="text-sm text-[color:var(--gg-muted)]">
            Already registered?{' '}
            <Link to="/login" className="font-semibold text-[color:var(--gg-sign)] hover:underline">Sign in</Link>
          </p>
        </form>
      )}

      {step === 0.5 && (
        <form onSubmit={verifyOtp} className="mt-6 grid gap-4">
          <FormTitle title="Check your email" text={<>We sent a 6-digit code to <strong className="text-[color:var(--gg-ink)]">{form.email}</strong>.</>} />

          <div>
            <label htmlFor="reg-otp" className="pub-label">6-digit code</label>
            <input id="reg-otp" type="text" inputMode="numeric" autoComplete="one-time-code" maxLength={6}
                   className="pub-input text-center font-mono text-xl tracking-[0.5em]"
                   value={form.otp} onChange={set('otp')} placeholder="······" required />
          </div>
          <SubmitButton loading={loading} label="Verify code" />
          <button type="button" onClick={() => setStep(0)} className="inline-flex items-center gap-1.5 text-sm text-[color:var(--gg-muted)] hover:text-[color:var(--gg-sign)]">
            <ArrowLeft size={14} /> Use a different email
          </button>
        </form>
      )}

      {step === 1 && (
        <form onSubmit={submitPersonal} className="mt-6 grid gap-4 sm:grid-cols-2">
          <FormTitle className="sm:col-span-2" title="Driver details" text="Your fleet admin reviews these before approving you." />
          <Field id="reg-name" className="sm:col-span-2" label="Full name" value={form.name} onChange={set('name')} required autoComplete="name" />
          <Field id="reg-phone" label="Phone number" type="tel" value={form.phone} onChange={set('phone')} required autoComplete="tel" />
          <Field id="reg-dob" label="Date of birth (optional)" type="date" value={form.dob} onChange={set('dob')} />
          <Field id="reg-licence" label="Driving licence number" value={form.license_no} onChange={set('license_no')} required />
          <Field id="reg-exp" label="Years driving (optional)" type="number" min="0" max="50" value={form.experience_years} onChange={set('experience_years')} />
          <div className="sm:col-span-2">
            <label htmlFor="reg-address" className="pub-label">Address (optional)</label>
            <textarea id="reg-address" rows={2} className="pub-input resize-none" value={form.address} onChange={set('address')} />
          </div>
          <Field id="reg-emergency" className="sm:col-span-2" label="Emergency contact (optional)" placeholder="Name and phone number"
                 value={form.emergency_contact} onChange={set('emergency_contact')} />
          <button type="submit" className="pub-btn pub-btn-primary sm:col-span-2 w-full">Continue</button>
        </form>
      )}

      {step === 2 && (
        <form onSubmit={submitRegistration} className="mt-6 grid gap-4">
          <FormTitle title="Set your password" text="At least 8 characters." />
          <Field id="reg-password" label="Password" type="password" autoComplete="new-password" minLength={8}
                 value={form.password} onChange={set('password')} required />
          <Field id="reg-confirm" label="Confirm password" type="password" autoComplete="new-password"
                 value={form.confirm_password} onChange={set('confirm_password')} required />
          <div className="mt-1 flex gap-3">
            <button type="button" onClick={() => setStep(1)} className="pub-btn pub-btn-ghost flex-1">Back</button>
            <SubmitButton loading={loading} label="Submit application" className="flex-1" />
          </div>
        </form>
      )}

      {step === 3 && (
        <div className="py-2">
          <CheckCircle className="h-10 w-10 text-[color:var(--gg-sign)]" />
          <h1 className="mt-4 font-display text-4xl font-bold">Application sent</h1>
          <p className="mt-3 text-[15px] leading-relaxed text-[color:var(--gg-muted)]">
            Your registration is waiting for your fleet admin’s approval. You can sign in once it is approved.
          </p>
          <Link to="/login" className="pub-btn pub-btn-primary mt-6 w-full">Go to sign in</Link>
        </div>
      )}
    </AuthShell>
  );
}

function FormTitle({ title, text, className = '' }) {
  return (
    <div className={className}>
      <h1 className="font-display text-4xl font-bold">{title}</h1>
      <p className="mt-2 text-sm text-[color:var(--gg-muted)]">{text}</p>
    </div>
  );
}

function SubmitButton({ loading, label, className = '' }) {
  return (
    <button type="submit" className={`pub-btn pub-btn-primary w-full ${className}`} disabled={loading}>
      {loading ? <><Loader className="animate-spin" size={16} /> Please wait…</> : label}
    </button>
  );
}

// Progress shown as kilometre stones: green = done, yellow cap = current, grey = later.
function StepMilestones({ current }) {
  return (
    <ol className="flex items-center gap-3" aria-label="Registration progress">
      {STEPS.map((label, i) => {
        const state = i < current ? 'is-done' : i === current ? '' : 'is-later';
        return (
          <React.Fragment key={label}>
            <li className="flex items-center gap-2.5" aria-current={i === current ? 'step' : undefined}>
              <div className={`pub-stone ${state}`}>
                <span className="pub-stone-cap">KM</span>
                <span className="pub-stone-num">{i + 1}</span>
              </div>
              <span className={`hidden text-sm sm:inline ${i === current ? 'font-semibold' : 'text-[color:var(--gg-muted)]'}`}>{label}</span>
            </li>
            {i < STEPS.length - 1 && <li aria-hidden="true" className="h-px flex-1 border-t-2 border-dashed border-[color:var(--gg-line-strong)]" />}
          </React.Fragment>
        );
      })}
    </ol>
  );
}

function RegisterSign() {
  return (
    <div>
      <p className="font-display text-3xl leading-tight font-bold sm:text-4xl lg:text-5xl">Drive for a fleet on GoGreen.</p>
      <div className="mt-6 hidden lg:block">
        <div className="pub-sign-row">
          <span className="text-white/80">Register and verify your email</span>
        </div>
        <div className="pub-sign-row">
          <span className="text-white/80">Your fleet admin approves you and assigns a vehicle</span>
        </div>
        <div className="pub-sign-row">
          <span className="text-white/80">Plan trips, get the greener route, report fuel used</span>
        </div>
      </div>
    </div>
  );
}
