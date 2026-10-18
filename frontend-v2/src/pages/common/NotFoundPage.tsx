import { Link } from 'react-router-dom'
import { AnchorIcon } from '../../components/icons'

export function NotFoundPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 px-4 py-12">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-lg space-y-4">
        <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-slate-100 text-slate-500">
          <AnchorIcon className="h-7 w-7 text-slate-400" />
        </div>

        <div>
          <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
            404 Error
          </span>
          <h1 className="mt-1 text-xl font-bold text-slate-900">
            Page Not Found
          </h1>
        </div>

        <p className="text-sm text-slate-600 leading-relaxed">
          The requested address is not mapped to an active NFPL operations workspace or shipment route.
        </p>

        <div className="pt-4">
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-xl bg-maritime-800 px-5 py-2.5 text-xs font-semibold text-white shadow-xs hover:bg-maritime-900 transition"
          >
            Return to Home
          </Link>
        </div>
      </div>
    </main>
  )
}
