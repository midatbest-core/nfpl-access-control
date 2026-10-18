import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import type { AttentionJobPage } from '../api/contracts'
import { useAuth } from '../auth/AuthContext'
import { PageHeader } from '../components/AppShell'
import { EmptyState, ErrorMessage, InlineLoader } from '../components/Feedback'
import { StatusBadge } from '../components/StatusBadge'

export function AdminAttentionPage() {
  const { token } = useAuth()
  const [data, setData] = useState<AttentionJobPage>()
  const [cursor, setCursor] = useState<string>()
  const [stack, setStack] = useState<Array<string | undefined>>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    api.attentionJobs(token!, cursor)
      .then((result) => { if (active) setData(result) })
      .catch((caught: Error) => { if (active) setError(caught.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [cursor, token])

  return <div>
    <PageHeader eyebrow="Admin workspace" title="Jobs requiring attention" description="One focused queue for missing assignments, uncovered absences, ineligible nominees, and unresolved reassignment needs." />
    {error && <ErrorMessage message={error} />}
    {loading ? <InlineLoader label="Loading attention queue" /> : data?.items.length ? <>
      <div className="space-y-3">{data.items.map((item) => <article className="summary-card" key={item.job_id}><div className="flex flex-col justify-between gap-4 sm:flex-row"><div><div className="flex flex-wrap items-center gap-2"><Link className="text-lg font-semibold text-teal-700" to={`/admin/jobs/${item.job_id}`}>{item.reference}</Link><StatusBadge status={item.stage} /></div><p className="mt-1 text-sm text-slate-600">{item.client_name} · {item.branch_name}</p><ul className="mt-3 space-y-1">{item.reasons.map((reason) => <li className="flex gap-2 text-sm text-amber-900" key={reason}><span aria-hidden="true">!</span><span>{reason}</span></li>)}</ul></div><Link className="button-primary self-start" to={`/admin/jobs/${item.job_id}`}>Resolve assignments</Link></div></article>)}</div>
      <nav className="mt-5 flex justify-between" aria-label="Attention queue pagination"><button className="button-secondary" disabled={stack.length === 0} onClick={() => { const previous = stack.at(-1); setLoading(true); setError(''); setStack((items) => items.slice(0, -1)); setCursor(previous) }}>Previous</button><button className="button-secondary" disabled={!data.next_cursor} onClick={() => { if (!data.next_cursor) return; setLoading(true); setError(''); setStack((items) => [...items, cursor]); setCursor(data.next_cursor ?? undefined) }}>Next</button></nav>
    </> : !loading && !error ? <EmptyState title="No jobs need assignment attention" message="All active jobs have complete, effective responsibility coverage." /> : null}
  </div>
}
