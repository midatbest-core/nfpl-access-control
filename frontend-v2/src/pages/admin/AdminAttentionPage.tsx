import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import type { AttentionJob } from '../../api/contracts'
import { useAuth } from '../../auth/AuthContext'
import type { Column } from '../../components/design-system/SearchTable'
import { SearchTable } from '../../components/design-system/SearchTable'
import { StatusBadge } from '../../components/design-system/StatusBadge'
import { PageHeader } from '../../components/shell/AppShell'

export function AdminAttentionPage() {
  const { token } = useAuth()
  const [jobs, setJobs] = useState<AttentionJob[]>([])
  const [cursor, setCursor] = useState<string | undefined>()
  const [cursorStack, setCursorStack] = useState<Array<string | undefined>>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!token) return
    let active = true

    api.attentionJobs(token, cursor)
      .then((res) => {
        if (active) {
          setJobs(res.items)
          setNextCursor(res.next_cursor)
          setLoading(false)
        }
      })
      .catch(() => {
        if (active) {
          setJobs([])
          setNextCursor(null)
          setLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [token, cursor])

  function handleNext() {
    if (!nextCursor) return
    setCursorStack((prev) => [...prev, cursor])
    setCursor(nextCursor)
  }

  function handlePrev() {
    const prev = cursorStack[cursorStack.length - 1]
    setCursorStack((cur) => cur.slice(0, -1))
    setCursor(prev)
  }

  const columns: Column<AttentionJob>[] = [
    {
      key: 'reference',
      header: 'Shipment Reference',
      render: (job) => (
        <div>
          <Link
            to={`/admin/jobs/${job.job_id}`}
            className="font-mono text-xs font-bold text-maritime-800 hover:text-cyan-700 hover:underline"
          >
            {job.reference}
          </Link>
          <p className="text-[11px] text-slate-400 font-mono">Ver. {job.version}</p>
        </div>
      ),
    },
    {
      key: 'client',
      header: 'Client / Branch',
      render: (job) => (
        <div>
          <span className="text-xs font-semibold text-slate-800">{job.client_name}</span>
          <p className="text-[11px] text-slate-500">{job.branch_name}</p>
        </div>
      ),
    },
    {
      key: 'stage',
      header: 'Stage',
      render: (job) => <StatusBadge status={job.stage} size="sm" />,
    },
    {
      key: 'reasons',
      header: 'Flags & Unresolved Concerns',
      render: (job) => (
        <div className="flex flex-col gap-1 max-w-sm">
          {job.reasons.map((r, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1.5 rounded-md bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-900 border border-amber-200"
            >
              <span className="text-amber-500 font-bold">!</span>
              {r}
            </span>
          ))}
        </div>
      ),
    },
    {
      key: 'action',
      header: 'Action',
      render: (job) => (
        <Link
          to={`/admin/jobs/${job.job_id}`}
          className="rounded-lg bg-maritime-800 px-3 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-maritime-900 transition"
        >
          Resolve Assignments
        </Link>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Supervision Queue"
        title="Jobs Requiring Attention"
        description="Shipments blocked by employee absence, unassigned responsibilities, or pending correction loops."
      />

      <SearchTable
        data={jobs}
        columns={columns}
        keyExtractor={(job) => job.job_id}
        isLoading={loading}
        hasPrevPage={cursorStack.length > 0}
        hasNextPage={Boolean(nextCursor)}
        onPrevPage={handlePrev}
        onNextPage={handleNext}
        emptyTitle="No jobs currently requiring attention"
        emptyDescription="All active shipments have valid, present operational assignees and are proceeding normally."
      />
    </div>
  )
}
