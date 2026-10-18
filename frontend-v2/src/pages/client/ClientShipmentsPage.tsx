import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import type { ClientShipmentSummary } from '../../api/contracts'
import { useAuth } from '../../auth/AuthContext'
import { DirectionBadge, ModeBadge, StatusBadge } from '../../components/design-system/StatusBadge'
import type { Column } from '../../components/design-system/SearchTable'
import { SearchTable } from '../../components/design-system/SearchTable'
import { PageHeader } from '../../components/shell/AppShell'

export function ClientShipmentsPage() {
  const { token } = useAuth()
  const [shipments, setShipments] = useState<ClientShipmentSummary[]>([])
  const [cursor, setCursor] = useState<string | undefined>()
  const [cursorStack, setCursorStack] = useState<Array<string | undefined>>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!token) return
    let active = true

    api.clientJobs(token, cursor, 25, search)
      .then((res) => {
        if (active) {
          setShipments(res.items)
          setNextCursor(res.next_cursor)
          setLoading(false)
        }
      })
      .catch(() => {
        if (active) {
          setShipments([])
          setNextCursor(null)
          setLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [token, cursor, search])

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

  const columns: Column<ClientShipmentSummary>[] = [
    {
      key: 'reference',
      header: 'Shipment Reference',
      render: (s) => (
        <div>
          <Link
            to={`/client/shipments/${s.job_id}`}
            className="font-mono text-xs font-bold text-maritime-800 hover:text-cyan-700 hover:underline"
          >
            {s.reference}
          </Link>
          <div className="flex items-center gap-1.5 mt-1">
            <DirectionBadge direction={s.direction} />
            <ModeBadge mode={s.mode} />
          </div>
        </div>
      ),
    },
    {
      key: 'stage',
      header: 'Status & Stage',
      render: (s) => <StatusBadge status={s.stage} size="sm" />,
    },
    {
      key: 'progress',
      header: 'Customs Clearance Progress',
      render: (s) => (
        <div className="w-44 space-y-1">
          <div className="flex items-center justify-between text-[11px] font-semibold text-slate-600">
            <span>Progress</span>
            <span>{s.progress_percent}%</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-cyan-600 transition-all duration-300"
              style={{ width: `${Math.min(100, Math.max(0, s.progress_percent))}%` }}
            />
          </div>
        </div>
      ),
    },
    {
      key: 'updated',
      header: 'Last Update',
      render: (s) => (
        <span className="text-xs text-slate-500">
          {new Date(s.updated_at).toLocaleDateString()}
        </span>
      ),
    },
    {
      key: 'action',
      header: 'Action',
      render: (s) => (
        <Link
          to={`/client/shipments/${s.job_id}`}
          className="rounded-lg bg-maritime-800 px-3 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-maritime-900 transition"
        >
          Track & Inquire
        </Link>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Client Tracking Portal"
        title="My Shipments & Freight"
        description="Real-time customs clearance milestones and status tracking for your authorized shipments."
      />

      <SearchTable
        data={shipments}
        columns={columns}
        keyExtractor={(s) => s.job_id}
        searchQuery={search}
        onSearchChange={(q) => {
          setSearch(q)
          setCursor(undefined)
          setCursorStack([])
        }}
        searchPlaceholder="Filter shipments by reference or description..."
        isLoading={loading}
        hasPrevPage={cursorStack.length > 0}
        hasNextPage={Boolean(nextCursor)}
        onPrevPage={handlePrev}
        onNextPage={handleNext}
        emptyTitle="No shipments found"
        emptyDescription={
          search
            ? `No shipments matching "${search}".`
            : 'There are currently no shipments associated with your client account.'
        }
      />
    </div>
  )
}
