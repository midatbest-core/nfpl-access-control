import { useState } from 'react'
import { api } from '../../api/client'
import type { AuditEvent } from '../../api/contracts'
import { useAuth } from '../../auth/AuthContext'
import { AuditBadge } from '../../components/design-system/AuditBadge'
import { classifyAuditAction } from '../../components/design-system/auditUtils'
import type { Column } from '../../components/design-system/SearchTable'
import { SearchTable } from '../../components/design-system/SearchTable'
import { PageHeader } from '../../components/shell/AppShell'
import { HistoryIcon, SearchIcon } from '../../components/icons'

export function AdminAuditPage() {
  const { token } = useAuth()
  const [jobId, setJobId] = useState('')
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [categoryFilter, setCategoryFilter] = useState<string>('all')

  async function handleSearch(e?: React.FormEvent) {
    if (e) e.preventDefault()
    if (!token || !jobId.trim()) return

    setLoading(true)
    setSearched(true)

    try {
      const results = await api.audit(token, jobId.trim())
      setEvents(results)
    } catch {
      setEvents([])
    } finally {
      setLoading(false)
    }
  }

  const filteredEvents =
    categoryFilter === 'all'
      ? events
      : events.filter((ev) => classifyAuditAction(ev.action) === categoryFilter)

  const columns: Column<AuditEvent>[] = [
    {
      key: 'action',
      header: 'Audit Action & Category',
      render: (ev) => (
        <div className="space-y-1">
          <AuditBadge action={ev.action} denied={ev.denied} />
          <p className="font-mono text-xs font-semibold text-slate-900">{ev.action}</p>
        </div>
      ),
    },
    {
      key: 'actor',
      header: 'Actor',
      render: (ev) => (
        <div>
          <span className="text-xs font-bold text-slate-800">{ev.actor_display_name}</span>
          <p className="font-mono text-[11px] text-slate-400">{ev.actor_user_id}</p>
        </div>
      ),
    },
    {
      key: 'reason',
      header: 'Recorded Justification',
      render: (ev) => (
        <p className="max-w-xs text-xs text-slate-700 leading-relaxed truncate" title={ev.reason}>
          {ev.reason || <span className="italic text-slate-400">Standard transition</span>}
        </p>
      ),
    },
    {
      key: 'version',
      header: 'Version',
      render: (ev) => (
        <span className="font-mono text-xs text-slate-600">
          {ev.affected_job_version ? `v${ev.affected_job_version}` : '—'}
        </span>
      ),
    },
    {
      key: 'timestamp',
      header: 'Recorded Time (UTC)',
      render: (ev) => (
        <span className="text-xs text-slate-500 whitespace-nowrap">
          {new Date(ev.occurred_at).toLocaleString()}
        </span>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Immutable Audit Trail"
        title="Audit Explorer & Compliance History"
        description="Inspect chronological, append-only security logs, access grants, workflow decisions, and denied actions."
      />

      {/* Job Lookup Card */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-4">
        <form onSubmit={handleSearch} className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-slate-400">
              <SearchIcon className="h-4 w-4" />
            </div>
            <input
              type="text"
              value={jobId}
              onChange={(e) => setJobId(e.target.value)}
              placeholder="Enter exact shipment UUID (e.g. from Jobs directory)..."
              className="block w-full rounded-xl border border-slate-300 bg-white py-2.5 pl-10 pr-3.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-cyan-600 focus:ring-3 focus:ring-cyan-100"
            />
          </div>
          <button
            type="submit"
            disabled={!jobId.trim() || loading}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-maritime-800 px-5 py-2.5 text-sm font-semibold text-white shadow-xs hover:bg-maritime-900 disabled:opacity-50 transition"
          >
            <HistoryIcon className="h-4 w-4" />
            Inspect Audit Trail
          </button>
        </form>

        {/* Category Filter Pills */}
        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-100">
          <span className="text-xs font-semibold text-slate-500 mr-1">Filter category:</span>
          {[
            { id: 'all', label: 'All Categories' },
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
                  ? 'bg-slate-900 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Events Table */}
      <SearchTable
        data={filteredEvents}
        columns={columns}
        keyExtractor={(ev) => ev.id}
        isLoading={loading}
        emptyTitle={searched ? 'No audit events found' : 'Enter a shipment UUID above'}
        emptyDescription={
          searched
            ? 'No audit records match the selected category for this shipment.'
            : 'Enter an authorized shipment identifier to inspect its immutable historical events.'
        }
      />
    </div>
  )
}
