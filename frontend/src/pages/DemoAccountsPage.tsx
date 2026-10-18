import { Link } from 'react-router-dom'

const enabled = import.meta.env.VITE_DEMO_ACCOUNTS_ENABLED === 'true'

const accounts = [
  { name: 'Nadia Admin', roles: 'Admin', email: 'admin@nfpl.test' },
  { name: 'Aarav Shah', roles: 'Maker · scoped Checker', email: 'emp-00@nfpl.test' },
  { name: 'Diya Nair', roles: 'Checker · Filing Officer', email: 'emp-01@nfpl.test' },
  { name: 'Kabir Rao', roles: 'Filing Officer', email: 'emp-02@nfpl.test' },
  { name: 'Oriana Textiles Portal', roles: 'Client Viewer', email: 'client-viewer-00@portal.test' },
]

export function DemoAccountsPage() {
  return <main className="min-h-screen bg-canvas px-5 py-10 sm:px-8">
    <div className="mx-auto max-w-5xl">
      <div className="mb-8 rounded-2xl border-4 border-red-600 bg-red-50 p-6 text-red-950 shadow-2xl ring-4 ring-red-400/40">
        <div className="flex items-center gap-3">
          <span className="text-3xl sm:text-4xl">⚠️</span>
          <div>
            <h2 className="text-xl sm:text-2xl font-black uppercase tracking-tight text-red-700">
              WARNING: DO NOT USE THIS VERSION
            </h2>
            <p className="text-xs font-bold uppercase tracking-wider text-red-800">
              Legacy Prototype (/frontend) is Deprecated &amp; Not Useful
            </p>
          </div>
        </div>
        <p className="mt-3 text-sm font-semibold text-red-950">
          This basic demo page is part of the early deprecated prototype. Please run and evaluate <strong>Frontend V2</strong> (<code className="rounded bg-red-200/80 px-1 py-0.5 font-mono text-xs">/frontend-v2</code>) which features the complete modern Evaluator Persona Quick-Switch, interactive visual workflows, and audit feeds.
        </p>
      </div>
      <Link className="inline-flex items-center gap-2 text-sm font-semibold text-teal-700" to="/login"><span aria-hidden="true">←</span> Back to sign in</Link>
      <header className="mt-7 max-w-3xl"><p className="text-xs font-bold uppercase tracking-[0.2em] text-coral">One-day evaluation</p><h1 className="mt-3 font-display text-4xl font-bold tracking-tight text-ink">Explore NFPL by role</h1><p className="mt-3 text-base leading-7 text-slate-600">Use the deliberately fictional seed accounts to follow a shipment from preparation through client-safe tracking. Every account still obeys its real backend authorization scope.</p></header>
      {!enabled ? <section className="summary-card mt-8"><h2 className="text-lg font-semibold">Demo directory is disabled</h2><p className="mt-2 text-sm leading-6 text-slate-600">This deployment has not explicitly enabled the evaluator directory. Set the documented Vite demo flag only for a disposable demo environment.</p></section> : <>
        <div className="mt-8 overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm"><table className="w-full min-w-[46rem] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="p-4">Fictional user</th><th className="p-4">Role access</th><th className="p-4">Demo email</th><th className="p-4">Demo password</th><th className="p-4"><span className="sr-only">Action</span></th></tr></thead><tbody>{accounts.map((account) => <tr className="border-t border-slate-100" key={account.email}><td className="p-4 font-semibold">{account.name}</td><td className="p-4 text-slate-600">{account.roles}</td><td className="p-4 font-mono text-xs">{account.email}</td><td className="p-4 text-slate-600">Use the evaluator-provided shared password</td><td className="p-4"><Link className="font-semibold text-teal-700" to={`/login?email=${encodeURIComponent(account.email)}`}>Use account →</Link></td></tr>)}</tbody></table></div>
        <section className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-5"><h2 className="font-semibold text-amber-950">Suggested five-minute tour</h2><ol className="mt-3 grid gap-2 text-sm text-amber-950 sm:grid-cols-2"><li>1. Admin: dashboard, attention queue, and audit timeline.</li><li>2. Maker: search My Work and submit a shipment.</li><li>3. Checker: complete the generated checklist.</li><li>4. Filing Officer: file or return checked work.</li><li>5. Client Viewer: review safe progress and raise a query.</li></ol></section>
      </>}
    </div>
  </main>
}
