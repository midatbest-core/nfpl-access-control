import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { landingPath } from '../../auth/roles'
import { StatusBadge } from '../../components/design-system/StatusBadge'
import { useToast } from '../../components/feedback/ToastContext'
import { AlertCircleIcon, ClockIcon, RefreshIcon } from '../../components/icons'

export function AccountStatusPage() {
  const { user, logout, refreshProfile } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()
  const [checking, setChecking] = useState(false)

  const isPending = user?.account_status === 'pending'

  async function handleRefresh() {
    setChecking(true)
    try {
      const updated = await refreshProfile()
      if (updated?.account_status === 'active') {
        toast.success('Your account is now active!', 'Access Granted')
        navigate(landingPath(updated), { replace: true })
      } else {
        toast.info('Account is still pending administrator review.', 'Status Checked')
      }
    } catch {
      toast.error('Could not refresh status. Please try again.', 'Error')
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-lg space-y-4">
        <div
          className={`mx-auto grid h-14 w-14 place-items-center rounded-2xl ${
            isPending ? 'bg-amber-50 text-amber-600' : 'bg-rose-50 text-rose-600'
          }`}
        >
          {isPending ? <ClockIcon className="h-7 w-7" /> : <AlertCircleIcon className="h-7 w-7" />}
        </div>

        <div>
          <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
            Account Status Review
          </span>
          <h2 className="mt-1 text-xl font-bold text-slate-900">
            {isPending ? 'Pending Administrator Approval' : 'Account Deactivated'}
          </h2>
        </div>

        <div className="py-2">
          <StatusBadge status={user?.account_status ?? 'pending'} size="md" />
        </div>

        <p className="text-sm text-slate-600 leading-relaxed">
          {isPending
            ? 'Your registration was received. Under NFPL security invariants, employee accounts cannot access operational shipments until a scoped administrator approves your identity and assigns role scopes.'
            : 'Your account has been deactivated by an operations administrator. Outstanding sessions have been revoked.'}
        </p>

        <div className="pt-4 flex flex-col gap-2.5 sm:flex-row sm:justify-center">
          {isPending && (
            <button
              type="button"
              disabled={checking}
              onClick={handleRefresh}
              className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50 transition"
            >
              <RefreshIcon className={`h-4 w-4 ${checking ? 'animate-spin' : ''}`} />
              Check Status
            </button>
          )}

          <button
            type="button"
            onClick={() => void logout()}
            className="inline-flex items-center justify-center rounded-xl bg-slate-800 px-4 py-2.5 text-xs font-semibold text-white shadow-xs hover:bg-slate-900 transition"
          >
            Sign Out
          </button>
        </div>
      </div>
    </div>
  )
}
