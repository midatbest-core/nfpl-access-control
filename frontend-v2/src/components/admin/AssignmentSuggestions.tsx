import { useEffect, useMemo, useState } from 'react'
import { api, ApiError } from '../../api/client'
import type { Suggestion } from '../../api/contracts'
import { SEEDED_STAFF_DIRECTORY, type StaffMember } from '../../api/staffDirectory'
import { FormField, SelectInput, TextInput } from '../design-system/FormElements'
import { SkeletonMetricCard } from '../design-system/LoadingSkeleton'
import { useToast } from '../feedback/ToastContext'
import {
  AlertTriangleIcon,
  CheckCircleIcon,
  RefreshIcon,
  UserCheckIcon,
  UsersIcon,
} from '../icons'

interface AssignmentRoleConfig {
  key: 'maker' | 'checker' | 'filing_officer'
  title: string
  subtitle: string
  badgeText: string
}

const ROLES: AssignmentRoleConfig[] = [
  {
    key: 'maker',
    title: 'Maker (Preparation)',
    subtitle: 'Prepares documentation, declarations & shipment attributes',
    badgeText: 'Preparation',
  },
  {
    key: 'checker',
    title: 'Checker (Verification)',
    subtitle: 'Audits checklist items, validates compliance & accuracy',
    badgeText: 'Verification',
  },
  {
    key: 'filing_officer',
    title: 'Filing Officer (Customs Filing)',
    subtitle: 'Submits finalized manifest & clearance to customs authority',
    badgeText: 'Customs Filing',
  },
]

export function AssignmentSuggestions({
  job,
  token,
  onAssignmentSaved,
}: {
  job: { id: string; reference: string }
  token: string
  onAssignmentSaved?: () => void
}) {
  const toast = useToast()

  const [suggestions, setSuggestions] = useState<Record<string, Suggestion[]>>({})
  const [currentAssignments, setCurrentAssignments] = useState<Record<string, { userId: string | null; name: string | null }>>({
    maker: { userId: null, name: null },
    checker: { userId: null, name: null },
    filing_officer: { userId: null, name: null },
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reason, setReason] = useState('Admin assignment based on current eligibility and workload.')

  // Local selection state for each role
  const [selectedMaker, setSelectedMaker] = useState('')
  const [customMakerId, setCustomMakerId] = useState('')

  const [selectedChecker, setSelectedChecker] = useState('')
  const [customCheckerId, setCustomCheckerId] = useState('')

  const [selectedOfficer, setSelectedOfficer] = useState('')
  const [customOfficerId, setCustomOfficerId] = useState('')

  useEffect(() => {
    let active = true

    Promise.all([
      api.suggestions(token, job.id).catch(() => ({})),
      api.jobResponsibilities(token, job.id).catch(() => []),
    ])
      .then(([sugData, respData]) => {
        if (active) {
          setSuggestions(sugData)

          const curr: Record<string, { userId: string | null; name: string | null }> = {
            maker: { userId: null, name: null },
            checker: { userId: null, name: null },
            filing_officer: { userId: null, name: null },
          }

          respData.forEach((r) => {
            curr[r.responsibility] = {
              userId: r.user_id,
              name: r.display_name,
            }
          })

          setCurrentAssignments(curr)
          setSelectedMaker(curr.maker.userId || '')
          setSelectedChecker(curr.checker.userId || '')
          setSelectedOfficer(curr.filing_officer.userId || '')
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
  }, [job.id, token])

  async function reloadAll() {
    setLoading(true)
    setError(null)
    try {
      const [sugData, respData] = await Promise.all([
        api.suggestions(token, job.id).catch(() => ({})),
        api.jobResponsibilities(token, job.id).catch(() => []),
      ])
      setSuggestions(sugData)

      const curr: Record<string, { userId: string | null; name: string | null }> = {
        maker: { userId: null, name: null },
        checker: { userId: null, name: null },
        filing_officer: { userId: null, name: null },
      }

      respData.forEach((r) => {
        curr[r.responsibility] = {
          userId: r.user_id,
          name: r.display_name,
        }
      })

      setCurrentAssignments(curr)
      setSelectedMaker(curr.maker.userId || '')
      setSelectedChecker(curr.checker.userId || '')
      setSelectedOfficer(curr.filing_officer.userId || '')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not refresh assignments.')
    } finally {
      setLoading(false)
    }
  }

  // Get effective values taking into account manual entry
  const effectiveMaker = selectedMaker === 'custom' ? customMakerId.trim() : selectedMaker
  const effectiveChecker = selectedChecker === 'custom' ? customCheckerId.trim() : selectedChecker
  const effectiveOfficer = selectedOfficer === 'custom' ? customOfficerId.trim() : selectedOfficer

  // Invariant check: Maker and Checker cannot be identical
  const hasMakerCheckerConflict = useMemo(() => {
    return Boolean(effectiveMaker && effectiveChecker && effectiveMaker === effectiveChecker)
  }, [effectiveMaker, effectiveChecker])

  // Count pending changes
  const pendingChanges = useMemo(() => {
    const changes: { role: 'maker' | 'checker' | 'filing_officer'; label: string; targetId: string | null }[] = []

    const origMaker = currentAssignments.maker.userId || ''
    if (effectiveMaker !== origMaker) {
      changes.push({ role: 'maker', label: 'Maker', targetId: effectiveMaker || null })
    }

    const origChecker = currentAssignments.checker.userId || ''
    if (effectiveChecker !== origChecker) {
      changes.push({ role: 'checker', label: 'Checker', targetId: effectiveChecker || null })
    }

    const origOfficer = currentAssignments.filing_officer.userId || ''
    if (effectiveOfficer !== origOfficer) {
      changes.push({ role: 'filing_officer', label: 'Filing Officer', targetId: effectiveOfficer || null })
    }

    return changes
  }, [currentAssignments, effectiveMaker, effectiveChecker, effectiveOfficer])

  async function handleSaveAllAssignments(e: React.FormEvent) {
    e.preventDefault()
    if (saving) return

    if (!reason.trim()) {
      toast.error('An assignment or reallocation reason is required.')
      return
    }

    if (hasMakerCheckerConflict) {
      toast.error('Maker and Checker cannot be the same employee on the same shipment.')
      return
    }

    if (pendingChanges.length === 0) {
      toast.info('No assignment changes detected. All positions already match.')
      return
    }

    setSaving(true)
    setError(null)

    try {
      // Execute all pending changes sequentially
      for (const change of pendingChanges) {
        await api.assign(token, job.id, change.role, change.targetId, reason.trim())
      }

      toast.success(
        `Successfully updated ${pendingChanges.length} workforce assignment(s).`,
        'Assignments Saved'
      )
      onAssignmentSaved?.()
      await reloadAll()
    } catch (caught) {
      if (caught instanceof ApiError && (caught.reasonCode === 'assignment_ineligible' || caught.status === 409)) {
        toast.warning(`${caught.message} Refreshed directory displayed.`)
      } else {
        toast.error(caught instanceof Error ? caught.message : 'Could not save assignments.')
      }
      await reloadAll()
    } finally {
      setSaving(false)
    }
  }

  function handleReset() {
    setSelectedMaker(currentAssignments.maker.userId || '')
    setCustomMakerId('')
    setSelectedChecker(currentAssignments.checker.userId || '')
    setCustomCheckerId('')
    setSelectedOfficer(currentAssignments.filing_officer.userId || '')
    setCustomOfficerId('')
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-50 text-cyan-700">
            <UsersIcon className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-900">Workforce Allocation Directory</h3>
            <p className="text-xs text-slate-500">
              Deterministic allocation suggestions & assignment controls for shipment{' '}
              <span className="font-mono font-bold text-slate-900">{job.reference}</span>
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => void reloadAll()}
          disabled={loading || saving}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-cyan-700 hover:text-cyan-800 self-start sm:self-center transition cursor-pointer"
        >
          <RefreshIcon className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>{loading ? 'Refreshing...' : 'Refresh Suggestions'}</span>
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs font-semibold text-rose-800">
          {error}
        </div>
      )}

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-3">
          <SkeletonMetricCard />
          <SkeletonMetricCard />
          <SkeletonMetricCard />
        </div>
      ) : (
        <form onSubmit={handleSaveAllAssignments} className="space-y-6">
          {/* Invariant Warning if Maker & Checker Match */}
          {hasMakerCheckerConflict && (
            <div className="rounded-xl border border-amber-300 bg-amber-50 p-3.5 text-xs text-amber-900 flex items-start gap-2.5">
              <AlertTriangleIcon className="h-4.5 w-4.5 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold">Maker-Checker Separation Invariant Conflict</p>
                <p className="mt-0.5 text-amber-800 leading-relaxed">
                  The actual preparer (Maker) can never check or verify the same shipment version. Please select different colleagues for Maker and Checker.
                </p>
              </div>
            </div>
          )}

          {/* Three Unified Role Selector Columns */}
          <div className="grid gap-5 md:grid-cols-3">
            {ROLES.map((role) => {
              const roleKey = role.key
              const roleSuggestions = suggestions[roleKey] || []
              const current = currentAssignments[roleKey]

              const selectedVal =
                roleKey === 'maker'
                  ? selectedMaker
                  : roleKey === 'checker'
                    ? selectedChecker
                    : selectedOfficer

              const setSelectedVal =
                roleKey === 'maker'
                  ? setSelectedMaker
                  : roleKey === 'checker'
                    ? setSelectedChecker
                    : setSelectedOfficer

              const customVal =
                roleKey === 'maker'
                  ? customMakerId
                  : roleKey === 'checker'
                    ? customCheckerId
                    : customOfficerId

              const setCustomVal =
                roleKey === 'maker'
                  ? setCustomMakerId
                  : roleKey === 'checker'
                    ? setCustomCheckerId
                    : setCustomOfficerId

              return (
                <div
                  key={roleKey}
                  className="flex flex-col justify-between rounded-xl border border-slate-200 bg-slate-50/70 p-4 space-y-4"
                >
                  <div className="space-y-3">
                    {/* Header with Title & Current Status Pill */}
                    <div>
                      <div className="flex items-center justify-between gap-1">
                        <span className="text-xs font-bold uppercase tracking-wider text-slate-800">
                          {role.title}
                        </span>
                        <span className="rounded-full bg-slate-200/80 px-2 py-0.5 text-[10px] font-bold text-slate-600">
                          {roleSuggestions.length} Suggested
                        </span>
                      </div>
                      <p className="mt-0.5 text-[11px] text-slate-500 leading-snug">{role.subtitle}</p>
                    </div>

                    {/* Current Assigned Status */}
                    <div className="flex items-center justify-between rounded-lg bg-white px-2.5 py-1.5 border border-slate-200 text-xs">
                      <span className="text-slate-400 text-[11px]">Current:</span>
                      {current.name ? (
                        <span className="font-semibold text-slate-800 truncate max-w-[160px]" title={current.name}>
                          {current.name}
                        </span>
                      ) : (
                        <span className="italic text-slate-400">Unassigned</span>
                      )}
                    </div>

                    {/* Dropdown to pick ANY employee or leave unassigned */}
                    <FormField label={`Assign ${role.badgeText}`} required={false}>
                      <SelectInput
                        value={selectedVal}
                        onChange={(e) => setSelectedVal(e.target.value)}
                        className="bg-white font-medium"
                      >
                        <option value="">-- Leave Unassigned --</option>

                        {roleSuggestions.length > 0 && (
                          <optgroup label="⭐ Suggestions (Workload & Scope Match)">
                            {roleSuggestions.map((sug) => (
                              <option key={sug.user_id} value={sug.user_id}>
                                {sug.display_name} (Workload: {sug.pending_workload} jobs)
                              </option>
                            ))}
                          </optgroup>
                        )}

                        <optgroup label="🏢 All Company Staff Directory">
                          {SEEDED_STAFF_DIRECTORY.map((staff: StaffMember) => (
                            <option key={staff.id} value={staff.id}>
                              {staff.name} ({staff.email}) — {staff.roleSummary || 'Staff Operations'}
                            </option>
                          ))}
                        </optgroup>

                        <option value="custom">Manual User UUID (Other)...</option>
                      </SelectInput>
                    </FormField>

                    {/* Custom User ID text input if selected */}
                    {selectedVal === 'custom' && (
                      <FormField label="Target User UUID" required>
                        <TextInput
                          value={customVal}
                          onChange={(e) => setCustomVal(e.target.value)}
                          placeholder="e.g. 3dec8dbc-cea5-51d5-9d1a-75954cd87741"
                          className="font-mono text-xs"
                        />
                      </FormField>
                    )}

                    {/* Quick Suggestion Chips */}
                    {roleSuggestions.length > 0 && (
                      <div className="space-y-1.5 pt-1">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          Quick Suggestions
                        </span>
                        <div className="space-y-1.5">
                          {roleSuggestions.slice(0, 3).map((item) => {
                            const isSelected = selectedVal === item.user_id
                            return (
                              <button
                                key={item.user_id}
                                type="button"
                                onClick={() => setSelectedVal(item.user_id)}
                                className={`w-full flex items-center justify-between rounded-lg p-2 text-left transition border text-xs cursor-pointer ${
                                  isSelected
                                    ? 'border-maritime-700 bg-maritime-50/60 text-maritime-900 font-bold shadow-2xs'
                                    : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50'
                                }`}
                              >
                                <div>
                                  <p className="truncate max-w-[150px]">{item.display_name}</p>
                                  <p className="text-[10px] text-slate-500 font-normal">
                                    Workload: <span className="font-bold text-slate-700">{item.pending_workload}</span> open jobs
                                  </p>
                                </div>
                                {isSelected ? (
                                  <CheckCircleIcon className="h-4 w-4 text-maritime-700 shrink-0" />
                                ) : (
                                  <span className="text-[10px] text-maritime-700 font-semibold hover:underline">
                                    Select
                                  </span>
                                )}
                              </button>
                            )
                          })}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Clear / Leave Unassigned Action */}
                  <div className="pt-2 border-t border-slate-200/80 text-center">
                    <button
                      type="button"
                      onClick={() => setSelectedVal('')}
                      className="text-xs font-semibold text-slate-500 hover:text-rose-600 transition cursor-pointer"
                    >
                      Clear / Leave Unassigned
                    </button>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Reason Justification Field */}
          <FormField
            label="Assignment / Reallocation Justification"
            required
            helperText="Audited justification recorded in the immutable timeline for compliance."
          >
            <TextInput
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Balanced allocation across qualified customs operations specialists"
            />
          </FormField>

          {/* Bottom Action Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-slate-100">
            <div className="flex items-center gap-2 text-xs">
              {pendingChanges.length > 0 ? (
                <span className="rounded-full bg-cyan-50 px-2.5 py-1 font-bold text-cyan-800 border border-cyan-200">
                  {pendingChanges.length} position change(s) ready to apply ({pendingChanges.map((c) => c.label).join(', ')})
                </span>
              ) : (
                <span className="text-slate-500">
                  No changes pending. Select employees above to reassign.
                </span>
              )}
            </div>

            <div className="flex items-center gap-2 self-end sm:self-center">
              {pendingChanges.length > 0 && (
                <button
                  type="button"
                  onClick={handleReset}
                  disabled={saving}
                  className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition cursor-pointer"
                >
                  Reset
                </button>
              )}

              <button
                type="submit"
                disabled={saving || hasMakerCheckerConflict || !reason.trim() || pendingChanges.length === 0}
                className="inline-flex items-center gap-2 rounded-xl bg-maritime-800 px-5 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-maritime-900 disabled:opacity-50 transition cursor-pointer"
              >
                <UserCheckIcon className="h-4 w-4 text-cyan-400" />
                <span>{saving ? 'Applying Workforce Allocation...' : 'Save & Apply Workforce Assignments'}</span>
              </button>
            </div>
          </div>
        </form>
      )}
    </div>
  )
}
