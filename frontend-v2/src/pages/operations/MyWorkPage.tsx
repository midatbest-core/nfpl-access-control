import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import type { WorkQueueItem } from '../../api/contracts'
import { useAuth } from '../../auth/AuthContext'
import {
  DirectionBadge,
  ModeBadge,
  ResponsibilityBadge,
  StatusBadge,
} from '../../components/design-system/StatusBadge'
import type { Column } from '../../components/design-system/SearchTable'
import { SearchTable } from '../../components/design-system/SearchTable'
import { CheckCircleIcon } from '../../components/icons'
import { PageHeader } from '../../components/shell/AppShell'

export function MyWorkPage() {
  const { token, user } = useAuth()
  const [items, setItems] = useState<WorkQueueItem[]>([])
  const [count, setCount] = useState<number | undefined>(undefined)
  const [cursor, setCursor] = useState<string | undefined>()
  const [cursorStack, setCursorStack] = useState<Array<string | undefined>>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState<string>('all')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(search)
      setCursor(undefined)
      setCursorStack([])
      setLoading(true)
    }, 250)
    return () => clearTimeout(handler)
  }, [search])

  const isSearching = loading || search !== debouncedSearch

  useEffect(() => {
    if (!token) return
    let active = true

    api.myWork(token, cursor, 20, debouncedSearch)
      .then((res) => {
        if (active) {
          setItems(res.items)
          setCount(res.count)
          setNextCursor(res.next_cursor)
          setLoading(false)
        }
      })
      .catch(() => {
        if (active) {
          setItems([])
          setNextCursor(null)
          setLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [token, cursor, debouncedSearch])

  async function reloadWorkQueue() {
    if (!token) return
    setLoading(true)
    try {
      const res = await api.myWork(token, cursor, 20, search)
      setItems(res.items)
      setCount(res.count)
      setNextCursor(res.next_cursor)
    } catch {
      setItems([])
      setNextCursor(null)
    } finally {
      setLoading(false)
    }
  }

  function handleNext() {
    if (!nextCursor) return
    setCursorStack((prev) => [...prev, cursor])
    setCursor(nextCursor)
    setLoading(true)
  }

  function handlePrev() {
    const prev = cursorStack[cursorStack.length - 1]
    setCursorStack((cur) => cur.slice(0, -1))
    setCursor(prev)
    setLoading(true)
  }

  const filteredItems =
    roleFilter === 'all'
      ? items
      : items.filter((item) => item.responsibility === roleFilter)

  const columns: Column<WorkQueueItem>[] = [
    {
      key: 'reference',
      header: 'Shipment',
      render: (item) => (
        <div>
          <Link
            to={`/work/jobs/${item.job_id}`}
            className="font-mono text-xs font-bold text-maritime-800 hover:text-cyan-700 hover:underline"
          >
            {item.reference}
          </Link>
          <div className="flex items-center gap-1.5 mt-1">
            <DirectionBadge direction={item.direction} />
            <ModeBadge mode={item.mode} />
          </div>
        </div>
      ),
    },
    {
      key: 'client',
      header: 'Client & Branch',
      render: (item) => (
        <div>
          <p className="text-xs font-semibold text-slate-800">{item.client_name}</p>
          <p className="text-[11px] text-slate-500">{item.branch_name}</p>
        </div>
      ),
    },
    {
      key: 'stage',
      header: 'Stage',
      render: (item) => <StatusBadge status={item.stage} size="sm" />,
    },
    {
      key: 'responsibility',
      header: 'Role & Responsibility',
      render: (item) => (
        <div className="space-y-1">
          <ResponsibilityBadge responsibility={item.responsibility} />
          {item.is_delegated && (
            <span className="inline-block rounded-md bg-amber-50 px-1.5 py-0.5 text-[10px] font-bold text-amber-700 border border-amber-200">
              Delegated Cover
            </span>
          )}
        </div>
      ),
    },
    {
      key: 'action',
      header: 'Actionable Step',
      render: (item) => (
        <div>
          <span className="text-xs font-semibold text-cyan-800 bg-cyan-50 px-2 py-0.5 rounded-md border border-cyan-200">
            {item.next_action || 'Pending action'}
          </span>
          {item.feedback && (
            <p className="mt-1 text-[11px] text-amber-900 bg-amber-50 p-1.5 rounded-md border border-amber-200 max-w-xs font-medium">
              Feedback: {item.feedback}
            </p>
          )}
        </div>
      ),
    },
    {
      key: 'open',
      header: 'Action',
      render: (item) => (
        <Link
          to={`/work/jobs/${item.job_id}`}
          className="rounded-lg bg-maritime-800 px-3 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-maritime-900 transition"
        >
          Open Shipment
        </Link>
      ),
    },
  ]

  const filterBar = (
    <div className="flex items-center gap-1.5">
      {[
        { id: 'all', label: 'All Work' },
        { id: 'maker', label: 'Maker' },
        { id: 'checker', label: 'Checker' },
        { id: 'filing_officer', label: 'Filing Officer' },
      ].map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => setRoleFilter(tab.id)}
          className={`rounded-lg px-2.5 py-1.5 text-xs font-semibold transition ${
            roleFilter === tab.id
              ? 'bg-maritime-800 text-white shadow-xs'
              : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <PageHeader
          eyebrow="Operations Workspace"
          title="My Actionable Work Queue"
          description="Only shipments you can act on now are shown. Access is strictly revalidated upon opening."
        />
        <button
          type="button"
          onClick={() => void reloadWorkQueue()}
          disabled={loading}
          className="self-start sm:self-center text-xs font-semibold text-cyan-700 hover:text-cyan-800"
        >
          {loading ? 'Refreshing...' : 'Refresh Queue'}
        </button>
      </div>

      <SearchTable
        data={filteredItems}
        columns={columns}
        keyExtractor={(item) => `${item.job_id}-${item.responsibility}`}
        searchQuery={search}
        onSearchChange={(q) => {
          setSearch(q)
          setCursor(undefined)
          setCursorStack([])
        }}
        searchPlaceholder="Search reference, client, or goods description..."
        filterBar={filterBar}
        totalCount={count}
        isLoading={isSearching}
        hasPrevPage={cursorStack.length > 0}
        hasNextPage={Boolean(nextCursor)}
        onPrevPage={handlePrev}
        onNextPage={handleNext}
        emptyTitle="Your work queue is clear"
        emptyDescription={
          user?.availability !== 'available'
            ? `Your availability is currently set to "${user?.availability}". Set status to "Available" to receive new work assignments.`
            : 'You have no pending shipments requiring preparation, checking, or filing at this time.'
        }
        emptyAction={
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <CheckCircleIcon className="h-4 w-4 text-emerald-500" />
            <span>All assigned responsibilities are up to date</span>
          </div>
        }
      />
    </div>
  )
}
