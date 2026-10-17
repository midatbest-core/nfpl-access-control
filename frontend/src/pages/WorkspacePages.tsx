import { Link } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { landingPath } from '../auth/roles'
import { PageHeader } from '../components/AppShell'
import { EmptyState } from '../components/Feedback'
import { StatusBadge } from '../components/StatusBadge'

const pageCopy: Record<string, { eyebrow: string; title: string; description: string }> = {
  jobs: { eyebrow: 'Admin workspace', title: 'All jobs', description: 'Search, assignment, creation, and archive controls arrive in Phase 6B.' },
  employees: { eyebrow: 'Admin workspace', title: 'Employees', description: 'The employee directory and approval controls arrive in Phase 6B.' },
  requests: { eyebrow: 'Admin workspace', title: 'Urgent requests', description: 'Absence, edit, and exceptional request review arrives in Phase 6B.' },
  audit: { eyebrow: 'Admin workspace', title: 'Audit history', description: 'Authorized audit timelines arrive in a later frontend phase.' },
  notifications: { eyebrow: 'Your workspace', title: 'Notifications', description: 'Actionable notification listing arrives in Phase 6B.' },
  work: { eyebrow: 'Operations', title: 'My work', description: 'Your authorized, actionable shipment queue arrives in Phase 6B.' },
  job: { eyebrow: 'Operations', title: 'Assigned job', description: 'Shipment details and workflow actions arrive in Phase 6B.' },
  shipments: { eyebrow: 'Client workspace', title: 'My shipments', description: 'Client-scoped shipment tracking arrives in Phase 6B.' },
  updates: { eyebrow: 'Client workspace', title: 'Recent updates', description: 'The client-safe incremental update feed arrives in Phase 6B.' },
  shipment: { eyebrow: 'Client workspace', title: 'Shipment details', description: 'Client-safe progress and history arrive in Phase 6B.' },
}

export function AdminOverviewPage() {
  const { user } = useAuth()
  return (
    <div><PageHeader eyebrow="Admin workspace" title={`Good day, ${user?.display_name.split(' ')[0] ?? 'Admin'}`} description="Your workspace foundation is ready. Live operational cards and request actions are intentionally deferred to Phase 6B." /><section className="grid gap-4 sm:grid-cols-3"><div className="summary-card"><p className="summary-label">Account</p><StatusBadge status={user?.account_status ?? 'active'} /></div><div className="summary-card"><p className="summary-label">Availability</p><StatusBadge status={user?.availability ?? 'available'} /></div><div className="summary-card"><p className="summary-label">Branch</p><p className="mt-2 text-sm font-semibold text-ink">{user?.branch_name ?? 'All authorized branches'}</p></div></section><div className="mt-6"><EmptyState title="Operational dashboard coming in Phase 6B" message="No mock counts are shown. The next phase will connect these cards to the existing Admin overview API." /></div></div>
  )
}

export function PlaceholderPage({ page }: { page: keyof typeof pageCopy }) {
  const copy = pageCopy[page]
  return <div><PageHeader {...copy} /><EmptyState title="Frontend integration not enabled yet" message="This page is part of the approved navigation structure, but live controls and data are intentionally deferred. There are no fake actions or sample records here." /></div>
}

export function UnauthorizedPage() {
  const { user, logout } = useAuth()
  return (
    <main className="grid min-h-screen place-items-center bg-canvas px-5"><section className="w-full max-w-lg rounded-3xl border border-slate-200 bg-white p-8 text-center shadow-xl shadow-slate-200/40"><p className="text-xs font-bold uppercase tracking-[0.2em] text-coral">Access unavailable</p><h1 className="mt-3 text-3xl font-bold text-ink">This workspace is not assigned to you</h1><p className="mt-4 text-sm leading-6 text-slate-600">Your current active roles do not include this section. Access may have expired or been revoked. No shipment details were disclosed.</p><div className="mt-7 flex flex-col gap-3 sm:flex-row sm:justify-center">{user && <Link className="button-primary" to={landingPath(user)}>Go to my workspace</Link>}<button type="button" className="button-secondary" onClick={() => void logout()}>Sign out</button></div></section></main>
  )
}

export function NotFoundPage() {
  return <main className="grid min-h-screen place-items-center bg-canvas px-5"><section className="text-center"><p className="text-sm font-bold text-coral">404</p><h1 className="mt-2 text-3xl font-bold text-ink">Page not found</h1><p className="mt-3 text-slate-600">The address may be incorrect or no longer available.</p><Link className="button-primary mt-6" to="/">Return home</Link></section></main>
}
