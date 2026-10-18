import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import type { AdminJob } from '../../api/contracts'
import { useAuth } from '../../auth/AuthContext'
import { ConfirmationDialog } from '../../components/design-system/ConfirmationDialog'
import { FormField, TextInput } from '../../components/design-system/FormElements'
import type { Column } from '../../components/design-system/SearchTable'
import { SearchTable } from '../../components/design-system/SearchTable'
import { StatusBadge } from '../../components/design-system/StatusBadge'
import { useToast } from '../../components/feedback/ToastContext'
import { ArchiveIcon, HistoryIcon, PlusIcon } from '../../components/icons'
import { PageHeader } from '../../components/shell/AppShell'

export function AdminJobsPage() {
  const { token } = useAuth()
  const toast = useToast()
  const [jobs, setJobs] = useState<AdminJob[]>([])
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)

  // Archive modal
  const [archiveTarget, setArchiveTarget] = useState<AdminJob | null>(null)
  const [archiveReason, setArchiveReason] = useState('')
  const [archiving, setArchiving] = useState(false)

  const pageSize = 25

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(search)
      setOffset(0)
      setLoading(true)
    }, 250)
    return () => clearTimeout(handler)
  }, [search])

  const isSearching = loading || search !== debouncedSearch

  useEffect(() => {
    if (!token) return
    let active = true

    api.adminJobs(token, debouncedSearch, offset)
      .then((items) => {
        if (active) {
          setJobs(items)
          setLoading(false)
        }
      })
      .catch(() => {
        if (active) {
          setJobs([])
          setLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [token, debouncedSearch, offset])

  async function reloadJobs() {
    if (!token) return
    setLoading(true)
    try {
      const items = await api.adminJobs(token, search, offset)
      setJobs(items)
    } catch {
      setJobs([])
    } finally {
      setLoading(false)
    }
  }

  async function handleArchive() {
    if (!token || !archiveTarget || !archiveReason.trim()) {
      toast.error('An archive reason is required.')
      return
    }
    setArchiving(true)
    try {
      await api.archiveJob(token, archiveTarget.id, archiveTarget.version, archiveReason.trim())
      toast.success(`Shipment ${archiveTarget.reference} archived.`)
      setArchiveTarget(null)
      setArchiveReason('')
      await reloadJobs()
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Archive failed.')
    } finally {
      setArchiving(false)
    }
  }

  const columns: Column<AdminJob>[] = [
    {
      key: 'reference',
      header: 'Job Reference',
      render: (job) => (
        <div>
          <Link
            to={`/admin/jobs/${job.id}`}
            className="font-mono text-xs font-bold text-maritime-800 hover:text-cyan-700 hover:underline"
          >
            {job.reference}
          </Link>
          <p className="text-[11px] text-slate-400 font-mono">
            Ver. {job.version} {job.archived_at && '· Archived'}
          </p>
        </div>
      ),
    },
    {
      key: 'client',
      header: 'Client / Branch',
      render: (job) => (
        <div>
          <span className="text-xs font-semibold text-slate-800">{job.client_name || job.client_id}</span>
          <p className="text-[11px] text-slate-500">{job.branch_name || job.branch_id}</p>
        </div>
      ),
    },
    {
      key: 'stage',
      header: 'Stage',
      render: (job) => <StatusBadge status={job.stage} size="sm" />,
    },
    {
      key: 'assignments',
      header: 'Responsibility',
      render: (job) => (
        <div className="text-[11px] text-slate-600 space-y-0.5">
          <p>Maker: <span className="font-semibold text-slate-800">{job.maker_user_id ? 'Assigned' : 'Unassigned'}</span></p>
          <p>Checker: <span className="font-semibold text-slate-800">{job.checker_user_id ? 'Assigned' : 'Unassigned'}</span></p>
          <p>Filer: <span className="font-semibold text-slate-800">{job.filing_officer_user_id ? 'Assigned' : 'Unassigned'}</span></p>
        </div>
      ),
    },
    {
      key: 'updated',
      header: 'Last Updated',
      render: (job) => (
        <span className="text-xs text-slate-500">
          {new Date(job.updated_at).toLocaleDateString()}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (job) => (
        <div className="flex items-center gap-2">
          <Link
            to={`/admin/jobs/${job.id}`}
            className="rounded-lg bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-200 transition"
          >
            Manage
          </Link>
          <Link
            to={`/admin/audit/${job.id}`}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition"
            title="View Audit Timeline"
          >
            <HistoryIcon className="h-4 w-4" />
          </Link>
          {!job.archived_at && (
            <button
              type="button"
              onClick={() => {
                setArchiveTarget(job)
                setArchiveReason('')
              }}
              className="rounded-lg p-1 text-rose-500 hover:bg-rose-50 transition"
              title="Archive Shipment"
            >
              <ArchiveIcon className="h-4 w-4" />
            </button>
          )}
        </div>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Admin Directory"
        title="Shipment Operations Registry"
        description="Search, inspect, allocate, and supervise all customs shipments across authorized branches."
        action={
          <Link
            to="/admin/jobs/new"
            className="inline-flex items-center gap-1.5 rounded-xl bg-maritime-800 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-maritime-900 transition"
          >
            <PlusIcon className="h-4 w-4 text-cyan-400" />
            Create Shipment
          </Link>
        }
      />

      <SearchTable
        data={jobs}
        columns={columns}
        keyExtractor={(job) => job.id}
        searchQuery={search}
        onSearchChange={(q) => {
          setSearch(q)
          setOffset(0)
        }}
        searchPlaceholder="Search reference, client, or goods description..."
        isLoading={isSearching}
        hasPrevPage={offset > 0}
        hasNextPage={jobs.length === pageSize}
        onPrevPage={() => {
          setOffset((cur) => Math.max(0, cur - pageSize))
          setLoading(true)
        }}
        onNextPage={() => {
          setOffset((cur) => cur + pageSize)
          setLoading(true)
        }}
        emptyTitle="No shipments found"
        emptyDescription={
          search ? `No shipments matching "${search}".` : 'No shipments currently registered in the database.'
        }
      />

      {/* Archive Modal */}
      <ConfirmationDialog
        open={archiveTarget !== null}
        title="Archive Shipment?"
        message={
          <div className="space-y-3">
            <p>
              Are you sure you want to archive shipment{' '}
              <strong className="font-mono">{archiveTarget?.reference}</strong>?
            </p>
            <FormField label="Required Archive Reason" required>
              <TextInput
                value={archiveReason}
                onChange={(e) => setArchiveReason(e.target.value)}
                placeholder="Reason for archiving..."
              />
            </FormField>
          </div>
        }
        confirmLabel={archiving ? 'Archiving...' : 'Confirm Archive'}
        danger
        onConfirm={() => void handleArchive()}
        onCancel={() => setArchiveTarget(null)}
      />
    </div>
  )
}
