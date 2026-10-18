import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import type {
  ChecklistItem,
  ChecklistStatus,
  FilingReturnCategory,
  Job,
  JobResponsibilityDetail,
  OperationalHistoryItem,
} from '../../api/contracts'
import { useAuth } from '../../auth/AuthContext'
import { ConfirmationDialog } from '../../components/design-system/ConfirmationDialog'
import { FormField, SelectInput, TextInput, TextareaInput } from '../../components/design-system/FormElements'
import { SkeletonMetricsGrid } from '../../components/design-system/LoadingSkeleton'
import { DirectionBadge, ModeBadge, StatusBadge } from '../../components/design-system/StatusBadge'
import { useToast } from '../../components/feedback/ToastContext'
import {
  AlertTriangleIcon,
  ArrowLeftIcon,
  CheckCircleIcon,
  ClockIcon,
  FileCheckIcon,
  LockIcon,
  RotateCcwIcon,
  SaveIcon,
  SendIcon,
} from '../../components/icons'
import { PageHeader } from '../../components/shell/AppShell'

const DEFAULT_CHECKLIST_ITEMS: Record<string, { key: string; label: string }[]> = {
  air: [
    { key: 'commercial_invoice', label: 'Commercial invoice matches shipment details' },
    { key: 'packing_list', label: 'Packing list is present and consistent' },
    { key: 'air_waybill', label: 'Air waybill details are verified' },
  ],
  fcl: [
    { key: 'commercial_invoice', label: 'Commercial invoice matches shipment details' },
    { key: 'packing_list', label: 'Packing list is present and consistent' },
    { key: 'bill_of_lading', label: 'Bill of lading details are verified' },
    { key: 'container_reference', label: 'Container and seal references are verified' },
  ],
  lcl: [
    { key: 'commercial_invoice', label: 'Commercial invoice matches shipment details' },
    { key: 'packing_list', label: 'Packing list is present and consistent' },
    { key: 'house_bill_of_lading', label: 'House bill of lading is verified' },
    { key: 'consolidation_reference', label: 'Consolidation reference is verified' },
  ],
}

function getGeneratedChecklistItems(shipment: Job): ChecklistItem[] {
  if (
    Array.isArray(shipment.checklist_data?.items) &&
    shipment.checklist_data.items.length > 0 &&
    typeof shipment.checklist_data.items[0] === 'object'
  ) {
    return shipment.checklist_data.items as ChecklistItem[]
  }
  const modeKey = (shipment.mode || 'air').toLowerCase()
  const base = DEFAULT_CHECKLIST_ITEMS[modeKey] || DEFAULT_CHECKLIST_ITEMS.air
  const directionKey = `${(shipment.direction || 'import').toLowerCase()}_requirements`
  const directionLabel =
    (shipment.direction || 'import').toLowerCase() === 'import'
      ? 'Import permits and arrival requirements are verified'
      : 'Export permits and departure requirements are verified'

  return [
    ...base.map((item) => ({
      key: item.key,
      label: item.label,
      required: true,
      status: null as ChecklistStatus | null,
      justification: null,
    })),
    {
      key: directionKey,
      label: directionLabel,
      required: true,
      status: null as ChecklistStatus | null,
      justification: null,
    },
  ]
}

export function OperationalJobPage() {
  const { jobId = '' } = useParams<{ jobId: string }>()
  const { token } = useAuth()
  const toast = useToast()

  const [job, setJob] = useState<Job | null>(null)
  const [responsibilities, setResponsibilities] = useState<JobResponsibilityDetail[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Maker form state
  const [goodsDescription, setGoodsDescription] = useState('')
  const [containerReference, setContainerReference] = useState('')
  const [makerJustification, setMakerJustification] = useState('')
  const [savingDetails, setSavingDetails] = useState(false)
  const [confirmSubmitPrepared, setConfirmSubmitPrepared] = useState(false)
  const [submittingPrepared, setSubmittingPrepared] = useState(false)


  // Checker checklist state
  const [checklistItems, setChecklistItems] = useState<ChecklistItem[]>([])
  const [checkerFeedback, setCheckerFeedback] = useState('')
  const [checkerJustification, setCheckerJustification] = useState('')
  const [confirmCheck, setConfirmCheck] = useState(false)
  const [submittingCheck, setSubmittingCheck] = useState(false)

  // Filing Officer state
  const [filingHistory, setFilingHistory] = useState<OperationalHistoryItem[]>([])
  const [returnCategory, setReturnCategory] = useState<FilingReturnCategory>('maker_fault')
  const [returnReason, setReturnReason] = useState('')
  const [confirmFilingAction, setConfirmFilingAction] = useState<'file' | 'return' | null>(null)
  const [submittingFiling, setSubmittingFiling] = useState(false)

  useEffect(() => {
    if (!token || !jobId) return
    let active = true

    Promise.all([
      api.job(token, jobId),
      api.jobResponsibilities(token, jobId),
    ])
      .then(([shipment, assigns]) => {
        if (!active) return
        setJob(shipment)
        setResponsibilities(assigns)
        setGoodsDescription(shipment.goods_description || '')
        setContainerReference(shipment.container_reference || '')
        setChecklistItems(getGeneratedChecklistItems(shipment))

        if (Array.isArray(assigns) && assigns.some((a) => a.responsibility === 'filing_officer' && a.current_actor_responsible)) {
          api.operationalHistory(token, jobId)
            .then((hist) => {
              if (active) setFilingHistory(hist)
            })
            .catch(() => {})
        }
        setLoading(false)
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

  async function reloadJobData() {
    if (!token || !jobId) return
    setLoading(true)
    setError(null)
    try {
      const [shipment, assigns] = await Promise.all([
        api.job(token, jobId),
        api.jobResponsibilities(token, jobId),
      ])
      setJob(shipment)
      setResponsibilities(assigns)
      setGoodsDescription(shipment.goods_description || '')
      setContainerReference(shipment.container_reference || '')
      setChecklistItems(getGeneratedChecklistItems(shipment))

      if (Array.isArray(assigns) && assigns.some((a) => a.responsibility === 'filing_officer' && a.current_actor_responsible)) {
        try {
          const hist = await api.operationalHistory(token, jobId)
          setFilingHistory(hist)
        } catch {
          // history optional
        }
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to load authorized shipment.')
    } finally {
      setLoading(false)
    }
  }

  // Responsibility checks
  const respArray = Array.isArray(responsibilities) ? responsibilities : []
  const makerResp = respArray.find((r) => r.responsibility === 'maker')
  const checkerResp = respArray.find((r) => r.responsibility === 'checker')
  const filingResp = respArray.find((r) => r.responsibility === 'filing_officer')

  const isMaker = makerResp?.current_actor_responsible === true
  const isChecker = checkerResp?.current_actor_responsible === true
  const isFiler = filingResp?.current_actor_responsible === true

  const canMakerEdit = Boolean(
    isMaker && job && !job.maker_edit_locked && ['confirmed', 'reopened'].includes(job.stage)
  )
  const isCorrection = Boolean(job && (job.checklist_revision > 0 || job.maker_correction_required))

  // Maker handlers
  async function handleSaveDetails() {
    if (!token || !job) return
    setSavingDetails(true)
    try {
      const updated = await api.updateJob(token, job.id, {
        expected_version: job.version,
        goods_description: goodsDescription,
        container_reference: containerReference.trim() || null,
      })
      setJob(updated)
      toast.success('Shipment details saved.')
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Save failed.')
    } finally {
      setSavingDetails(false)
    }
  }

  async function handleSubmitPrepared() {
    if (!token || !job) return
    if (isCorrection && !makerJustification.trim()) {
      toast.error('Explain what was corrected before resubmitting.')
      return
    }

    setSubmittingPrepared(true)
    try {
      const updated = await api.prepareJob(token, job.id, job.version, makerJustification.trim())
      setJob(updated)
      setConfirmSubmitPrepared(false)
      setMakerJustification('')
      toast.success(
        isCorrection
          ? 'Corrections resubmitted for independent verification.'
          : 'Shipment submitted for independent verification.'
      )
      await reloadJobData()
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Submission failed.')
    } finally {
      setSubmittingPrepared(false)
    }
  }


  // Checker handlers
  const hasIncomplete = checklistItems.some((it) => it.status === 'incomplete')

  function handleChecklistStatusChange(key: string, status: ChecklistStatus) {
    setChecklistItems((prev) =>
      prev.map((it) =>
        it.key === key
          ? { ...it, status, justification: status === 'not_applicable' ? it.justification : null }
          : it
      )
    )
  }

  function handleChecklistJustificationChange(key: string, justification: string) {
    setChecklistItems((prev) =>
      prev.map((it) => (it.key === key ? { ...it, justification } : it))
    )
  }

  function validateChecklist(): string | null {
    if (checklistItems.length === 0) {
      return 'Checklist items could not be loaded. Please reload the shipment.'
    }
    if (checklistItems.some((it) => it.status === null)) {
      return 'Please choose Complete, Incomplete, or Not Applicable for every checklist item.'
    }
    if (checklistItems.some((it) => it.status === 'not_applicable' && !it.justification?.trim())) {
      return 'Explain every Not Applicable decision.'
    }
    if (hasIncomplete && !checkerFeedback.trim()) {
      return 'Provide actionable correction feedback for the Maker.'
    }
    if (job?.checker_correction_required && !checkerJustification.trim()) {
      return 'Explain your reevaluation before resubmitting this checklist.'
    }
    return null
  }

  async function handleSubmitChecklist() {
    if (!token || !job) return
    setSubmittingCheck(true)
    try {
      const updated = await api.checkJob(token, job.id, {
        expected_version: job.version,
        approved: !hasIncomplete,
        reason: checkerFeedback.trim(),
        checklist_items: checklistItems.map((it) => ({
          key: it.key,
          status: it.status!,
          justification: it.justification?.trim() || null,
        })),
        justification: checkerJustification.trim(),
      })
      setJob(updated)
      setConfirmCheck(false)
      toast.success(
        hasIncomplete
          ? 'Shipment returned to Maker with written correction feedback.'
          : 'Checklist verified and submitted for customs filing.'
      )
      await reloadJobData()
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Checklist submission failed.')
    } finally {
      setSubmittingCheck(false)
    }
  }

  // Filing handlers
  async function handleFilingAction() {
    if (!token || !job || !confirmFilingAction) return
    setSubmittingFiling(true)
    try {
      if (confirmFilingAction === 'file') {
        const updated = await api.fileJob(token, job.id, job.version)
        setJob(updated)
        toast.success('Shipment customs filing recorded successfully.')
      } else {
        if (!returnReason.trim()) {
          toast.error('A written correction explanation is required.')
          setSubmittingFiling(false)
          return
        }
        const updated = await api.returnForCorrection(
          token,
          job.id,
          job.version,
          returnCategory,
          returnReason.trim()
        )
        setJob(updated)
        toast.success('Shipment returned for correction.')
      }
      setConfirmFilingAction(null)
      setReturnReason('')
      await reloadJobData()
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Filing action failed.')
    } finally {
      setSubmittingFiling(false)
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
        <Link to="/work" className="text-xs font-semibold text-slate-500 hover:text-slate-800">
          &larr; Back to My Work
        </Link>
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-xs text-rose-800">
          {error ?? 'This shipment is unavailable or not assigned to your authorized responsibilities.'}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Navigation Header */}
      <div className="flex items-center justify-between">
        <Link
          to="/work"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 transition"
        >
          <ArrowLeftIcon className="h-4 w-4" />
          Back to My Work Queue
        </Link>
      </div>

      <PageHeader
        eyebrow="Operational Shipment Workspace"
        title={job.reference}
        description="Shipment access and segregation of duties are revalidated on every submission."
      />

      {/* Meta Card */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-base font-black text-slate-900">{job.reference}</span>
            <StatusBadge status={job.stage} />
            <DirectionBadge direction={job.direction} />
            <ModeBadge mode={job.mode} />
          </div>
          <p className="text-xs text-slate-400 font-mono">
            Revision: <strong className="text-slate-700">{job.checklist_revision}</strong> · Version:{' '}
            <strong className="text-slate-700">{job.version}</strong>
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 text-xs">
          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Client / Branch</span>
            <p className="mt-1 font-semibold text-slate-900">{job.client_name}</p>
            <p className="text-slate-500">{job.branch_name}</p>
          </div>

          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Assigned Maker</span>
            <p className="mt-1 font-semibold text-slate-900">
              {makerResp?.display_name ?? 'Unassigned'}
              {makerResp?.current_actor_responsible && (
                <span className="ml-1 text-cyan-700 font-bold">
                  {makerResp.via_delegation ? '(You via Delegation)' : '(You)'}
                </span>
              )}
            </p>
          </div>

          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Assigned Checker</span>
            <p className="mt-1 font-semibold text-slate-900">
              {checkerResp?.display_name ?? 'Unassigned'}
              {checkerResp?.current_actor_responsible && (
                <span className="ml-1 text-cyan-700 font-bold">
                  {checkerResp.via_delegation ? '(You via Delegation)' : '(You)'}
                </span>
              )}
            </p>
          </div>

          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Assigned Filing Officer</span>
            <p className="mt-1 font-semibold text-slate-900">
              {filingResp?.display_name ?? 'Unassigned'}
              {filingResp?.current_actor_responsible && (
                <span className="ml-1 text-cyan-700 font-bold">
                  {filingResp.via_delegation ? '(You via Delegation)' : '(You)'}
                </span>
              )}
            </p>
          </div>
        </div>

        {/* Correction Feedback Notice */}
        {job.last_return_reason && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 space-y-1">
            <div className="flex items-center gap-2 text-amber-900 font-bold text-xs uppercase tracking-wider">
              <AlertTriangleIcon className="h-4 w-4 text-amber-600" />
              Correction Feedback ({job.last_return_category?.replace('_', ' ') ?? 'General'})
            </div>
            <p className="text-xs text-amber-950 font-medium pl-6">{job.last_return_reason}</p>
          </div>
        )}

        {/* Maker Justification if visible to Checker */}
        {isChecker && job.last_maker_justification && (
          <div className="rounded-xl border border-sky-200 bg-sky-50 p-4 space-y-1">
            <p className="text-xs font-bold text-sky-950 uppercase tracking-wider">
              Maker Resubmission Explanation
            </p>
            <p className="text-xs text-sky-900">{job.last_maker_justification}</p>
          </div>
        )}

        {/* Checker Justification if visible to Filing */}
        {isFiler && job.last_checker_justification && (
          <div className="rounded-xl border border-sky-200 bg-sky-50 p-4 space-y-1">
            <p className="text-xs font-bold text-sky-950 uppercase tracking-wider">
              Checker Verification Explanation
            </p>
            <p className="text-xs text-sky-900">{job.last_checker_justification}</p>
          </div>
        )}
      </div>

      {/* MAKER WORKSPACE */}
      {isMaker && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-5">
          <div className="border-b border-slate-100 pb-3">
            <h3 className="text-sm font-bold text-slate-900">Maker Preparation Workspace</h3>
            <p className="text-xs text-slate-500">
              Prepare customs declaration data, container equipment references, and resubmission explanations.
            </p>
          </div>

          <div className="space-y-4">
            <FormField label="Goods Description" required={canMakerEdit}>
              <TextareaInput
                disabled={!canMakerEdit}
                value={goodsDescription}
                onChange={(e) => setGoodsDescription(e.target.value)}
                placeholder="Detailed description of goods for customs classification..."
              />
            </FormField>

            <FormField label="Container / Equipment Reference">
              <TextInput
                disabled={!canMakerEdit}
                value={containerReference}
                onChange={(e) => setContainerReference(e.target.value)}
                placeholder="e.g. MSKU-9182374"
                className="font-mono text-xs"
              />
            </FormField>

            {canMakerEdit && isCorrection && (
              <FormField
                label="Correction & Resubmission Justification"
                required
                helperText="Explain what changes were made or why unchanged information is accurate."
              >
                <TextareaInput
                  value={makerJustification}
                  onChange={(e) => setMakerJustification(e.target.value)}
                  placeholder="Explain resolution of returned feedback..."
                />
              </FormField>
            )}

            {canMakerEdit && (
              <div className="flex flex-wrap items-center gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  disabled={savingDetails}
                  onClick={() => void handleSaveDetails()}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 disabled:opacity-50 transition"
                >
                  <SaveIcon className="h-4 w-4" />
                  {savingDetails ? 'Saving...' : 'Save Draft'}
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmSubmitPrepared(true)}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-maritime-800 px-5 py-2 text-xs font-semibold text-white shadow-xs hover:bg-maritime-900 transition"
                >
                  <SendIcon className="h-4 w-4 text-cyan-400" />
                  {isCorrection ? 'Resubmit Corrections' : 'Submit for Verification'}
                </button>
              </div>
            )}

            {job.maker_edit_locked ? (
              <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-4 text-xs text-amber-950 flex items-start gap-3">
                <LockIcon className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
                <div>
                  <strong className="text-amber-900 block font-bold">Preparation Completed & Locked</strong>
                  <span className="text-amber-800">
                    This shipment has been submitted for independent verification and is locked. Further editing is disabled to preserve segregation of duties and prevent overwrite by another maker, unless returned for correction by the Checker or Filing Officer.
                  </span>
                </div>
              </div>
            ) : !['confirmed', 'reopened'].includes(job.stage) ? (
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-700 flex items-start gap-3">
                <LockIcon className="h-4 w-4 text-slate-500 mt-0.5 shrink-0" />
                <div>
                  <strong className="text-slate-800 block font-bold">Preparation Completed (Stage: {job.stage})</strong>
                  <span className="text-slate-600">
                    This shipment has advanced beyond the preparation stage and cannot be edited.
                  </span>
                </div>
              </div>
            ) : null}
          </div>

        </div>
      )}

      {/* CHECKER WORKSPACE */}
      {isChecker && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-5">
          <div className="border-b border-slate-100 pb-3 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Independent Verification Checklist</h3>
              <p className="text-xs text-slate-500">
                Segregation of duties enforces independent check. Once verified, actions are locked to prevent overwrite.
              </p>
            </div>
            {['checked', 'filed'].includes(job.stage) && (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 border border-emerald-200 px-3 py-1 text-xs font-semibold text-emerald-800">
                <CheckCircleIcon className="h-3.5 w-3.5 text-emerald-600" />
                Verification Completed
              </span>
            )}
          </div>

          {job.stage === 'prepared' ? (
            <div className="space-y-4">
              {checklistItems.map((item) => (
                <div
                  key={item.key}
                  className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 space-y-3"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div>
                      <p className="text-xs font-bold text-slate-900">{item.label}</p>
                      <p className="text-[11px] font-mono text-slate-400">Key: {item.key}</p>
                    </div>

                    <div className="flex items-center gap-3">
                      {(['complete', 'incomplete', 'not_applicable'] as const).map((statusVal) => (
                        <label
                          key={statusVal}
                          className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-semibold cursor-pointer transition ${
                            item.status === statusVal
                              ? statusVal === 'complete'
                                ? 'border-emerald-500 bg-emerald-50 text-emerald-800'
                                : statusVal === 'incomplete'
                                  ? 'border-rose-500 bg-rose-50 text-rose-800'
                                  : 'border-amber-500 bg-amber-50 text-amber-800'
                              : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
                          }`}
                        >
                          <input
                            type="radio"
                            name={`status-${item.key}`}
                            checked={item.status === statusVal}
                            onChange={() => handleChecklistStatusChange(item.key, statusVal)}
                            className="sr-only"
                          />
                          {statusVal === 'complete'
                            ? 'Complete'
                            : statusVal === 'incomplete'
                              ? 'Incomplete'
                              : 'N/A'}
                        </label>
                      ))}
                    </div>
                  </div>

                  {item.status === 'not_applicable' && (
                    <FormField label="Not Applicable Justification" required>
                      <TextInput
                        value={item.justification ?? ''}
                        onChange={(e) => handleChecklistJustificationChange(item.key, e.target.value)}
                        placeholder="Audited justification explaining why this item does not apply..."
                      />
                    </FormField>
                  )}
                </div>
              ))}

              {hasIncomplete && (
                <FormField
                  label="Correction Feedback for Maker"
                  required
                  helperText="Explain what the Maker must rectify before this shipment can proceed."
                >
                  <TextareaInput
                    value={checkerFeedback}
                    onChange={(e) => setCheckerFeedback(e.target.value)}
                    placeholder="Specific items and documentation requiring correction..."
                  />
                </FormField>
              )}

              {job.checker_correction_required && (
                <FormField
                  label="Reevaluation Explanation"
                  required
                  helperText="Explain reconsidered verification findings."
                >
                  <TextareaInput
                    value={checkerJustification}
                    onChange={(e) => setCheckerJustification(e.target.value)}
                    placeholder="Explain reevaluation context..."
                  />
                </FormField>
              )}

              <div className="flex justify-end pt-3">
                <button
                  type="button"
                  onClick={() => {
                    const problem = validateChecklist()
                    if (problem) {
                      toast.error(problem)
                      return
                    }
                    setConfirmCheck(true)
                  }}
                  className={`rounded-xl px-5 py-2.5 text-xs font-semibold text-white shadow-xs transition ${
                    hasIncomplete
                      ? 'bg-rose-700 hover:bg-rose-800'
                      : 'bg-emerald-700 hover:bg-emerald-800'
                  }`}
                >
                  {hasIncomplete ? 'Return to Maker for Correction' : 'Approve Independent Verification'}
                </button>
              </div>
            </div>
          ) : ['checked', 'filed'].includes(job.stage) ? (
            <div className="space-y-4">
              <div className="rounded-xl border border-emerald-200 bg-emerald-50/80 p-4 text-xs text-emerald-950 flex items-start gap-3">
                <CheckCircleIcon className="h-4 w-4 text-emerald-600 mt-0.5 shrink-0" />
                <div>
                  <p className="font-bold text-emerald-900">Independent Verification Completed & Locked</p>
                  <p className="mt-0.5 text-emerald-800">
                    This shipment has already been independently verified and passed for customs filing by a Checker. Under segregation of duties and concurrency rules, verification decisions are permanently locked and cannot be overwritten or altered by another checker.
                  </p>
                </div>
              </div>

              <div className="space-y-3">
                {checklistItems.map((item) => (
                  <div
                    key={item.key}
                    className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                  >
                    <div>
                      <p className="text-xs font-bold text-slate-900">{item.label}</p>
                      <p className="text-[11px] font-mono text-slate-400">Key: {item.key}</p>
                      {item.justification && (
                        <p className="text-xs text-amber-800 mt-1 italic">
                          Justification: {item.justification}
                        </p>
                      )}
                    </div>
                    <div>
                      {item.status === 'complete' ? (
                        <span className="inline-flex items-center gap-1 rounded-md bg-emerald-100 text-emerald-800 px-2.5 py-1 text-xs font-semibold">
                          <CheckCircleIcon className="h-3.5 w-3.5 text-emerald-600" />
                          Complete
                        </span>
                      ) : item.status === 'not_applicable' ? (
                        <span className="inline-flex items-center gap-1 rounded-md bg-amber-100 text-amber-800 px-2.5 py-1 text-xs font-semibold">
                          N/A
                        </span>
                      ) : item.status === 'incomplete' ? (
                        <span className="inline-flex items-center gap-1 rounded-md bg-rose-100 text-rose-800 px-2.5 py-1 text-xs font-semibold">
                          Incomplete
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-md bg-emerald-100 text-emerald-800 px-2.5 py-1 text-xs font-semibold">
                          <CheckCircleIcon className="h-3.5 w-3.5 text-emerald-600" />
                          Verified
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-600 flex items-start gap-3">
              <ClockIcon className="h-4 w-4 text-slate-400 mt-0.5 shrink-0" />
              <div>
                <p className="font-bold text-slate-800">Awaiting Maker Submission</p>
                <p className="mt-0.5">
                  The verification checklist will unlock once the assigned Maker completes and submits the declaration.
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* FILING OFFICER WORKSPACE */}
      {isFiler && job.stage === 'checked' && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-6">
          <div className="border-b border-slate-100 pb-3">
            <h3 className="text-sm font-bold text-slate-900">Customs Filing Officer Workspace</h3>
            <p className="text-xs text-slate-500">
              Submit verified shipment to external customs authority or return for revision.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => setConfirmFilingAction('file')}
              className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-700 px-5 py-2.5 text-xs font-semibold text-white shadow-xs hover:bg-emerald-800 transition"
            >
              <FileCheckIcon className="h-4 w-4" />
              File Shipment with Customs
            </button>
          </div>

          {/* Return for Correction Section */}
          <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-5 space-y-4">
            <h4 className="text-xs font-bold text-slate-900">Return for Correction</h4>
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="Responsible Area" required>
                <SelectInput
                  value={returnCategory}
                  onChange={(e) => setReturnCategory(e.target.value as FilingReturnCategory)}
                >
                  <option value="maker_fault">Maker (Documentation / Declaration)</option>
                  <option value="checker_fault">Checker (Checklist Verification)</option>
                  <option value="both">Both (Maker & Checker)</option>
                </SelectInput>
              </FormField>

              <div className="sm:col-span-2">
                <FormField label="Required Return Explanation" required>
                  <TextareaInput
                    value={returnReason}
                    onChange={(e) => setReturnReason(e.target.value)}
                    placeholder="Provide detailed feedback on required corrections..."
                  />
                </FormField>
              </div>
            </div>

            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => {
                  if (!returnReason.trim()) {
                    toast.error('A return explanation is required.')
                    return
                  }
                  setConfirmFilingAction('return')
                }}
                className="inline-flex items-center gap-1.5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-xs font-semibold text-rose-700 hover:bg-rose-100 transition"
              >
                <RotateCcwIcon className="h-4 w-4" />
                Return Shipment for Correction
              </button>
            </div>
          </div>

          {/* Operational History Log */}
          {filingHistory.length > 0 && (
            <div className="space-y-3 pt-3">
              <h4 className="text-xs font-bold text-slate-900">Operational History Log</h4>
              <div className="space-y-2">
                {filingHistory.map((item) => (
                  <div
                    key={item.version_number}
                    className="border-l-2 border-cyan-500 pl-3 py-1 text-xs"
                  >
                    <p className="font-semibold text-slate-800 uppercase">
                      {item.action.replace(/_/g, ' ')}
                    </p>
                    <p className="text-slate-600 mt-0.5">{item.reason}</p>
                    <p className="text-[10px] text-slate-400 font-mono mt-0.5">
                      {new Date(item.occurred_at).toLocaleString()} · v{item.version_number}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Confirmation Dialogs */}
      <ConfirmationDialog
        open={confirmSubmitPrepared}
        title={isCorrection ? 'Resubmit Corrections?' : 'Submit for Independent Verification?'}
        message="This action locks your editing permissions until the revision is independently verified by a Checker or returned."
        confirmLabel={submittingPrepared ? 'Submitting...' : 'Confirm Submission'}
        onConfirm={() => void handleSubmitPrepared()}
        onCancel={() => setConfirmSubmitPrepared(false)}
      />

      <ConfirmationDialog
        open={confirmCheck}
        title={hasIncomplete ? 'Return to Maker?' : 'Approve Independent Verification?'}
        message={
          hasIncomplete
            ? 'The shipment will route back to the Maker with your actionable correction feedback.'
            : 'Your verified revision will become available to Filing Officers for customs declaration.'
        }
        confirmLabel={submittingCheck ? 'Recording...' : hasIncomplete ? 'Confirm Return' : 'Confirm Approval'}
        danger={hasIncomplete}
        onConfirm={() => void handleSubmitChecklist()}
        onCancel={() => setConfirmCheck(false)}
      />

      <ConfirmationDialog
        open={confirmFilingAction !== null}
        title={confirmFilingAction === 'file' ? 'File Shipment with Customs?' : 'Return for Correction?'}
        message={
          confirmFilingAction === 'file'
            ? 'This registers the final filing against the independently checked revision.'
            : 'The designated personnel will be notified to correct and resubmit.'
        }
        confirmLabel={submittingFiling ? 'Processing...' : confirmFilingAction === 'file' ? 'Confirm Filing' : 'Confirm Return'}
        danger={confirmFilingAction === 'return'}
        onConfirm={() => void handleFilingAction()}
        onCancel={() => setConfirmFilingAction(null)}
      />
    </div>
  )
}
