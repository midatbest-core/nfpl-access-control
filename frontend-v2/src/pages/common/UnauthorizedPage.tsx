import { Link } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { landingPath } from '../../auth/roles'
import { ShieldCheckIcon } from '../../components/icons'

export function UnauthorizedPage() {
  const { user, logout } = useAuth()

  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 px-4 py-12">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-lg space-y-4">
        <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-amber-50 text-amber-600">
          <ShieldCheckIcon className="h-8 w-8" />
        </div>

        <div>
          <span className="text-[10px] font-bold uppercase tracking-widest text-amber-600">
            403 &bull; Access Restricted
          </span>
          <h1 className="mt-1 text-xl font-bold text-slate-900">
            Workspace Not Assigned
          </h1>
        </div>

        <p className="text-sm text-slate-600 leading-relaxed">
          Your active roles or scopes do not authorize access to this section. Under NFPL fail-closed policies, unauthorized routes do not disclose operational shipment data.
        </p>

        <div className="pt-4 flex flex-col gap-2.5 sm:flex-row sm:justify-center">
          {user && (
            <Link
              to={landingPath(user)}
              className="inline-flex items-center justify-center rounded-xl bg-maritime-800 px-4 py-2.5 text-xs font-semibold text-white shadow-xs hover:bg-maritime-900 transition"
            >
              Go to my workspace
            </Link>
          )}

          <button
            type="button"
            onClick={() => void logout()}
            className="inline-flex items-center justify-center rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50 transition"
          >
            Sign out
          </button>
        </div>
      </div>
    </main>
  )
}
