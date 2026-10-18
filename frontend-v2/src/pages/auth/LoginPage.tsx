import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { landingPath } from '../../auth/roles'
import { FormField, TextInput } from '../../components/design-system/FormElements'
import { useToast } from '../../components/feedback/ToastContext'
import {
  AnchorIcon,
  ArrowRightIcon,
  CopyIcon,
  LockIcon,
  ShieldCheckIcon,
  UserIcon,
} from '../../components/icons'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const toast = useToast()

  const locationState = location.state as { email?: string; expired?: boolean } | null
  const wasExpired = locationState?.expired

  const [enteredEmail, setEnteredEmail] = useState<string | null>(null)
  const email = enteredEmail !== null ? enteredEmail : (locationState?.email || '')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const isDemoEnabled = import.meta.env.VITE_ENABLE_DEMO_ACCOUNTS !== 'false'

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!email.trim() || !password) {
      setErrorMessage('Please enter both your work email and password.')
      return
    }

    setSubmitting(true)
    setErrorMessage(null)

    try {
      const profile = await login({ email: email.trim(), password })
      toast.success(`Welcome back, ${profile.display_name}`, 'Signed In')
      navigate(landingPath(profile), { replace: true })
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : 'Authentication failed. Please verify your credentials and try again.'
      setErrorMessage(msg)
      toast.error(msg, 'Sign In Error')
    } finally {
      setSubmitting(false)
    }
  }

  const DEMO_PASSWORD = '123123123123'

  function handleSelectPersona(targetEmail: string) {
    setEnteredEmail(targetEmail)
    setErrorMessage(null)
  }

  function handleFillPassword() {
    setPassword(DEMO_PASSWORD)
    toast.success('Evaluation demo password filled.')
  }

  async function handleCopyPassword() {
    try {
      await navigator.clipboard.writeText(DEMO_PASSWORD)
      toast.success('Password 123123123123 copied to clipboard.')
    } catch {
      toast.error('Unable to copy password to clipboard.')
    }
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Visual Brand Sidepanel (visible on desktop) */}
      <div className="relative hidden w-1/2 flex-col justify-between bg-gradient-to-br from-maritime-950 via-maritime-900 to-maritime-800 p-12 text-white lg:flex">
        <div className="flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br from-cyan-400 to-sky-600 text-white shadow-lg shadow-cyan-950/50">
            <AnchorIcon className="h-6 w-6" />
          </div>
          <div>
            <span className="text-base font-extrabold tracking-wide">NFPL</span>
            <p className="text-xs text-cyan-300">Nagarkot Forwarders Pvt. Ltd.</p>
          </div>
        </div>

        <div className="max-w-md space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full bg-cyan-500/20 px-3 py-1 text-xs font-bold text-cyan-300 border border-cyan-400/30">
            <ShieldCheckIcon className="h-4 w-4" />
            Zero-Trust Scoped RBAC
          </div>
          <h2 className="text-3xl font-extrabold tracking-tight leading-tight">
            Customs brokerage shipment operations platform.
          </h2>
          <p className="text-sm text-slate-300 leading-relaxed">
            Strict separation of duty, immutable append-only versioning, and deterministic assignment verification.
          </p>
        </div>

        <div className="flex items-center justify-between border-t border-maritime-800/80 pt-6 text-xs text-slate-400">
          <p>&copy; {new Date().getFullYear()} Nagarkot Forwarders. Logistics excellence since 1989.</p>
          <Link to="/demo-accounts" className="text-cyan-400 hover:text-cyan-300 transition underline underline-offset-4">
            Phase 7 Demo Accounts
          </Link>
        </div>
      </div>

      {/* Login Form Container */}
      <div className="flex flex-1 flex-col justify-center px-4 py-12 sm:px-6 lg:px-12 xl:px-20">
        <div className="mx-auto w-full max-w-sm sm:max-w-md">
          {/* Mobile Logo */}
          <div className="flex items-center gap-2.5 mb-8 lg:hidden">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-maritime-800 text-white">
              <AnchorIcon className="h-5 w-5 text-cyan-400" />
            </div>
            <div>
              <span className="text-sm font-bold text-slate-900">NFPL Operations</span>
              <p className="text-xs text-slate-500">Logistics Access Control</p>
            </div>
          </div>

          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
              Sign in to your workspace
            </h1>
            <p className="mt-2 text-sm text-slate-600">
              Enter your corporate credentials to access authorized shipments.
            </p>
          </div>

          {wasExpired && (
            <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-800 font-medium">
              Your previous session has expired. Please sign in again.
            </div>
          )}

          {errorMessage && (
            <div
              className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs font-semibold text-rose-800"
              role="alert"
            >
              {errorMessage}
            </div>
          )}

          {isDemoEnabled && (
            <div className="mt-5 rounded-2xl border border-cyan-200 bg-gradient-to-br from-cyan-50/80 via-white to-sky-50/70 p-4 shadow-2xs space-y-3.5">
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-cyan-950">
                  <span className="h-2 w-2 rounded-full bg-cyan-500 animate-pulse" />
                  Evaluation Demo Mode
                </span>
                <Link
                  to="/demo-accounts"
                  className="text-xs font-semibold text-cyan-700 hover:text-cyan-900 underline underline-offset-2"
                >
                  Explore Demo Accounts &rarr;
                </Link>
              </div>

              {/* Shared Password Callout */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 rounded-xl bg-white border border-cyan-200/90 p-3 shadow-2xs">
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                    Evaluation demo password:
                  </p>
                  <p className="font-mono text-base font-black tracking-wider text-slate-900 select-all">
                    123123123123
                  </p>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <button
                    type="button"
                    onClick={handleCopyPassword}
                    className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition cursor-pointer"
                    title="Copy evaluation demo password to clipboard"
                  >
                    <CopyIcon className="h-3.5 w-3.5 text-slate-500" />
                    <span>Copy Password</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleFillPassword}
                    className="inline-flex items-center gap-1 rounded-lg bg-cyan-700 px-2.5 py-1.5 text-xs font-semibold text-white shadow-2xs hover:bg-cyan-800 transition cursor-pointer"
                    title="Fill demo password into input without submitting"
                  >
                    <span>Fill Password</span>
                  </button>
                </div>
              </div>

              {/* Quick Persona Fill */}
              <div className="space-y-1.5">
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Quick-Fill Fictional Account (Click to Select)
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {[
                    { label: 'Admin', email: 'admin@nfpl.test' },
                    { label: 'Maker', email: 'emp-00@nfpl.test' },
                    { label: 'Checker', email: 'emp-01@nfpl.test' },
                    { label: 'Filing', email: 'emp-02@nfpl.test' },
                    { label: 'Client', email: 'client-viewer-00@portal.test' },
                    { label: 'Deactivated', email: 'emp-18@nfpl.test' },
                  ].map((p) => (
                    <button
                      key={p.email}
                      type="button"
                      onClick={() => handleSelectPersona(p.email)}
                      className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition cursor-pointer ${
                        email === p.email
                          ? 'bg-cyan-800 text-white shadow-2xs'
                          : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              <p className="text-[11px] text-slate-500 leading-tight">
                * Note: These are disposable, fictional demonstration accounts with seeded roles. No production credentials or data are used.
              </p>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate className="mt-5 space-y-4">
            <FormField id="login-email" label="Email Address" required>
              <TextInput
                id="login-email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEnteredEmail(e.target.value)}
                placeholder="name@nfpl.test"
                icon={<UserIcon className="h-4 w-4" />}
              />
            </FormField>

            <FormField id="login-password" label="Password" required>
              <TextInput
                id="login-password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                icon={<LockIcon className="h-4 w-4" />}
              />
            </FormField>

            <button
              type="submit"
              disabled={submitting}
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-maritime-800 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-maritime-900 focus-visible:outline-2 focus-visible:outline-maritime-800 disabled:opacity-50"
            >
              {submitting ? (
                <>
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white" />
                  Verifying identity...
                </>
              ) : (
                <>
                  Sign in to workspace
                  <ArrowRightIcon className="h-4 w-4" />
                </>
              )}
            </button>
          </form>

          <div className="mt-8 border-t border-slate-200 pt-6">
            <div className="flex flex-col gap-3 text-center sm:flex-row sm:justify-between text-xs text-slate-600">
              <p>
                New employee?{' '}
                <Link to="/register" className="font-semibold text-cyan-700 hover:text-cyan-800">
                  Register staff account
                </Link>
              </p>
              <Link to="/demo-accounts" className="font-semibold text-slate-600 hover:text-slate-900">
                View demo accounts &rarr;
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
