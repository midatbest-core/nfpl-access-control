import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useToast } from '../../components/feedback/ToastContext'
import {
  AnchorIcon,
  ArrowRightIcon,
  CheckCircle2Icon,
  ChevronLeftIcon,
  CopyIcon,
} from '../../components/icons'
import { DEMO_EVALUATION_ACCOUNTS } from './demoData'


export function DemoAccountsPage() {
  const navigate = useNavigate()
  const toast = useToast()
  const [copiedEmail, setCopiedEmail] = useState<string | null>(null)

  const isDemoEnabled = import.meta.env.VITE_ENABLE_DEMO_ACCOUNTS !== 'false'

  async function handleCopy(email: string) {
    try {
      await navigator.clipboard.writeText(email)
      setCopiedEmail(email)
      toast.success(`Copied ${email} to clipboard.`)
      setTimeout(() => setCopiedEmail(null), 2500)
    } catch {
      toast.error('Unable to copy to clipboard.')
    }
  }

  function handleSelectAccount(email: string) {
    navigate('/login', { state: { email } })
  }

  const DEMO_PASSWORD = '123123123123'

  async function handleCopyPassword() {
    try {
      await navigator.clipboard.writeText(DEMO_PASSWORD)
      toast.success('Password 123123123123 copied to clipboard.')
    } catch {
      toast.error('Unable to copy password to clipboard.')
    }
  }

  if (!isDemoEnabled) {
    return (
      <div className="min-h-screen bg-slate-50 px-4 py-12 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-xl space-y-6 text-center">
          <Link
            to="/login"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900 transition"
          >
            <ChevronLeftIcon className="h-4 w-4" />
            Back to Sign In
          </Link>
          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-8 text-amber-900">
            <h2 className="text-base font-bold">Demo Accounts Reference Disabled</h2>
            <p className="mt-2 text-xs leading-relaxed text-amber-800">
              The evaluation demo accounts showcase has been disabled in this environment configuration via <code className="font-mono font-semibold">VITE_ENABLE_DEMO_ACCOUNTS=false</code>.
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-12 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-4xl space-y-8">
        <div className="flex items-center justify-between">
          <Link
            to="/login"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900 transition"
          >
            <ChevronLeftIcon className="h-4 w-4" />
            Back to Sign In
          </Link>
          <div className="flex items-center gap-2">
            <AnchorIcon className="h-4 w-4 text-cyan-600" />
            <span className="text-xs font-bold text-slate-700">Fictional Evaluation Reference</span>
          </div>
        </div>

        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-bold text-cyan-800">
            <span className="h-2 w-2 rounded-full bg-cyan-500 animate-pulse" />
            Evaluator Reference
          </div>
          <h1 className="mt-3 text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">
            Seeded Role Evaluation Personas
          </h1>
          <p className="mt-2 text-sm text-slate-600 leading-relaxed max-w-2xl">
            These fictional identities exercise the complete zero-trust customs brokerage RBAC model. Click <span className="font-semibold text-slate-800">Use in sign in</span> to prefill an identity on the login page.
          </p>

          {/* Shared Password Callout */}
          <div className="mt-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-2xl border border-cyan-200 bg-gradient-to-r from-cyan-50/80 via-white to-sky-50/60 p-4 shadow-2xs">
            <div className="space-y-0.5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-cyan-900">
                Shared Evaluation Demo Password
              </span>
              <p className="font-mono text-base font-black tracking-wider text-slate-900 select-all">
                123123123123
              </p>
              <p className="text-xs text-slate-500">
                All seeded fictional staff, client, and admin accounts use this password in the demo environment.
              </p>
            </div>
            <button
              type="button"
              onClick={handleCopyPassword}
              className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-cyan-300 bg-white px-3.5 py-2 text-xs font-bold text-cyan-900 shadow-2xs hover:bg-cyan-50 transition cursor-pointer shrink-0"
              title="Copy shared evaluation password"
            >
              <CopyIcon className="h-4 w-4 text-cyan-700" />
              <span>Copy Demo Password</span>
            </button>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {DEMO_EVALUATION_ACCOUNTS.map((acc) => {
            const Icon = acc.icon
            const isCopied = copiedEmail === acc.email
            return (
              <div
                key={acc.email}
                className={`flex flex-col justify-between rounded-2xl border p-5 shadow-xs transition hover:shadow-md ${acc.tone}`}
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="rounded-md bg-white/80 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-700 shadow-2xs border border-slate-200/50">
                      {acc.badge}
                    </span>
                    <Icon className="h-4 w-4 opacity-70" />
                  </div>

                  <h3 className="mt-3 text-sm font-bold text-slate-900">{acc.name}</h3>
                  <div className="mt-1 flex items-center justify-between gap-2">
                    <span className="font-mono text-xs text-slate-700 truncate">{acc.email}</span>
                    <button
                      type="button"
                      onClick={() => handleCopy(acc.email)}
                      title="Copy email to clipboard"
                      className="shrink-0 p-1 text-slate-400 hover:text-slate-700 rounded transition"
                    >
                      {isCopied ? (
                        <CheckCircle2Icon className="h-3.5 w-3.5 text-emerald-600" />
                      ) : (
                        <CopyIcon className="h-3.5 w-3.5" />
                      )}
                    </button>
                  </div>
                  <p className="mt-2 text-xs leading-relaxed text-slate-600">{acc.scope}</p>

                  <div className="mt-3 rounded-xl bg-white/60 p-2.5 border border-slate-200/60 text-[11px] text-slate-600 leading-normal">
                    <span className="font-bold text-slate-700">Test Focus: </span>
                    {acc.keyTest}
                  </div>
                </div>

                <div className="mt-5 pt-3 border-t border-slate-200/60">
                  <button
                    type="button"
                    onClick={() => handleSelectAccount(acc.email)}
                    className="inline-flex w-full items-center justify-center gap-1.5 rounded-xl bg-white/80 px-3 py-2 text-xs font-bold text-cyan-900 shadow-2xs border border-cyan-300 hover:bg-white hover:text-cyan-950 transition"
                  >
                    <span>Use in sign in</span>
                    <ArrowRightIcon className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            )
          })}
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-3">
          <h2 className="text-sm font-bold text-slate-900">Confidentiality & Security Guarantees</h2>
          <ul className="text-xs text-slate-600 space-y-1.5 list-disc pl-5 leading-relaxed">
            <li>No live database credentials, Neon connection URIs, or bearer tokens are ever shipped in client code.</li>
            <li>All requests authenticate through strict HTTP bearer tokens issued dynamically by the FastAPI backend.</li>
            <li>Zero-trust scoped RBAC invariants (maker-checker separation, version locking) are enforced authoritatively by backend policy services.</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
