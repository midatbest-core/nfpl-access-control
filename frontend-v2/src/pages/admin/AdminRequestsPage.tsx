import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import type { AbsenceOutcome, Suggestion, UrgentRequest } from '../../api/contracts'
import { useAuth } from '../../auth/AuthContext'
import { ConfirmationDialog } from '../../components/design-system/ConfirmationDialog'
import { FormField, SelectInput, TextInput } from '../../components/design-system/FormElements'
import { useToast } from '../../components/feedback/ToastContext'
import { CheckCircle2Icon, XCircleIcon } from '../../components/icons'
import { PageHeader } from '../../components/shell/AppShell'

export function AdminRequestsPage() {
  const { token } = useAuth()
  const toast = useToast()
  const [requests, setRequests] = useState<UrgentRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Decision Modal State
  const [selectedRequest, setSelectedRequest] = useState<{
    item: UrgentRequest
    approved: boolean
  } | null>(null)
  const [decisionReason, setDecisionReason] = useState('')
  const [deciding, setDeciding] = useState(false)

  // Absence outcomes resolution state
  const [outcomes, setOutcomes] = useState<AbsenceOutcome[]>([])
  const [outcomeSuggestions, setOutcomeSuggestions] = useState<Record<string, Suggestion[]>>({})
  const [replacementUser, setReplacementUser] = useState<Record<string, string>>({})
  const [overrideReason, setOverrideReason] = useState<Record<string, string>>({})
  const [overridingId, setOverridingId] = useState<string | null>(null)

  useEffect(() => {
    if (!token) return
    let active = true

    api.urgentRequests(token)
      .then((items) => {
        if (active) {
          setRequests(items)
          setError(null)
          setLoading(false)
        }
      })
      .catch((err: Error) => {
        if (active) {
          setRequests([])
          setError(err.message)
          setLoading(false)
        }
      })

    function handleRefresh() {
      if (active && token) {
        api.urgentRequests(token)
          .then((items) => {
            if (active) setRequests(items)
          })
          .catch(() => {})
      }
    }
    window.addEventListener('nfpl:refresh-notifications', handleRefresh)

    return () => {
      active = false
      window.removeEventListener('nfpl:refresh-notifications', handleRefresh)
    }
  }, [token])

  async function reloadRequests() {
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      const items = await api.urgentRequests(token)
      setRequests(items)
    } catch (err) {
      setRequests([])
      setError(err instanceof Error ? err.message : 'Failed to reload requests')
    } finally {
      setLoading(false)
    }
  }

  async function loadOutcomes(nominationId: string) {
    if (!token) return
    try {
      const items = await api.absenceOutcomes(token, nominationId)
      setOutcomes(items)
      const flagged = items.filter((it) => !['delegated', 'overridden'].includes(it.outcome))
      const entries = await Promise.all(
        flagged.map(async (it) => {
          const suggestions = await api.suggestions(token, it.job_id)
          return [it.id, suggestions[it.responsibility] ?? []] as const
        })
      )
      setOutcomeSuggestions(Object.fromEntries(entries))
    } catch {
      // outcomes optional
    }
  }

  async function handleDecision() {
    if (!token || !selectedRequest) return
    if (!decisionReason.trim() && selectedRequest.item.request_type !== 'exceptional_transition') {
      toast.error('An audited decision reason is required.')
      return
    }

    setDeciding(true)
    const { item, approved } = selectedRequest

    try {
      if (item.request_type === 'absence_nomination') {
        await api.absenceDecision(token, item.request_id, item.version, approved, decisionReason.trim())
        if (approved) {
          await loadOutcomes(item.request_id)
        }
      } else if (item.request_type === 'edit_request') {
        await api.editDecision(token, item.request_id, item.version, approved, decisionReason.trim())
      } else {
        if (!approved) {
          toast.error('Exceptional transitions support approval only.')
          setDeciding(false)
          return
        }
        await api.exceptionApproval(token, item.request_id, item.version)
      }

      toast.success(`Request ${approved ? 'approved' : 'rejected'} successfully.`)
      window.dispatchEvent(new CustomEvent('nfpl:refresh-notifications'))
      setSelectedRequest(null)
      setDecisionReason('')
      await reloadRequests()
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Decision failed.')
      setSelectedRequest(null)
      setDecisionReason('')
      await reloadRequests()
    } finally {
      setDeciding(false)
    }
  }

  async function handleOverride(outcome: AbsenceOutcome) {
    if (!token) return
    const userId = replacementUser[outcome.id]
    const reason = overrideReason[outcome.id]?.trim()
    if (!userId || !reason) {
      toast.error('Choose an eligible replacement and provide an override reason.')
      return
    }

    setOverridingId(outcome.id)
    try {
      const updated = await api.overrideAbsenceOutcome(token, outcome.id, userId, reason)
      setOutcomes((prev) => prev.map((o) => (o.id === updated.id ? updated : o)))
      toast.success('Absence outcome overridden and delegated.')
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Override failed.')
    } finally {
      setOverridingId(null)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Independent Approvals"
        title="Urgent & Exception Requests"
        description="Pending Maker correction requests, absence replacement decisions, and exceptional transitions."
      />

      {loading ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-xs text-slate-500">
          Loading pending urgent requests...
        </div>
      ) : error ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-xs text-rose-800 shadow-xs flex items-center justify-between">
          <span>Failed to load urgent requests: {error}</span>
          <button
            type="button"
            onClick={reloadRequests}
            className="rounded-lg bg-rose-800 px-3 py-1.5 text-xs font-semibold text-white hover:bg-rose-900 transition"
          >
            Retry
          </button>
        </div>
      ) : requests.length === 0 ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center shadow-xs">
          <p className="text-sm font-bold text-slate-900">No urgent requests pending</p>
          <p className="mt-1 text-xs text-slate-500">
            All exceptional transition requests and employee absence nominations have been reviewed.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {requests.map((req) => (
            <div
              key={req.request_id}
              className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-xs hover:border-slate-300 transition"
            >
              <div className="space-y-1.5 max-w-xl">
                <div className="flex items-center gap-2">
                  <span className="rounded-md bg-amber-50 px-2 py-0.5 text-xs font-bold uppercase tracking-wider text-amber-800 border border-amber-200">
                    {req.request_type.replace(/_/g, ' ')}
                  </span>
                  <span className="text-[11px] text-slate-400 font-mono">
                    Req Ver. {req.version} · {new Date(req.requested_at).toLocaleString()}
                  </span>
                </div>
                <p className="text-xs text-slate-700 font-medium">"{req.reason}"</p>
                <div className="flex items-center gap-3 text-[11px] text-slate-500">
                  <span>Requester: <strong className="font-mono text-slate-700">{req.requester_user_id.slice(0, 8)}...</strong></span>
                  {req.job_id && (
                    <Link
                      to={`/admin/jobs/${req.job_id}`}
                      className="text-cyan-700 hover:underline font-semibold"
                    >
                      View Associated Shipment &rarr;
                    </Link>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2 self-start sm:self-center">
                <button
                  type="button"
                  onClick={() => {
                    setSelectedRequest({ item: req, approved: true })
                    setDecisionReason('')
                  }}
                  className="inline-flex items-center gap-1 rounded-xl bg-emerald-700 px-3.5 py-2 text-xs font-semibold text-white shadow-xs hover:bg-emerald-800 transition"
                >
                  <CheckCircle2Icon className="h-4 w-4" />
                  Approve
                </button>
                {req.request_type !== 'exceptional_transition' && (
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedRequest({ item: req, approved: false })
                      setDecisionReason('')
                    }}
                    className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-rose-700 shadow-2xs hover:bg-rose-50 hover:border-rose-200 transition"
                  >
                    <XCircleIcon className="h-4 w-4" />
                    Reject
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Flagged Absence Outcomes Resolution */}
      {outcomes.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-4 mt-8">
          <div className="border-b border-slate-100 pb-3">
            <h3 className="text-sm font-bold text-slate-900">Absence Transfer Results</h3>
            <p className="text-xs text-slate-500">
              Eligible jobs were transferred automatically. Review and override any flagged jobs below.
            </p>
          </div>

          <div className="space-y-3">
            {outcomes.map((item) => (
              <div
                key={item.id}
                className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 space-y-3"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Link
                      to={`/admin/jobs/${item.job_id}`}
                      className="font-mono text-xs font-bold text-cyan-700 hover:underline"
                    >
                      Job {item.job_id.slice(0, 8)}...
                    </Link>
                    <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-bold text-slate-700 uppercase">
                      {item.outcome}
                    </span>
                  </div>
                  <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    {item.responsibility.replace('_', ' ')}
                  </span>
                </div>

                <p className="text-xs text-slate-600">{item.reason}</p>

                {!['delegated', 'overridden'].includes(item.outcome) && (
                  <div className="grid gap-3 sm:grid-cols-2 pt-2 border-t border-slate-200">
                    <FormField label="Eligible Replacement">
                      <SelectInput
                        value={replacementUser[item.id] ?? ''}
                        onChange={(e) =>
                          setReplacementUser((prev) => ({ ...prev, [item.id]: e.target.value }))
                        }
                      >
                        <option value="">Select Replacement</option>
                        {outcomeSuggestions[item.id]?.map((opt) => (
                          <option key={opt.user_id} value={opt.user_id}>
                            {opt.display_name} ({opt.pending_workload} active)
                          </option>
                        ))}
                      </SelectInput>
                    </FormField>

                    <FormField label="Override Reason">
                      <TextInput
                        value={overrideReason[item.id] ?? ''}
                        onChange={(e) =>
                          setOverrideReason((prev) => ({ ...prev, [item.id]: e.target.value }))
                        }
                        placeholder="Reason for manual override..."
                      />
                    </FormField>

                    <div className="sm:col-span-2 flex justify-end">
                      <button
                        type="button"
                        disabled={overridingId === item.id}
                        onClick={() => void handleOverride(item)}
                        className="rounded-xl bg-maritime-800 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-maritime-900 disabled:opacity-50 transition"
                      >
                        {overridingId === item.id ? 'Overriding...' : 'Override Job Delegation'}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Decision Confirmation Dialog */}
      <ConfirmationDialog
        open={selectedRequest !== null}
        title={`${selectedRequest?.approved ? 'Approve' : 'Reject'} ${selectedRequest?.item.request_type.replace(/_/g, ' ')}?`}
        message={
          <div className="space-y-3">
            <p>
              Please enter your audited justification reason for this independent administrative decision.
            </p>
            <FormField label="Decision Justification" required>
              <TextInput
                value={decisionReason}
                onChange={(e) => setDecisionReason(e.target.value)}
                placeholder="Audited reason for approval/rejection..."
              />
            </FormField>
          </div>
        }
        confirmLabel={deciding ? 'Recording...' : selectedRequest?.approved ? 'Confirm Approval' : 'Confirm Rejection'}
        danger={!selectedRequest?.approved}
        onConfirm={() => void handleDecision()}
        onCancel={() => setSelectedRequest(null)}
      />
    </div>
  )
}
