import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import type { AuditEvent, Job } from '../../api/contracts'
import { useAuth } from '../../auth/AuthContext'
import { AuditBadge } from '../../components/design-system/AuditBadge'
import { classifyAuditAction } from '../../components/design-system/auditUtils'
import { EmptyState } from '../../components/design-system/EmptyState'
import { SkeletonMetricsGrid } from '../../components/design-system/LoadingSkeleton'
import { StatusBadge } from '../../components/design-system/StatusBadge'
import { ArrowLeftIcon } from '../../components/icons'
import { PageHeader } from '../../components/shell/AppShell'

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'None'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function extractChanges(event: AuditEvent): string[] {
  if (!event.before_state && !event.after_state) return []
  const keys = new Set([
    ...Object.keys(event.before_state ?? {}),
    ...Object.keys(event.after_state ?? {}),
  ])
  return [...keys].filter(
    (key) => JSON.stringify(event.before_state?.[key]) !== JSON.stringify(event.after_state?.[key])
  )
}

export function AdminAuditDetailPage() {
  const { jobId = '' } = useParams<{ jobId: string }>()
  const { token } = useAuth()
  const [job, setJob] = useState<Job | null>(null)
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [categoryFilter, setCategoryFilter] = useState('all')

  useEffect(() => {
    if (!token || !jobId) return
    let active = true

    Promise.all([api.job(token, jobId), api.audit(token, jobId)])
      .then(([shipment, auditEvents]) => {
        if (active) {
          setJob(shipment)
          setEvents([...auditEvents].reverse())
          setLoading(false)
        }
      })
      .catch((err: Error) => {
        if (active) {
          setError(err.message)
          setLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [jobId, token])

  const filteredEvents =
    categoryFilter === 'all'
      ? events
      : events.filter((ev) => classifyAuditAction(ev.action) === categoryFilter)

  return (
    <div className="space-y-6">
      {/* Navigation Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <Link
          to="/admin/audit"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 transition"
        >
          <ArrowLeftIcon className="h-4 w-4" />
          Back to Audit Explorer
        </Link>
        {job && (
          <Link
            to={`/admin/jobs/${job.id}`}
            className="text-xs font-semibold text-cyan-700 hover:underline"
          >
            Manage Shipment Record &rarr;
          </Link>
        )}
      </div>

      <PageHeader
        eyebrow="Immutable Compliance Timeline"
        title={job ? `Audit Trail: ${job.reference}` : 'Shipment Audit Timeline'}
        description="Chronological, append-only record of every workflow mutation, state transition, access evaluation, and denied request."
      />

      {error && (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-xs font-semibold text-rose-800">
          {error}
        </div>
      )}

      {loading ? (
        <SkeletonMetricsGrid />
      ) : events.length === 0 ? (
        <EmptyState
          title="No Audit Events Recorded"
          description="There are no authorized audit records available for this shipment."
        />
      ) : (
        <div className="space-y-6">
          {/* Shipment Summary Card */}
          {job && (
            <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
              <div className="flex flex-wrap items-center gap-3">
                <span className="font-mono text-sm font-black text-slate-900">{job.reference}</span>
                <StatusBadge status={job.stage} />
                <span className="text-xs text-slate-500">
                  {job.client_name} · {job.branch_name}
                </span>
              </div>
              <span className="font-mono text-xs text-slate-400">
                Current Version: <strong className="text-slate-700">{job.version}</strong>
              </span>
            </div>
          )}

          {/* Category Filter Bar */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-slate-500 mr-1">Filter Timeline:</span>
            {[
              { id: 'all', label: 'All Events' },
              { id: 'workflow', label: 'Workflow' },
              { id: 'access', label: 'Role & Policy' },
              { id: 'responsibility', label: 'Responsibility' },
              { id: 'exception', label: 'Exceptions' },
              { id: 'security', label: 'Security & Auth' },
            ].map((cat) => (
              <button
                key={cat.id}
                type="button"
                onClick={() => setCategoryFilter(cat.id)}
                className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition ${
                  categoryFilter === cat.id
                    ? 'bg-maritime-800 text-white'
                    : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>

          {/* Chronological Timeline */}
          <div className="relative border-l-2 border-slate-200 ml-4 pl-6 space-y-6">
            {filteredEvents.map((ev) => {
              const changedFields = extractChanges(ev)
              return (
                <div key={ev.id} className="relative">
                  {/* Timeline Dot */}
                  <div
                    className={`absolute -left-[31px] top-1.5 h-4 w-4 rounded-full border-2 border-white ${
                      ev.denied ? 'bg-rose-500' : 'bg-cyan-600'
                    }`}
                  />

                  {/* Event Card */}
                  <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-3">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
                      <div className="flex items-center gap-2">
                        <AuditBadge action={ev.action} denied={ev.denied} />
                        <span className="font-mono text-xs font-bold text-slate-900">
                          {ev.action}
                        </span>
                      </div>
                      <time className="text-xs text-slate-400 font-mono">
                        {new Date(ev.occurred_at).toLocaleString()}
                      </time>
                    </div>

                    <div className="grid gap-2 sm:grid-cols-2 text-xs">
                      <div>
                        <span className="text-[11px] font-bold text-slate-400 uppercase">Actor:</span>
                        <p className="font-semibold text-slate-800">
                          {ev.actor_display_name}{' '}
                          <span className="text-[11px] font-mono text-slate-400">({ev.actor_user_id})</span>
                        </p>
                      </div>

                      <div>
                        <span className="text-[11px] font-bold text-slate-400 uppercase">Job Version:</span>
                        <p className="font-mono font-semibold text-slate-800">
                          {ev.affected_job_version ? `v${ev.affected_job_version}` : 'N/A'}
                        </p>
                      </div>

                      <div className="sm:col-span-2">
                        <span className="text-[11px] font-bold text-slate-400 uppercase">Justification:</span>
                        <p className="mt-0.5 text-slate-700 italic">
                          "{ev.reason || 'Standard operational transition'}"
                        </p>
                      </div>
                    </div>

                    {/* Before vs After Diff Table */}
                    {changedFields.length > 0 && (
                      <div className="mt-3 overflow-x-auto rounded-xl border border-slate-100 bg-slate-50/70 p-3">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-2 block">
                          State Mutation Diffs
                        </span>
                        <table className="w-full text-left text-xs">
                          <thead>
                            <tr className="border-b border-slate-200 text-slate-400">
                              <th className="pb-1.5 font-bold">Field</th>
                              <th className="pb-1.5 font-bold">Previous Value</th>
                              <th className="pb-1.5 font-bold">Mutated Value</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {changedFields.map((field) => (
                              <tr key={field}>
                                <td className="py-1.5 font-semibold font-mono text-slate-700">{field}</td>
                                <td className="py-1.5 text-slate-500 font-mono text-[11px]">
                                  {displayValue(ev.before_state?.[field])}
                                </td>
                                <td className="py-1.5 font-bold font-mono text-[11px] text-cyan-800">
                                  {displayValue(ev.after_state?.[field])}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}

                    {/* Authorization & Security Policy Context */}
                    {Object.keys(ev.authorization_context).length > 0 && (
                      <details className="text-xs text-slate-600 pt-1">
                        <summary className="font-semibold text-slate-500 hover:text-slate-800 cursor-pointer">
                          View Authorization & Scope Context
                        </summary>
                        <pre className="mt-2 overflow-x-auto rounded-xl bg-slate-900 p-3.5 text-[11px] font-mono text-cyan-300">
                          {JSON.stringify(ev.authorization_context, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
