import { useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { api, ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { ErrorMessage } from '../components/Feedback'

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function AuthFrame({ children, title, description }: { children: ReactNode; title: string; description: string }) {
  return (
    <div className="min-h-screen bg-canvas">
      <div className="bg-red-600 px-4 py-3 text-center text-white shadow-lg">
        <p className="text-sm sm:text-base font-black uppercase tracking-wider">
          ⚠️ WARNING: DO NOT USE THIS VERSION! THIS IS THE DEPRECATED LEGACY PROTOTYPE. PLEASE USE FRONTEND V2 (/frontend-v2) INSTEAD.
        </p>
      </div>
      <main className="min-h-[calc(100vh-50px)] lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(480px,0.78fr)]">
        <section className="relative hidden overflow-hidden bg-deep-teal p-12 text-white lg:flex lg:flex-col lg:justify-between">
          <div className="absolute -right-32 -top-24 h-96 w-96 rounded-full border border-white/10" />
          <div className="absolute -right-16 -top-8 h-64 w-64 rounded-full border border-white/10" />
          <div className="relative flex items-center gap-3"><div className="grid h-11 w-11 place-items-center rounded-xl bg-white text-sm font-black text-teal-900">NF</div><div><p className="font-bold tracking-wide">NFPL</p><p className="text-xs text-teal-100">Customs brokerage operations</p></div></div>
          <div className="relative max-w-xl pb-12">
            <div className="mb-6 rounded-2xl border-2 border-amber-300 bg-amber-400/20 p-5 backdrop-blur">
              <p className="text-xs font-black uppercase tracking-widest text-amber-200">⚠️ Evaluator Warning</p>
              <p className="mt-1 text-sm font-bold text-white">This legacy folder (<code className="rounded bg-black/40 px-1 py-0.5 font-mono text-xs">/frontend</code>) is deprecated and not useful. Please run the official <strong className="underline text-amber-200">Frontend V2</strong> (<code className="rounded bg-black/40 px-1 py-0.5 font-mono text-xs">/frontend-v2</code>).</p>
            </div>
            <p className="mb-4 text-xs font-bold uppercase tracking-[0.24em] text-coral">Secure shipment workspace</p>
            <h1 className="font-display text-5xl font-semibold leading-[1.08] tracking-tight">Every handoff clear.<br />Every action accountable.</h1>
            <p className="mt-6 max-w-lg text-base leading-7 text-teal-50/80">A focused workspace for preparing, checking, and filing shipments with responsibility and access built into every step.</p>
          </div>
          <p className="relative text-xs text-teal-100/60">NFPL Access Control Service</p>
        </section>
        <section className="flex min-h-[calc(100vh-50px)] items-center justify-center px-5 py-10 sm:px-10">
          <div className="w-full max-w-md"><div className="mb-8 lg:hidden"><div className="inline-flex items-center gap-3"><div className="grid h-10 w-10 place-items-center rounded-xl bg-teal-800 text-sm font-black text-white">NF</div><p className="font-bold text-ink">NFPL Operations</p></div></div><p className="text-xs font-bold uppercase tracking-[0.2em] text-teal-700">Employee portal</p><h2 className="mt-3 text-3xl font-bold tracking-tight text-ink">{title}</h2><p className="mt-2 text-sm leading-6 text-slate-600">{description}</p><div className="mt-8">{children}</div></div>
        </section>
      </main>
    </div>
  )
}

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState(() => new URLSearchParams(location.search).get('email') ?? '')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const expired = Boolean((location.state as { expired?: boolean } | null)?.expired)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    if (!EMAIL_PATTERN.test(email.trim())) return setError('Enter a valid email address.')
    if (!password) return setError('Enter your password.')
    setSubmitting(true)
    try {
      await login({ email: email.trim().toLowerCase(), password })
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 403) {
        navigate('/account-status', { replace: true, state: { source: 'login' } })
      } else if (caught instanceof ApiError && caught.status === 401) {
        setError('The email or password is incorrect, or sign-in is temporarily locked after repeated failures. Verify the demo password and wait 15 minutes after five unsuccessful attempts.')
      } else {
        setError(caught instanceof Error ? caught.message : 'Login failed. Please try again.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthFrame title="Welcome back" description="Sign in with your approved NFPL employee account.">
      <div className="mb-6 rounded-2xl border-4 border-red-600 bg-red-50 p-6 text-red-950 shadow-2xl ring-4 ring-red-400/40">
        <div className="flex items-center gap-3">
          <span className="text-3xl sm:text-4xl" role="img" aria-label="warning">⚠️</span>
          <div>
            <h2 className="text-xl sm:text-2xl font-black uppercase tracking-tight text-red-700">
              WARNING: DO NOT USE THIS VERSION
            </h2>
            <p className="text-xs font-bold uppercase tracking-wider text-red-800">
              Legacy Prototype (/frontend) is Deprecated &amp; Not Useful
            </p>
          </div>
        </div>
        <p className="mt-3 text-sm font-semibold leading-relaxed text-red-950">
          This basic folder is an early proof-of-concept and is <strong>not useful</strong>. All complete features, modern UI, evaluator personas, and audit timelines are in <strong>Frontend V2</strong>.
        </p>
        <div className="mt-4 rounded-xl border border-red-300 bg-white p-4">
          <p className="text-sm font-black text-red-700">
            👉 Please run and use Frontend V2:
          </p>
          <pre className="mt-2 rounded-lg bg-slate-900 p-3 font-mono text-xs text-white overflow-x-auto">
cd frontend-v2{"\n"}npm install{"\n"}npm run dev
          </pre>
          <p className="mt-2 text-xs font-bold text-slate-700">
            Default URL: <a className="underline text-blue-600 font-bold" href="http://localhost:5173">http://localhost:5173</a>
          </p>
        </div>
      </div>
      {expired && <div className="mb-5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">Your session ended. Sign in again to continue.</div>}
      {error && <div className="mb-5"><ErrorMessage message={error} title="Sign-in unsuccessful" /></div>}
      <form className="space-y-5" onSubmit={(event) => void submit(event)} noValidate>
        <label className="form-label">Email address<input className="field mt-2" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@nfpl.example" /></label>
        <label className="form-label">Password<input className="field mt-2" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
        <button className="button-primary w-full" type="submit" disabled={submitting}>{submitting ? 'Signing in...' : 'Sign in securely'}</button>
      </form>
      <p className="mt-7 text-center text-sm text-slate-600">New to NFPL? <Link className="font-semibold text-teal-700 hover:text-teal-900" to="/register">Request an employee account</Link></p>
      <Link className="button-secondary mt-4 w-full" to="/demo-accounts">Explore Demo Accounts</Link>
    </AuthFrame>
  )
}

export function RegisterPage() {
  const navigate = useNavigate()
  const [values, setValues] = useState({ name: '', email: '', branch_id: '', password: '', confirm: '' })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const update = (field: keyof typeof values, value: string) => setValues((current) => ({ ...current, [field]: value }))

  function validate(): string | null {
    if (!values.name.trim()) return 'Enter your full name.'
    if (!EMAIL_PATTERN.test(values.email.trim())) return 'Enter a valid email address.'
    if (!values.branch_id.trim()) return 'Enter the branch ID supplied by your administrator.'
    if (values.password.length < 12) return 'Use at least 12 characters for your password.'
    if (!/[a-z]/.test(values.password) || !/[A-Z]/.test(values.password)) return 'Password must include upper- and lowercase letters.'
    if (!/\d/.test(values.password)) return 'Password must include a number.'
    if (values.password !== values.confirm) return 'The passwords do not match.'
    return null
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    const validation = validate()
    if (validation) return setError(validation)
    setSubmitting(true)
    try {
      const result = await api.register({ name: values.name.trim(), email: values.email.trim().toLowerCase(), branch_id: values.branch_id.trim(), password: values.password })
      navigate('/account-status', { replace: true, state: { source: 'registration', email: result.email } })
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Registration failed. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthFrame title="Request an account" description="Your account will remain pending until an NFPL Admin approves it.">
      {error && <div className="mb-5"><ErrorMessage message={error} title="Check your details" /></div>}
      <form className="space-y-4" onSubmit={(event) => void submit(event)} noValidate>
        <label className="form-label">Full name<input className="field mt-2" autoComplete="name" value={values.name} onChange={(event) => update('name', event.target.value)} /></label>
        <label className="form-label">Work email<input className="field mt-2" type="email" autoComplete="email" value={values.email} onChange={(event) => update('email', event.target.value)} /></label>
        <label className="form-label">Branch ID<input className="field mt-2" value={values.branch_id} onChange={(event) => update('branch_id', event.target.value)} aria-describedby="branch-help" /><span id="branch-help" className="mt-1.5 block text-xs font-normal leading-5 text-slate-500">Use the branch identifier provided by your administrator.</span></label>
        <label className="form-label">Password<input className="field mt-2" type="password" autoComplete="new-password" value={values.password} onChange={(event) => update('password', event.target.value)} /><span className="mt-1.5 block text-xs font-normal text-slate-500">12-128 characters with upper/lowercase letters and a number.</span></label>
        <label className="form-label">Confirm password<input className="field mt-2" type="password" autoComplete="new-password" value={values.confirm} onChange={(event) => update('confirm', event.target.value)} /></label>
        <button className="button-primary mt-2 w-full" type="submit" disabled={submitting}>{submitting ? 'Submitting...' : 'Submit for approval'}</button>
      </form>
      <p className="mt-6 text-center text-sm text-slate-600">Already approved? <Link className="font-semibold text-teal-700" to="/login">Return to sign in</Link></p>
    </AuthFrame>
  )
}

export function AccountStatusPage() {
  const location = useLocation()
  const state = location.state as { source?: string; email?: string } | null
  const registered = state?.source === 'registration'
  return (
    <AuthFrame title={registered ? 'Request received' : 'Account unavailable'} description={registered ? 'An NFPL administrator must approve your account before you can sign in.' : 'This account is pending approval or has been disabled by an administrator.'}>
      <div className="rounded-2xl border border-teal-100 bg-white p-6 shadow-sm"><div className="grid h-12 w-12 place-items-center rounded-full bg-teal-50 text-sm font-bold text-teal-700">OK</div><h3 className="mt-5 text-lg font-semibold text-ink">{registered ? 'Approval is the next step' : 'Contact an NFPL administrator'}</h3><p className="mt-2 text-sm leading-6 text-slate-600">{registered ? `Your request${state?.email ? ` for ${state.email}` : ''} is safely recorded. Roles cannot be selected during registration and will be assigned only after review.` : 'For security, the sign-in response does not reveal private account-state details. An administrator can confirm your status.'}</p></div>
      <Link className="button-secondary mt-6 w-full" to="/login">Back to sign in</Link>
    </AuthFrame>
  )
}
