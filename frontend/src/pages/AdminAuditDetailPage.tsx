import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api/client'
import type { AuditEvent, Job } from '../api/contracts'
import { useAuth } from '../auth/AuthContext'
import { PageHeader } from '../components/AppShell'
import { EmptyState, ErrorMessage, InlineLoader } from '../components/Feedback'

const displayDate = (value: string) => new Date(value).toLocaleString()
const titleCase = (value: string) => value.replaceAll('.', ' · ').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())

const categories = [
  { match: ['assignment', 'responsibility', 'delegat', 'role'], label: 'Member change', icon: '⇄', tone: 'border-sky-300 bg-sky-50 text-sky-900' },
  { match: ['file', 'check', 'approv'], label: 'Filing & approval', icon: '✓', tone: 'border-emerald-300 bg-emerald-50 text-emerald-900' },
  { match: ['prepar', 'submit', 'resubmit'], label: 'Submission', icon: '↑', tone: 'border-teal-300 bg-teal-50 text-teal-900' },
  { match: ['denied', 'return', 'correction', 'error'], label: 'Correction or denial', icon: '!', tone: 'border-amber-300 bg-amber-50 text-amber-950' },
  { match: ['admin', 'absence', 'cancel', 'reopen', 'override'], label: 'Administrative override', icon: '⚑', tone: 'border-violet-300 bg-violet-50 text-violet-950' },
]

function eventCategory(action: string) {
  return categories.find((category) => category.match.some((part) => action.includes(part)))
    ?? { label: 'Workflow event', icon: '•', tone: 'border-slate-300 bg-slate-50 text-slate-900' }
}

function displayValue(value: unknown) {
  if (value === null || value === undefined || value === '') return 'None'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function changes(event: AuditEvent) {
  if (!event.before_state && !event.after_state) return []
  const keys = new Set([
    ...Object.keys(event.before_state ?? {}),
    ...Object.keys(event.after_state ?? {}),
  ])
  return [...keys].filter((key) => JSON.stringify(event.before_state?.[key]) !== JSON.stringify(event.after_state?.[key]))
}

export function AdminAuditDetailPage() {
  const { jobId = '' } = useParams()
  const { token } = useAuth()
  const [job, setJob] = useState<Job>()
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    Promise.all([api.job(token!, jobId), api.audit(token!, jobId)])
      .then(([shipment, auditEvents]) => {
        if (!active) return
        setJob(shipment)
        setEvents([...auditEvents].reverse())
      })
      .catch((caught: Error) => { if (active) setError(caught.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [jobId, token])

  if (loading) return <InlineLoader label="Loading audit timeline" />
  return <div>
    <Link className="mb-5 inline-flex items-center gap-2 text-sm font-semibold text-teal-700" to="/admin/audit"><span aria-hidden="true">←</span> Back to audit history</Link>
    <PageHeader eyebrow="Immutable audit timeline" title={job?.reference ?? 'Shipment audit'} description="Chronological, append-only workflow evidence. Actor IDs remain available for exact traceability." />
    {error && <ErrorMessage title="History unavailable" message={error} />}
    {!error && events.length === 0 ? <EmptyState title="No audit events" message="No authorized audit events are available for this shipment." /> : <ol className="relative ml-4 border-l-2 border-slate-200 pl-7">{events.map((event) => {
      const category = eventCategory(event.action)
      const changedFields = changes(event)
      return <li className="relative mb-5" key={event.id}>
        <span className={`absolute -left-11 grid h-8 w-8 place-items-center rounded-full border text-sm font-bold ${category.tone}`} aria-hidden="true">{category.icon}</span>
        <article className="summary-card">
          <div className="flex flex-col justify-between gap-2 sm:flex-row"><div><span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-bold ${category.tone}`}>{category.icon} {category.label}</span><h2 className="mt-2 font-semibold">{titleCase(event.action)}{event.denied ? ' — Denied' : ''}</h2></div><time className="text-xs text-slate-500" dateTime={event.occurred_at}>{displayDate(event.occurred_at)}</time></div>
          <p className="mt-3 text-sm"><strong>{event.actor_display_name}</strong> <span className="text-slate-500">({event.actor_user_id})</span></p>
          <p className="mt-2 text-sm leading-6 text-slate-700">{event.reason}</p>
          {changedFields.length > 0 && <div className="mt-4 overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr><th className="pb-2 pr-4">Changed field</th><th className="pb-2 pr-4">Previous</th><th className="pb-2">New</th></tr></thead><tbody>{changedFields.map((field) => <tr className="border-t border-slate-100" key={field}><th className="py-2 pr-4 font-semibold">{titleCase(field)}</th><td className="max-w-xs break-words py-2 pr-4 text-slate-500">{displayValue(event.before_state?.[field])}</td><td className="max-w-xs break-words py-2 text-slate-800">{displayValue(event.after_state?.[field])}</td></tr>)}</tbody></table></div>}
          {Object.keys(event.authorization_context).length > 0 && <details className="mt-4 text-xs text-slate-600"><summary className="font-semibold">Policy and event context</summary><pre className="mt-2 overflow-x-auto rounded-lg bg-slate-900 p-3 text-slate-100">{JSON.stringify(event.authorization_context, null, 2)}</pre></details>}
        </article>
      </li>
    })}</ol>}
  </div>
}
