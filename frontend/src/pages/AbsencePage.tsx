import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { AbsenceCandidate, AbsenceNomination } from '../api/contracts'
import { useAuth } from '../auth/AuthContext'
import { PageHeader } from '../components/AppShell'
import { EmptyState, ErrorMessage, InlineLoader } from '../components/Feedback'
import { StatusBadge } from '../components/StatusBadge'
import { requestWorkspaceRefresh } from '../events/workspace'

const displayDate = (value: string) => new Date(value).toLocaleString()

export function AbsencePage() {
  const { token } = useAuth()
  const [candidates, setCandidates] = useState<AbsenceCandidate[]>([])
  const [nominations, setNominations] = useState<AbsenceNomination[]>([])
  const [nomineeId, setNomineeId] = useState('')
  const [validFrom, setValidFrom] = useState('')
  const [validUntil, setValidUntil] = useState('')
  const [reason, setReason] = useState('')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  async function load() {
    setLoading(true)
    setError('')
    try {
      const [candidateItems, nominationItems] = await Promise.all([
        api.absenceCandidates(token!),
        api.absenceNominations(token!),
      ])
      setCandidates(candidateItems)
      setNominations(nominationItems)
      setNomineeId((current) => current || candidateItems[0]?.user_id || '')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Absence information is unavailable.')
    } finally {
      setLoading(false)
    }
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
  useEffect(() => { void load() }, [token])

  async function submit() {
    setError('')
    setMessage('')
    if (!nomineeId || !validFrom || !validUntil || !reason.trim()) {
      setError('Choose a replacement, period, and reason before submitting.')
      return
    }
    const start = new Date(validFrom)
    const end = new Date(validUntil)
    if (Number.isNaN(start.valueOf()) || Number.isNaN(end.valueOf()) || end <= start) {
      setError('The absence end must be after its start.')
      return
    }
    setSubmitting(true)
    try {
      await api.createAbsenceNomination(token!, {
        nominee_user_id: nomineeId,
        valid_from: start.toISOString(),
        valid_until: end.toISOString(),
        reason: reason.trim(),
      })
      setReason('')
      setValidFrom('')
      setValidUntil('')
      setMessage('Absence request submitted for Admin review.')
      await load()
      requestWorkspaceRefresh()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Absence request failed.')
    } finally {
      setSubmitting(false)
    }
  }

  return <div>
    <PageHeader eyebrow="Operations" title="Absence & cover" description="Nominate an eligible colleague for a defined period. Admin approval activates only authorization-valid delegations and flags exceptions for review." />
    {error && <ErrorMessage message={error} />}
    {message && <p className="mb-5 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800" role="status">{message}</p>}
    {loading ? <InlineLoader label="Loading absence options" /> : <>
      <section className="summary-card">
        <h2 className="text-lg font-semibold">Request absence cover</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="form-label md:col-span-2">Eligible replacement<select className="field mt-1" value={nomineeId} onChange={(event) => setNomineeId(event.target.value)}><option value="">Select a colleague</option>{candidates.map((candidate) => <option key={candidate.user_id} value={candidate.user_id}>{candidate.display_name} — eligible for {candidate.eligible_assignment_count} of {candidate.total_assignment_count} active assignments</option>)}</select></label>
          <label className="form-label">From<input className="field mt-1" type="datetime-local" value={validFrom} onChange={(event) => setValidFrom(event.target.value)} /></label>
          <label className="form-label">Until<input className="field mt-1" type="datetime-local" value={validUntil} onChange={(event) => setValidUntil(event.target.value)} /></label>
          <label className="form-label md:col-span-2">Reason<textarea className="field mt-1 min-h-24" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Explain the absence and any handoff context." /></label>
        </div>
        <button className="button-primary mt-4" type="button" disabled={submitting || candidates.length === 0} onClick={() => void submit()}>{submitting ? 'Submitting…' : 'Submit absence request'}</button>
      </section>
      <section className="mt-7">
        <h2 className="text-lg font-semibold">Your requests</h2>
        <p className="mt-1 text-sm text-slate-600">Track Admin decisions and approved cover periods.</p>
        <div className="mt-4 space-y-3">{nominations.length === 0 ? <EmptyState title="No absence requests" message="Your submitted requests will appear here." /> : nominations.map((item) => <article className="summary-card" key={item.id}><div className="flex flex-wrap items-center justify-between gap-2"><p className="font-semibold">{displayDate(item.valid_from)} — {displayDate(item.valid_until)}</p><StatusBadge status={item.status} /></div><p className="mt-2 text-sm text-slate-700">{item.reason}</p>{item.decision_reason && <p className="mt-2 text-sm text-slate-600"><strong>Admin response:</strong> {item.decision_reason}</p>}</article>)}</div>
      </section>
    </>}
  </div>
}
