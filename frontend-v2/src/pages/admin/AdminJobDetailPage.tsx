import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import type { Job, JobResponsibilityDetail } from '../../api/contracts'
import { SEEDED_STAFF_DIRECTORY, type StaffMember } from '../../api/staffDirectory'
import { useAuth } from '../../auth/AuthContext'
import { AssignmentSuggestions } from '../../components/admin/AssignmentSuggestions'
import { ConfirmationDialog } from '../../components/design-system/ConfirmationDialog'
import { FormField, SelectInput, TextInput, TextareaInput } from '../../components/design-system/FormElements'
import { SkeletonMetricsGrid } from '../../components/design-system/LoadingSkeleton'
import { DirectionBadge, ModeBadge, StatusBadge } from '../../components/design-system/StatusBadge'
import { useToast } from '../../components/feedback/ToastContext'
import {
  AlertTriangleIcon,
  ArrowLeftIcon,
  BellIcon,
  HistoryIcon,
  ShieldAlertIcon,
  UserCheckIcon,
} from '../../components/icons'
import { PageHeader } from '../../components/shell/AppShell'

const ROLE_TITLES: Record<'maker' | 'checker' | 'filing_officer', string> = {
  maker: 'Maker (Preparation)',
  checker: 'Checker (Verification)',
  filing_officer: 'Filing Officer (Customs Filing)',
}

export function AdminJobDetailPage() {
  const { jobId = '' } = useParams<{ jobId: string }>()
  const { token } = useAuth()
  const toast = useToast()

  const [job, setJob] = useState<Job | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Actions state
  const [cancelReason, setCancelReason] = useState('')
  const [confirmCancel, setConfirmCancel] = useState(false)
  const [cancelling, setCancelling] = useState(false)

  // Exceptional transition
  const [exceptionAction, setExceptionAction] = useState<'cancel' | 'reopen'>('cancel')
  const [exceptionReason, setExceptionReason] = useState('')
  const [confirmException, setConfirmException] = useState(false)
  const [requestingException, setRequestingException] = useState(false)

  // Staff Attention Notification
  const [attentionReason, setAttentionReason] = useState('')
  const [sendingAttention, setSendingAttention] = useState(false)

  // Per-job Delegation
  const [delegationRole, setDelegationRole] = useState<'maker' | 'checker' | 'filing_officer'>('maker')
  const [delegateUserId, setDelegateUserId] = useState('')
  const [isCustomDelegate, setIsCustomDelegate] = useState(false)
  const [customDelegateId, setCustomDelegateId] = useState('')
  const [delegationFrom, setDelegationFrom] = useState('')
  const [delegationUntil, setDelegationUntil] = useState('')
  const [delegationReason, setDelegationReason] = useState('')
  const [submittingDelegation, setSubmittingDelegation] = useState(false)
  const [assigningDirectly, setAssigningDirectly] = useState(false)
  const [responsibilities, setResponsibilities] = useState<JobResponsibilityDetail[]>([])

  const effectiveDelegateId = isCustomDelegate ? customDelegateId.trim() : delegateUserId.trim()
  const selectedDelegate = useMemo(
    () => SEEDED_STAFF_DIRECTORY.find((s) => s.id === effectiveDelegateId),
    [effectiveDelegateId]
  )
  const selectedDelegateName = selectedDelegate?.name || (isCustomDelegate && effectiveDelegateId ? `User (${effectiveDelegateId.slice(0, 8)}...)` : '')

  const currentAssignee = useMemo(() => {
    return responsibilities.find((r) => r.responsibility === delegationRole && r.user_id) || null
  }, [responsibilities, delegationRole])

  useEffect(() => {
    if (!token || !jobId) return
    let active = true

    Promise.all([
      api.job(token, jobId),
      api.jobResponsibilities(token, jobId).catch(() => []),
    ])
      .then(([jobData, respData]) => {
        if (active) {
          setJob(jobData)
          setResponsibilities(respData)
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
  }, [jobId, token])

  async function reloadJob() {
    if (!token || !jobId) return
    setLoading(true)
    setError(null)
    try {
      const [jobData, respData] = await Promise.all([
        api.job(token, jobId),
        api.jobResponsibilities(token, jobId).catch(() => []),
      ])
      setJob(jobData)
      setResponsibilities(respData)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to load shipment details.')
    } finally {
      setLoading(false)
    }
  }

  async function handleCancelJob() {
    if (!token || !job || !cancelReason.trim()) {
      toast.error('A cancellation reason is required.')
      return
    }
    setCancelling(true)
    try {
      const updated = await api.cancelJob(token, job.id, job.version, cancelReason.trim())
      setJob(updated)
      setConfirmCancel(false)
      setCancelReason('')
      toast.success('Shipment cancelled and immutable audit record appended.')
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Cancellation failed.')
    } finally {
      setCancelling(false)
    }
  }

  async function handleExceptionRequest() {
    if (!token || !job || !exceptionReason.trim()) {
      toast.error('An exceptional transition justification reason is required.')
      return
    }
    setRequestingException(true)
    try {
      await api.exceptionRequest(token, job.id, exceptionAction, exceptionReason.trim())
      setConfirmException(false)
      setExceptionReason('')
      toast.success(`Exceptional ${exceptionAction} request submitted for independent approval.`)
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Exception request failed.')
    } finally {
      setRequestingException(false)
    }
  }

  async function handleSendAttention(e: React.FormEvent) {
    e.preventDefault()
    if (!token || !job || !attentionReason.trim()) {
      toast.error('An attention message explanation is required.')
      return
    }
    setSendingAttention(true)
    try {
      const receipt = await api.adminAttention(token, job.id, attentionReason.trim())
      setAttentionReason('')
      toast.success(`Attention delivered to ${receipt.delivered} currently authorized staff member(s).`)
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Failed to send attention notification.')
    } finally {
      setSendingAttention(false)
    }
  }

  async function handleDelegateJob(e: React.FormEvent) {
    e.preventDefault()
    if (!token || !job) return
    if (!currentAssignee) {
      toast.error(`The responsibility must be assigned before delegation. Allocate an employee as ${ROLE_TITLES[delegationRole].split(' ')[0]} directly first.`)
      return
    }
    const effectiveDelegateId = isCustomDelegate ? customDelegateId.trim() : delegateUserId.trim()
    if (!effectiveDelegateId || !delegationFrom || !delegationUntil || !delegationReason.trim()) {
      toast.error('Please select an employee delegate and complete all required fields.')
      return
    }
    const fromDate = new Date(delegationFrom)
    const untilDate = new Date(delegationUntil)
    if (untilDate <= fromDate) {
      toast.error('Delegation end date must be after the start date.')
      return
    }

    setSubmittingDelegation(true)
    try {
      await api.delegateJob(token, job.id, {
        responsibility: delegationRole,
        delegate_user_id: effectiveDelegateId,
        valid_from: fromDate.toISOString(),
        valid_until: untilDate.toISOString(),
        reason: delegationReason.trim(),
      })
      toast.success('Per-job delegation recorded and active.')
      setDelegateUserId('')
      setCustomDelegateId('')
      setIsCustomDelegate(false)
      setDelegationReason('')
      setDelegationFrom('')
      setDelegationUntil('')
      await reloadJob()
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Delegation failed.')
    } finally {
      setSubmittingDelegation(false)
    }
  }

  async function handleAssignPermanently() {
    if (!token || !job) return
    if (!effectiveDelegateId) {
      toast.error('Please select an employee delegate from the dropdown first to allocate them.')
      return
    }
    setAssigningDirectly(true)
    try {
      await api.assign(
        token,
        job.id,
        delegationRole,
        effectiveDelegateId,
        delegationReason.trim() || `Administrative workforce allocation of ${ROLE_TITLES[delegationRole]}`
      )
      toast.success(`Successfully allocated ${selectedDelegateName || 'selected staff'} as ${ROLE_TITLES[delegationRole]}!`)
      await reloadJob()
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Workforce allocation failed.')
    } finally {
      setAssigningDirectly(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <SkeletonMetricsGrid />
      </div>
    )
  }

  if (!job) {
    return (
      <div className="space-y-4">
        <Link to="/admin/jobs" className="text-xs font-semibold text-slate-500 hover:text-slate-800">
          &larr; Back to jobs
        </Link>
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-xs text-rose-800">
          {error ?? 'Shipment record could not be loaded or is not visible to your administrative scope.'}
        </div>
      </div>
    )
  }

  const isTerminalStage = job.stage === 'filed' || job.stage === 'cancelled'
  const canCancelDirectly = !isTerminalStage
  const allStaff: StaffMember[] = SEEDED_STAFF_DIRECTORY

  return (
    <div className="space-y-6">
      {/* Navigation Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <Link
          to="/admin/jobs"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 transition"
        >
          <ArrowLeftIcon className="h-4 w-4" />
          Back to Shipments Directory
        </Link>
        <div className="flex items-center gap-2">
          <Link
            to={`/admin/audit/${job.id}`}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 transition"
          >
            <HistoryIcon className="h-4 w-4 text-slate-500" />
            Audit History Timeline
          </Link>
        </div>
      </div>

      <PageHeader
        eyebrow="Customs Operations Command"
        title={job.reference}
        description="Shipment overview, workforce responsibility assignment, administrative controls, and staff attention."
      />

      {/* Shipment Meta Card */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-base font-black text-slate-900">{job.reference}</span>
            <StatusBadge status={job.stage} />
            <DirectionBadge direction={job.direction} />
            <ModeBadge mode={job.mode} />
          </div>
          <div className="text-right">
            <p className="text-xs text-slate-400 font-mono">
              Version: <span className="font-bold text-slate-700">{job.version}</span> · Revision:{' '}
              <span className="font-bold text-slate-700">{job.checklist_revision}</span>
            </p>
          </div>
        </div>

        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4 text-xs">
          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Client Account</span>
            <p className="mt-1 font-semibold text-slate-900">{job.client_name}</p>
            <p className="text-[11px] text-slate-400 font-mono">ID: {job.client_id}</p>
          </div>

          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Operations Branch</span>
            <p className="mt-1 font-semibold text-slate-900">{job.branch_name}</p>
            <p className="text-[11px] text-slate-400 font-mono">ID: {job.branch_id}</p>
          </div>

          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Container / Equipment</span>
            <p className="mt-1 font-mono font-semibold text-slate-900">
              {job.container_reference ?? 'None specified'}
            </p>
          </div>

          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Maker Edit Lock</span>
            <p className="mt-1 font-semibold text-slate-900">
              {job.maker_edit_locked ? (
                <span className="text-amber-700 font-bold">Locked (Submitted)</span>
              ) : (
                <span className="text-emerald-700 font-bold">Editable</span>
              )}
            </p>
          </div>

          <div className="sm:col-span-2 lg:col-span-4">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Goods Description</span>
            <p className="mt-1 text-slate-700 leading-relaxed">
              {job.goods_description || 'No goods description provided.'}
            </p>
          </div>
        </div>
      </div>

      {/* Assignment & Reallocation Suggestions Section */}
      <div id="workforce-allocation-section">
        <AssignmentSuggestions job={job} token={token!} onAssignmentSaved={() => void reloadJob()} />
      </div>

      {/* Per-Job Delegation Section */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
        <div className="flex items-center gap-3 border-b border-slate-100 pb-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-purple-50 text-purple-700">
            <ShieldAlertIcon className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900">Per-Job Responsibility Delegation</h3>
            <p className="text-xs text-slate-500">
              Authorize a temporary, expiring replacement delegate for an existing assigned role.
            </p>
          </div>
        </div>

        {/* Current Assignee or Unassigned Position Banner */}
        {!currentAssignee ? (
          <div className="rounded-xl border border-amber-200 bg-amber-50/80 p-4 text-xs text-amber-900 space-y-2.5">
            <div className="flex items-start gap-2.5">
              <AlertTriangleIcon className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
              <div className="space-y-1">
                <p className="font-semibold text-amber-950">
                  Position Unassigned: {ROLE_TITLES[delegationRole]}
                </p>
                <p className="text-amber-800 leading-relaxed">
                  The responsibility must be assigned before delegation. Under customs control invariants, delegation is temporary coverage for an <em>existing</em> assigned colleague. Because nobody is currently assigned as {ROLE_TITLES[delegationRole]}, you must allocate an employee directly instead of delegating.
                </p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2 pt-1 pl-6.5">
              <button
                type="button"
                disabled={!effectiveDelegateId || assigningDirectly}
                onClick={() => void handleAssignPermanently()}
                className="inline-flex items-center gap-1.5 rounded-lg bg-amber-800 px-3 py-1.5 font-semibold text-white hover:bg-amber-900 disabled:opacity-50 transition"
              >
                <UserCheckIcon className="h-3.5 w-3.5" />
                {assigningDirectly
                  ? 'Allocating...'
                  : effectiveDelegateId
                    ? `Allocate ${selectedDelegateName} as ${ROLE_TITLES[delegationRole].split(' ')[0]} Directly`
                    : `Select Colleague to Allocate as ${ROLE_TITLES[delegationRole].split(' ')[0]}`}
              </button>
              <a
                href="#workforce-allocation-section"
                className="text-[11px] font-medium text-amber-900 underline hover:text-amber-950 ml-1"
              >
                Or configure in Workforce Allocation &darr;
              </a>
            </div>
          </div>
        ) : (
          <div className="rounded-xl border border-purple-200 bg-purple-50/70 p-3 text-xs text-purple-900 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <UserCheckIcon className="h-4 w-4 text-purple-700 shrink-0" />
              <span>
                Currently assigned to: <strong className="font-semibold text-purple-950">{currentAssignee.display_name ?? 'Current Staff'}</strong>.
                Delegation will authorize temporary signing coverage on their behalf.
              </span>
            </div>
            {currentAssignee.via_delegation && (
              <span className="rounded bg-purple-200/80 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-purple-800">
                Active via Delegation
              </span>
            )}
          </div>
        )}

        <form onSubmit={handleDelegateJob} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <FormField label="Responsibility" required>
              <SelectInput
                value={delegationRole}
                onChange={(e) => setDelegationRole(e.target.value as 'maker' | 'checker' | 'filing_officer')}
              >
                {(['maker', 'checker', 'filing_officer'] as const).map((rKey) => {
                  const resp = responsibilities.find((r) => r.responsibility === rKey && r.user_id)
                  return (
                    <option key={rKey} value={rKey}>
                      {ROLE_TITLES[rKey]} — {resp ? `Assigned to ${resp.display_name ?? 'Staff'}` : '[Unassigned: Direct Allocation Required]'}
                    </option>
                  )
                })}
              </SelectInput>
            </FormField>

            <FormField
              label="Delegate Employee"
              required
              helperText={isCustomDelegate ? 'Enter custom user UUID directly' : 'Select suggested qualified staff or search colleague'}
            >
              <SelectInput
                value={isCustomDelegate ? 'custom' : delegateUserId}
                onChange={(e) => {
                  if (e.target.value === 'custom') {
                    setIsCustomDelegate(true)
                  } else {
                    setIsCustomDelegate(false)
                    setDelegateUserId(e.target.value)
                  }
                }}
              >
                <option value="">Select an employee delegate...</option>
                <optgroup label="All Operational Staff Directory">
                  {allStaff.map((emp) => (
                    <option key={emp.id} value={emp.id}>
                      {emp.name} ({emp.email})
                    </option>
                  ))}
                </optgroup>
                <option value="custom">Other / Custom User ID (Manual entry)...</option>
              </SelectInput>
              {isCustomDelegate && (
                <div className="mt-2">
                  <TextInput
                    value={customDelegateId}
                    onChange={(e) => setCustomDelegateId(e.target.value)}
                    placeholder="Enter employee UUID..."
                    className="font-mono text-xs"
                  />
                </div>
              )}
            </FormField>

            <FormField label="Valid From" required>
              <TextInput
                type="datetime-local"
                value={delegationFrom}
                onChange={(e) => setDelegationFrom(e.target.value)}
              />
            </FormField>

            <FormField label="Valid Until" required>
              <TextInput
                type="datetime-local"
                value={delegationUntil}
                onChange={(e) => setDelegationUntil(e.target.value)}
              />
            </FormField>

            <div className="sm:col-span-2 lg:col-span-4">
              <FormField label="Delegation Justification" required helperText="Audited reason for temporary assignment handoff.">
                <TextInput
                  value={delegationReason}
                  onChange={(e) => setDelegationReason(e.target.value)}
                  placeholder="e.g. Temporary coverage for urgent customs clearance during absence"
                />
              </FormField>
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={submittingDelegation || !currentAssignee}
              title={!currentAssignee ? 'The responsibility must be assigned before delegation.' : undefined}
              className="rounded-xl bg-purple-900 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-purple-950 disabled:opacity-50 transition"
            >
              {submittingDelegation
                ? 'Recording Delegation...'
                : !currentAssignee
                  ? `Assign ${ROLE_TITLES[delegationRole].split(' ')[0]} First to Enable Delegation`
                  : 'Authorize Delegation'}
            </button>
          </div>
        </form>
      </div>

      {/* Staff Attention Notification Form */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
        <div className="flex items-center gap-3 border-b border-slate-100 pb-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-50 text-amber-700">
            <BellIcon className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900">Send Attention to Responsible Personnel</h3>
            <p className="text-xs text-slate-500">
              Dispatches high-priority in-app notification to current assignees and active delegates.
            </p>
          </div>
        </div>

        <form onSubmit={handleSendAttention} className="space-y-4">
          <FormField label="Attention Message & Instructions" required helperText="Explain what responsible employees must review or rectify.">
            <TextareaInput
              value={attentionReason}
              onChange={(e) => setAttentionReason(e.target.value)}
              placeholder="e.g. Priority expedite requested by client. Please complete independent verification checklist."
            />
          </FormField>
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={sendingAttention}
              className="inline-flex items-center gap-1.5 rounded-xl bg-maritime-800 px-4 py-2 text-xs font-semibold text-white hover:bg-maritime-900 disabled:opacity-50 transition"
            >
              <BellIcon className="h-3.5 w-3.5" />
              {sendingAttention ? 'Delivering...' : 'Send Attention Notification'}
            </button>
          </div>
        </form>
      </div>

      {/* Administrative Workflow Control & Exceptional Actions */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
        <h3 className="text-sm font-bold text-slate-900">Administrative Workflow Control</h3>
        <p className="text-xs text-slate-500">
          Enforces server-side optimistic concurrency locks and immutable audit evidence.
        </p>

        <div className="flex flex-wrap items-center gap-3 pt-2">
          {canCancelDirectly && (
            <button
              type="button"
              onClick={() => {
                setCancelReason('')
                setConfirmCancel(true)
              }}
              className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-xs font-semibold text-rose-700 hover:bg-rose-100 transition"
            >
              Cancel Shipment
            </button>
          )}

          {job.stage === 'filed' && (
            <button
              type="button"
              onClick={() => {
                setExceptionAction('cancel')
                setExceptionReason('')
                setConfirmException(true)
              }}
              className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-xs font-semibold text-rose-700 hover:bg-rose-100 transition"
            >
              Request Exceptional Cancellation
            </button>
          )}

          {isTerminalStage && (
            <button
              type="button"
              onClick={() => {
                setExceptionAction('reopen')
                setExceptionReason('')
                setConfirmException(true)
              }}
              className="rounded-xl border border-cyan-200 bg-cyan-50 px-4 py-2 text-xs font-semibold text-cyan-800 hover:bg-cyan-100 transition"
            >
              Request Exceptional Reopening
            </button>
          )}
        </div>
      </div>

      {/* Cancel Confirmation Dialog */}
      <ConfirmationDialog
        open={confirmCancel}
        title="Cancel Shipment?"
        message={
          <div className="space-y-3">
            <p>
              Are you sure you want to cancel shipment <strong>{job.reference}</strong>? This action locks further editing and is recorded in the immutable audit log.
            </p>
            <FormField label="Cancellation Reason" required>
              <TextInput
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                placeholder="Reason for cancellation..."
              />
            </FormField>
          </div>
        }
        confirmLabel={cancelling ? 'Cancelling...' : 'Confirm Cancellation'}
        danger
        onConfirm={() => void handleCancelJob()}
        onCancel={() => setConfirmCancel(false)}
      />

      {/* Exceptional Transition Dialog */}
      <ConfirmationDialog
        open={confirmException}
        title={`Request Exceptional ${exceptionAction === 'cancel' ? 'Cancellation' : 'Reopening'}?`}
        message={
          <div className="space-y-3">
            <p>
              Filed shipments require independent administrative authorization before state transition.
            </p>
            <FormField label="Justification Reason" required>
              <TextInput
                value={exceptionReason}
                onChange={(e) => setExceptionReason(e.target.value)}
                placeholder="Reason for exceptional request..."
              />
            </FormField>
          </div>
        }
        confirmLabel={requestingException ? 'Submitting...' : 'Submit Request'}
        danger={exceptionAction === 'cancel'}
        onConfirm={() => void handleExceptionRequest()}
        onCancel={() => setConfirmException(false)}
      />
    </div>
  )
}
