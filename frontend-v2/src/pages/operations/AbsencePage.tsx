import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import type { AbsenceCandidate, AbsenceNomination } from '../../api/contracts'
import { SEEDED_STAFF_DIRECTORY, type StaffMember } from '../../api/staffDirectory'
import { useAuth } from '../../auth/AuthContext'
import { effectiveRoles, ROLE } from '../../auth/roles'
import { FormField, SelectInput, TextInput, TextareaInput } from '../../components/design-system/FormElements'
import type { Column } from '../../components/design-system/SearchTable'
import { SearchTable } from '../../components/design-system/SearchTable'
import { StatusBadge } from '../../components/design-system/StatusBadge'
import { useToast } from '../../components/feedback/ToastContext'
import { AlertTriangleIcon, CalendarIcon, PlusIcon, UsersIcon } from '../../components/icons'
import { PageHeader } from '../../components/shell/AppShell'

export function AbsencePage() {
  const { token, user } = useAuth()
  const toast = useToast()

  const [candidates, setCandidates] = useState<AbsenceCandidate[]>([])
  const [nominations, setNominations] = useState<AbsenceNomination[]>([])
  const [directoryEmployees, setDirectoryEmployees] = useState<StaffMember[]>([])
  const [loading, setLoading] = useState(true)

  // Form state
  const [nomineeId, setNomineeId] = useState('')
  const [isCustomNominee, setIsCustomNominee] = useState(false)
  const [customNomineeId, setCustomNomineeId] = useState('')
  const [validFrom, setValidFrom] = useState('')
  const [validUntil, setValidUntil] = useState('')
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const roles = effectiveRoles(user)
  const isAdmin = roles.has(ROLE.admin)

  useEffect(() => {
    if (!token) return
    let active = true

    const employeesPromise = isAdmin
      ? api.employees(token, 1, '').catch(() => null)
      : Promise.resolve(null)

    Promise.all([
      api.absenceCandidates(token).catch(() => []),
      api.absenceNominations(token).catch(() => []),
      employeesPromise,
    ])
      .then(([candidateList, nominationList, employeesData]) => {
        if (active) {
          setCandidates(candidateList)
          setNominations(nominationList)
          if (employeesData?.items && employeesData.items.length > 0) {
            setDirectoryEmployees(
              employeesData.items.map((emp) => ({
                id: emp.id,
                name: emp.display_name,
                email: emp.email,
              }))
            )
          }
          if (!nomineeId) {
            if (candidateList.length > 0) {
              setNomineeId(candidateList[0].user_id)
            } else {
              const baseStaff =
                employeesData?.items && employeesData.items.length > 0
                  ? employeesData.items.map((emp) => ({
                      id: emp.id,
                      name: emp.display_name,
                      email: emp.email,
                    }))
                  : SEEDED_STAFF_DIRECTORY
              const eligibleOther = baseStaff.filter(
                (emp) => emp.id !== user?.id && emp.email !== user?.email
              )
              if (eligibleOther.length > 0) {
                setNomineeId(eligibleOther[0].id)
              }
            }
          }
          setLoading(false)
        }
      })
      .catch(() => {
        if (active) {
          setCandidates([])
          setNominations([])
          setLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [token, nomineeId, user?.id, user?.email, isAdmin])

  async function reloadAbsenceData() {
    if (!token) return
    setLoading(true)
    try {
      const employeesPromise = isAdmin
        ? api.employees(token, 1, '').catch(() => null)
        : Promise.resolve(null)

      const [candidateList, nominationList, employeesData] = await Promise.all([
        api.absenceCandidates(token).catch(() => []),
        api.absenceNominations(token).catch(() => []),
        employeesPromise,
      ])
      setCandidates(candidateList)
      setNominations(nominationList)
      if (employeesData?.items && employeesData.items.length > 0) {
        setDirectoryEmployees(
          employeesData.items.map((emp) => ({
            id: emp.id,
            name: emp.display_name,
            email: emp.email,
          }))
        )
      }
    } catch {
      setCandidates([])
      setNominations([])
    } finally {
      setLoading(false)
    }
  }

  const allStaff = directoryEmployees.length > 0 ? directoryEmployees : SEEDED_STAFF_DIRECTORY
  const availableColleagues = allStaff.filter(
    (emp) => emp.id !== user?.id && emp.email !== user?.email
  )
  const candidateIds = new Set(candidates.map((c) => c.user_id))
  const otherColleagues = availableColleagues.filter((emp) => !candidateIds.has(emp.id))

  const conflictingNomination = useMemo(() => {
    if (!validFrom || !validUntil) return null
    const start = new Date(validFrom).getTime()
    const end = new Date(validUntil).getTime()
    if (Number.isNaN(start) || Number.isNaN(end) || end <= start) return null

    return (
      nominations.find((n) => {
        if (n.status !== 'pending' && n.status !== 'approved') return false
        const nStart = new Date(n.valid_from).getTime()
        const nEnd = new Date(n.valid_until).getTime()
        return nStart < end && nEnd > start
      }) || null
    )
  }, [validFrom, validUntil, nominations])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!token) return
    const effectiveNomineeId = isCustomNominee ? customNomineeId.trim() : nomineeId.trim()
    if (!effectiveNomineeId || !validFrom || !validUntil || !reason.trim()) {
      toast.error('Please select an employee colleague and complete all required fields.')
      return
    }

    const start = new Date(validFrom)
    const end = new Date(validUntil)
    if (end <= start) {
      toast.error('Absence end date must be after the start date.')
      return
    }

    if (conflictingNomination) {
      toast.error(
        `Overlapping absence exists: you already have a ${conflictingNomination.status} request from ${new Date(conflictingNomination.valid_from).toLocaleDateString()} to ${new Date(conflictingNomination.valid_until).toLocaleDateString()}. Please select dates outside this period.`
      )
      return
    }

    setSubmitting(true)
    try {
      await api.createAbsenceNomination(token, {
        nominee_user_id: effectiveNomineeId,
        valid_from: start.toISOString(),
        valid_until: end.toISOString(),
        reason: reason.trim(),
      })
      toast.success('Absence nomination submitted for Admin review.')
      setReason('')
      setValidFrom('')
      setValidUntil('')
      setIsCustomNominee(false)
      setCustomNomineeId('')
      await reloadAbsenceData()
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Nomination failed.')
    } finally {
      setSubmitting(false)
    }
  }

  const columns: Column<AbsenceNomination>[] = [
    {
      key: 'dates',
      header: 'Absence Window (UTC)',
      render: (nom) => (
        <div>
          <span className="text-xs font-semibold text-slate-800">
            {new Date(nom.valid_from).toLocaleDateString()} &rarr;{' '}
            {new Date(nom.valid_until).toLocaleDateString()}
          </span>
          <p className="text-[11px] text-slate-400 font-mono">Ver. {nom.version}</p>
        </div>
      ),
    },
    {
      key: 'nominee',
      header: 'Nominated Replacement',
      render: (nom) => {
        const matchedCandidate = candidates.find((c) => c.user_id === nom.nominee_user_id)
        const matchedStaff = allStaff.find((s) => s.id === nom.nominee_user_id)
        const displayName = matchedCandidate?.display_name || matchedStaff?.name || nom.nominee_user_id
        return (
          <div>
            <span className="text-xs font-semibold text-slate-800">
              {displayName}
            </span>
            <p className="font-mono text-[11px] text-slate-400">{nom.nominee_user_id.slice(0, 8)}...</p>
          </div>
        )
      },
    },
    {
      key: 'reason',
      header: 'Recorded Reason',
      render: (nom) => (
        <p className="text-xs text-slate-600 max-w-xs truncate" title={nom.reason}>
          {nom.reason}
        </p>
      ),
    },
    {
      key: 'status',
      header: 'Approval Status',
      render: (nom) => <StatusBadge status={nom.status} size="sm" />,
    },
    {
      key: 'decided',
      header: 'Admin Feedback',
      render: (nom) => (
        <div className="text-xs text-slate-500">
          {nom.decision_reason ? (
            <p className="italic text-slate-700">"{nom.decision_reason}"</p>
          ) : (
            <span>Pending Admin Review</span>
          )}
        </div>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Workforce Continuity"
        title="Absence & Cover Nominations"
        description="Nominate an eligible colleague for a defined period. Admin review activates only authorization-valid delegations and flags exceptions."
      />

      {isAdmin && (
        <div className="rounded-2xl border border-cyan-200 bg-cyan-50/80 p-5 text-xs text-cyan-950 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-xs">
          <div className="flex items-start gap-3 max-w-xl">
            <UsersIcon className="h-5 w-5 text-cyan-700 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold text-sm text-cyan-950">Direct Admin Allocation Available</p>
              <p className="mt-0.5 text-cyan-800 leading-relaxed">
                As an Administrator, you have global authority to directly assign, reallocate, or delegate staff on shipments without submitting an employee absence request.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Link
              to="/admin/jobs"
              className="rounded-xl bg-cyan-700 px-3.5 py-2 font-semibold text-white hover:bg-cyan-800 shadow-xs transition"
            >
              Allocate Shipments &rarr;
            </Link>
            <Link
              to="/admin/requests"
              className="rounded-xl bg-white border border-cyan-300 px-3.5 py-2 font-semibold text-cyan-800 hover:bg-cyan-100 shadow-xs transition"
            >
              Review Requests &rarr;
            </Link>
          </div>
        </div>
      )}

      {/* Nomination Form Card */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
        <div className="flex items-center gap-3 border-b border-slate-100 pb-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-cyan-50 text-cyan-700">
            <CalendarIcon className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900">Request Temporary Absence Cover</h3>
            <p className="text-xs text-slate-500">
              Select an authorized colleague to receive work delegations while you are unavailable.
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="lg:col-span-3">
              <FormField
                label="Replacement Colleague"
                required
                helperText={
                  isCustomNominee
                    ? 'Enter target colleague user UUID directly'
                    : 'Select an authorized colleague to receive work delegations while unavailable.'
                }
              >
                <SelectInput
                  value={isCustomNominee ? 'custom' : nomineeId}
                  onChange={(e) => {
                    if (e.target.value === 'custom') {
                      setIsCustomNominee(true)
                    } else {
                      setIsCustomNominee(false)
                      setNomineeId(e.target.value)
                    }
                  }}
                >
                  {candidates.length > 0 && (
                    <optgroup label="Recommended Eligible Colleagues (Calculated Scope Overlap)">
                      {candidates.map((c) => (
                        <option key={c.user_id} value={c.user_id}>
                          ★ {c.display_name} — eligible for {c.eligible_assignment_count} of{' '}
                          {c.total_assignment_count} active assignments
                        </option>
                      ))}
                    </optgroup>
                  )}
                  <optgroup label={candidates.length > 0 ? 'Other Staff Colleagues' : 'All Operational Staff Colleagues'}>
                    {otherColleagues.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} ({c.email}) {c.roleSummary ? `— ${c.roleSummary}` : ''}
                      </option>
                    ))}
                  </optgroup>
                  <option value="custom">Other / Custom Colleague UUID (Manual entry)...</option>
                </SelectInput>
                {isCustomNominee && (
                  <div className="mt-2">
                    <TextInput
                      value={customNomineeId}
                      onChange={(e) => setCustomNomineeId(e.target.value)}
                      placeholder="Enter colleague user UUID..."
                      className="font-mono text-xs"
                    />
                  </div>
                )}
              </FormField>
            </div>

            <FormField label="Absence Start (From)" required>
              <TextInput
                type="datetime-local"
                value={validFrom}
                onChange={(e) => setValidFrom(e.target.value)}
              />
            </FormField>

            <FormField
              label="Absence End (Until)"
              required
              helperText={
                validFrom && validUntil && new Date(validUntil) <= new Date(validFrom)
                  ? '⚠️ End date must be strictly after the start date.'
                  : undefined
              }
            >
              <TextInput
                type="datetime-local"
                value={validUntil}
                onChange={(e) => setValidUntil(e.target.value)}
                className={
                  validFrom && validUntil && new Date(validUntil) <= new Date(validFrom)
                    ? 'border-rose-400 focus:border-rose-500 ring-rose-200'
                    : ''
                }
              />
            </FormField>

            {conflictingNomination && (
              <div className="rounded-xl border border-amber-300 bg-amber-50/90 p-3.5 text-xs text-amber-900 flex items-start gap-2.5 sm:col-span-2 lg:col-span-3">
                <AlertTriangleIcon className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold">Overlapping Absence Conflict</p>
                  <p className="mt-0.5 text-amber-800 leading-relaxed">
                    You already have an existing <span className="font-semibold uppercase tracking-wider">{conflictingNomination.status}</span> absence request spanning{' '}
                    <strong>{new Date(conflictingNomination.valid_from).toLocaleString()}</strong> to{' '}
                    <strong>{new Date(conflictingNomination.valid_until).toLocaleString()}</strong>.
                    Please select dates outside this interval to avoid an overlapping leave conflict.
                  </p>
                </div>
              </div>
            )}

            <div className="sm:col-span-2 lg:col-span-3">
              <FormField
                label="Absence Justification & Handover Notes"
                required
                helperText="Audited reason reviewed by administration."
              >
                <TextareaInput
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Explain the planned leave and any urgent shipment context..."
                />
              </FormField>
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={submitting || (!isCustomNominee && !nomineeId) || (isCustomNominee && !customNomineeId.trim())}
              className="inline-flex items-center gap-1.5 rounded-xl bg-maritime-800 px-5 py-2.5 text-xs font-semibold text-white shadow-xs hover:bg-maritime-900 disabled:opacity-50 transition cursor-pointer"
            >
              <PlusIcon className="h-4 w-4 text-cyan-400" />
              {submitting ? 'Submitting Request...' : 'Submit Absence Request'}
            </button>
          </div>
        </form>
      </div>

      {/* Submitted Nominations History */}
      <div className="space-y-4">
        <h3 className="text-sm font-bold text-slate-900">Your Submitted Absence Requests</h3>
        <SearchTable
          data={nominations}
          columns={columns}
          keyExtractor={(nom) => nom.id}
          isLoading={loading}
          emptyTitle="No absence nominations recorded"
          emptyDescription="You have not requested temporary absence cover. Submit a request above when planning leave."
        />
      </div>
    </div>
  )
}
