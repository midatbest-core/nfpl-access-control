import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import type { ClientJobDetail, ClientShipmentStatus, ClientUpdate } from '../../api/contracts'
import { useAuth } from '../../auth/AuthContext'
import { FormField, SelectInput, TextareaInput } from '../../components/design-system/FormElements'
import { SkeletonMetricsGrid } from '../../components/design-system/LoadingSkeleton'
import { DirectionBadge, ModeBadge, StatusBadge } from '../../components/design-system/StatusBadge'
import { useToast } from '../../components/feedback/ToastContext'
import { ArrowLeftIcon, HelpCircleIcon, HistoryIcon, SendIcon } from '../../components/icons'
import { PageHeader } from '../../components/shell/AppShell'

export function ClientShipmentDetailPage() {
  const { jobId = '' } = useParams<{ jobId: string }>()
  const { token } = useAuth()
  const toast = useToast()

  const [detail, setDetail] = useState<ClientJobDetail | null>(null)
  const [status, setStatus] = useState<ClientShipmentStatus | null>(null)
  const [history, setHistory] = useState<ClientUpdate[]>([])
  const [beforeVersion, setBeforeVersion] = useState<number | undefined>()
  const [historyStack, setHistoryStack] = useState<Array<number | undefined>>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Query form state
  const [queryCategory, setQueryCategory] = useState('delay')
  const [queryExplanation, setQueryExplanation] = useState('')
  const [queryReceipt, setQueryReceipt] = useState<string | null>(null)
  const [submittingQuery, setSubmittingQuery] = useState(false)

  useEffect(() => {
    if (!token || !jobId) return
    let active = true

    Promise.all([
      api.clientJob(token, jobId),
      api.clientStatus(token, jobId),
      api.clientHistory(token, jobId, beforeVersion),
    ])
      .then(([jobData, statusData, historyData]) => {
        if (active) {
          setDetail(jobData)
          setStatus(statusData)
          setHistory(historyData)
          setLoading(false)
        }
      })
      .catch((caught: Error) => {
        if (active) {
          setError(caught.message)
          setLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [jobId, token, beforeVersion])

  async function handleSubmitQuery(e: React.FormEvent) {
    e.preventDefault()
    if (!token || !jobId) return
    if (!queryExplanation.trim()) {
      toast.error('Please enter an explanation of your concern.')
      return
    }

    setSubmittingQuery(true)
    try {
      const receipt = await api.clientQuery(token, jobId, queryCategory, queryExplanation.trim())
      setQueryReceipt(
        `Your inquiry was recorded and dispatched to ${receipt.delivered} authorized operations administrator${
          receipt.delivered === 1 ? '' : 's'
        }.`
      )
      setQueryExplanation('')
      toast.success('Inquiry delivered to operations administration.')
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Inquiry could not be sent.')
    } finally {
      setSubmittingQuery(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <SkeletonMetricsGrid />
      </div>
    )
  }

  if (!detail || !status) {
    return (
      <div className="space-y-4">
        <Link to="/client/shipments" className="text-xs font-semibold text-slate-500 hover:text-slate-800">
          &larr; Back to shipments
        </Link>
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-xs text-rose-800">
          {error ?? 'This shipment is not available to your authorized client organization.'}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Back button */}
      <div>
        <Link
          to="/client/shipments"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 transition"
        >
          <ArrowLeftIcon className="h-4 w-4" />
          Back to Shipments Portal
        </Link>
      </div>

      <PageHeader
        eyebrow="Sanitized Client Tracking"
        title={detail.reference}
        description="Live clearance progress and milestone history. Internal staff assignments remain confidential."
      />

      {/* Status & Progress Overview */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-base font-black text-slate-900">{detail.reference}</span>
            <StatusBadge status={status.stage} />
            <DirectionBadge direction={detail.direction} />
            <ModeBadge mode={detail.mode} />
          </div>
          <span className="text-xs text-slate-400 font-mono">
            Last Updated: {new Date(status.updated_at).toLocaleString()}
          </span>
        </div>

        {/* Clearance Progress Bar */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-700">
            <span>Overall Clearance Milestone Progression</span>
            <span className="font-bold text-cyan-800">{status.progress_percent}% Complete</span>
          </div>
          <div className="h-3 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-cyan-600 transition-all duration-500"
              style={{ width: `${Math.min(100, Math.max(0, status.progress_percent))}%` }}
            />
          </div>
        </div>
      </div>

      {/* Inquiry Form to Admin */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
        <div className="flex items-center gap-3 border-b border-slate-100 pb-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-cyan-50 text-cyan-700">
            <HelpCircleIcon className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900">Inquire About This Shipment</h3>
            <p className="text-xs text-slate-500">
              Raise a shipment-specific concern directly to customs operations management.
            </p>
          </div>
        </div>

        {queryReceipt && (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-xs font-semibold text-emerald-800">
            {queryReceipt}
          </div>
        )}

        <form onSubmit={handleSubmitQuery} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <FormField label="Concern Category" required>
              <SelectInput
                value={queryCategory}
                onChange={(e) => setQueryCategory(e.target.value)}
              >
                <option value="delay">Customs Clearance Delay</option>
                <option value="cancellation">Cancellation Inquiry</option>
                <option value="reopening">Reopening Request</option>
                <option value="missing_update">Missing Status Update</option>
                <option value="other">Other Inquiry</option>
              </SelectInput>
            </FormField>

            <div className="sm:col-span-2">
              <FormField
                label="Explanation & Questions"
                required
                helperText="Provide reference details or questions for operations administration."
              >
                <TextareaInput
                  value={queryExplanation}
                  onChange={(e) => setQueryExplanation(e.target.value)}
                  placeholder="Explain your shipment inquiry..."
                />
              </FormField>
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={submittingQuery}
              className="inline-flex items-center gap-1.5 rounded-xl bg-maritime-800 px-5 py-2.5 text-xs font-semibold text-white shadow-xs hover:bg-maritime-900 disabled:opacity-50 transition"
            >
              <SendIcon className="h-4 w-4 text-cyan-400" />
              {submittingQuery ? 'Delivering Inquiry...' : 'Send Inquiry to Admin'}
            </button>
          </div>
        </form>
      </div>

      {/* Sanitized Milestone History */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
        <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
          <HistoryIcon className="h-4 w-4 text-slate-400" />
          <h3 className="text-sm font-bold text-slate-900">Milestone Progress Feed</h3>
        </div>

        {history.length === 0 ? (
          <p className="text-xs text-slate-500 py-3">No client-visible milestone updates recorded yet.</p>
        ) : (
          <div className="space-y-3">
            {history.map((it) => (
              <div
                key={it.cursor}
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 rounded-xl border border-slate-100 bg-slate-50/70 p-3.5"
              >
                <div className="flex items-center gap-2.5">
                  <StatusBadge status={it.stage} size="sm" />
                  <p className="text-xs font-semibold text-slate-800">{it.message}</p>
                </div>
                <time className="text-[11px] text-slate-400 font-mono">
                  {new Date(it.occurred_at).toLocaleString()}
                </time>
              </div>
            ))}
          </div>
        )}

        {/* Keyset Pagination for History */}
        <div className="flex items-center justify-between pt-3 border-t border-slate-100">
          <button
            type="button"
            disabled={historyStack.length === 0}
            onClick={() => {
              const prev = historyStack[historyStack.length - 1]
              setHistoryStack((cur) => cur.slice(0, -1))
              setBeforeVersion(prev)
            }}
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40 transition"
          >
            Newer Updates
          </button>
          <button
            type="button"
            disabled={history.length < 25}
            onClick={() => {
              const last = history[history.length - 1]
              if (!last) return
              setHistoryStack((cur) => [...cur, beforeVersion])
              setBeforeVersion(last.version)
            }}
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40 transition"
          >
            Older Updates
          </button>
        </div>
      </div>
    </div>
  )
}
