import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { api } from '../api/client'
import type {
  Job,
  JobResponsibilityDetail,
  Notification,
  WorkQueuePage,
} from '../api/contracts'
import { useAuth } from '../auth/AuthContext'
import { PageHeader } from '../components/AppShell'
import { ConfirmationDialog } from '../components/Controls'
import { EmptyState, ErrorMessage, InlineLoader } from '../components/Feedback'
import { CheckerPanel, FilingPanel } from '../components/OperationalRoleActions'
import { StatusBadge } from '../components/StatusBadge'

const displayDate = (value: string) => new Date(value).toLocaleString()
const responsibilityLabelSafe = (value: string) => value
  .split('_')
  .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
  .join(' ')

export function MyWorkPage() {
  const { token } = useAuth()
  const [data, setData] = useState<WorkQueuePage>()
  const [cursor, setCursor] = useState<string>()
  const [cursorStack, setCursorStack] = useState<Array<string | undefined>>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let current = true
    api.myWork(token!, cursor)
      .then((result) => { if (current) setData(result) })
      .catch((caught: Error) => { if (current) setError(caught.message) })
      .finally(() => { if (current) setLoading(false) })
    return () => { current = false }
  }, [token, cursor])

  function nextPage() {
    if (!data?.next_cursor) return
    setLoading(true)
    setError('')
    setCursorStack((values) => [...values, cursor])
    setCursor(data.next_cursor)
  }

  function previousPage() {
    const previous = cursorStack.at(-1)
    setLoading(true)
    setError('')
    setCursorStack((values) => values.slice(0, -1))
    setCursor(previous)
  }

  return (
    <div>
      <PageHeader
        eyebrow="Operations"
        title="My work"
        description="Only shipments you can act on now are shown. Access is checked again when you open or update a shipment."
      />
      {error && <ErrorMessage message={error} />}
      {loading && <InlineLoader label="Loading your authorized work" />}
      {!loading && data && (
        <>
          <div className="mb-5 rounded-2xl border border-teal-100 bg-teal-50 p-4">
            <p className="text-sm text-teal-900"><strong>{data.count}</strong> pending {data.count === 1 ? 'shipment' : 'shipments'}</p>
          </div>
          {data.items.length === 0 ? (
            <EmptyState title="No action required" message="There are no currently authorized shipments waiting for you." />
          ) : (
            <div className="space-y-3">
              {data.items.map((item) => (
                <article className="summary-card" key={`${item.job_id}-${item.responsibility}`}>
                  <div className="flex flex-col justify-between gap-4 sm:flex-row">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Link className="font-semibold text-teal-700" to={`/work/jobs/${item.job_id}`}>{item.reference}</Link>
                        <StatusBadge status={item.stage} />
                        {item.is_delegated && <span className="rounded-full bg-sky-50 px-2.5 py-1 text-xs font-semibold text-sky-700">Delegated</span>}
                      </div>
                      <p className="mt-2 text-sm text-slate-700">{item.client_name} - {item.branch_name}</p>
                      <p className="mt-1 text-xs uppercase tracking-wide text-slate-500">{item.direction} / {item.mode} / {responsibilityLabelSafe(item.responsibility)}</p>
                      {item.feedback && <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900"><strong>Feedback:</strong> {item.feedback}</p>}
                    </div>
                    <div className="sm:text-right">
                      <p className="text-sm font-semibold text-ink">{item.next_action}</p>
                      <p className="mt-1 text-xs text-slate-500">Assigned {displayDate(item.assigned_at)}</p>
                      <Link className="button-primary mt-3" to={`/work/jobs/${item.job_id}`}>Open shipment</Link>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
          <nav className="mt-5 flex justify-between" aria-label="My Work pagination">
            <button className="button-secondary" disabled={cursorStack.length === 0} onClick={previousPage}>Previous</button>
            <button className="button-secondary" disabled={!data.next_cursor} onClick={nextPage}>Next</button>
          </nav>
        </>
      )}
    </div>
  )
}

export function OperationalJobPage() {
  const { jobId = '' } = useParams()
  const { token } = useAuth()
  const [job, setJob] = useState<Job>()
  const [responsibilities, setResponsibilities] = useState<JobResponsibilityDetail[]>([])
  const [goodsDescription, setGoodsDescription] = useState('')
  const [containerReference, setContainerReference] = useState('')
  const [justification, setJustification] = useState('')
  const [editReason, setEditReason] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [confirmSubmit, setConfirmSubmit] = useState(false)

  async function load() {
    setLoading(true)
    setError('')
    try {
      const [shipment, assignments] = await Promise.all([
        api.job(token!, jobId),
        api.jobResponsibilities(token!, jobId),
      ])
      setJob(shipment)
      setResponsibilities(assignments)
      setGoodsDescription(shipment.goods_description)
      setContainerReference(shipment.container_reference ?? '')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Shipment is unavailable.')
    } finally {
      setLoading(false)
    }
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
  useEffect(() => { void load() }, [jobId, token])

  const makerResponsibility = responsibilities.find((item) => item.responsibility === 'maker')
  const checkerResponsibility = responsibilities.find((item) => item.responsibility === 'checker')
  const filingResponsibility = responsibilities.find((item) => item.responsibility === 'filing_officer')
  const isMaker = makerResponsibility?.current_actor_responsible === true
  const isChecker = checkerResponsibility?.current_actor_responsible === true
  const isFilingOfficer = filingResponsibility?.current_actor_responsible === true
  const canEdit = Boolean(isMaker && job && !job.maker_edit_locked && ['confirmed', 'reopened'].includes(job.stage))
  const isCorrection = Boolean(job && (job.checklist_revision > 0 || job.maker_correction_required))
  const canRequestEdit = Boolean(isMaker && job?.maker_edit_locked && ['prepared', 'checked'].includes(job.stage))

  async function save() {
    if (!job) return
    setError('')
    setMessage('')
    try {
      const updated = await api.updateJob(token!, job.id, {
        expected_version: job.version,
        goods_description: goodsDescription,
        container_reference: containerReference || null,
      })
      setJob(updated)
      setMessage('Shipment details saved.')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Shipment update failed.')
    }
  }

  async function submit() {
    if (!job) return
    setConfirmSubmit(false)
    if (isCorrection && !justification.trim()) {
      setError('Explain what was corrected before resubmitting.')
      return
    }
    setError('')
    setMessage('')
    try {
      const updated = await api.prepareJob(token!, job.id, job.version, justification.trim())
      setJob(updated)
      setJustification('')
      setMessage(isCorrection ? 'Corrections resubmitted for independent verification.' : 'Shipment submitted for independent verification.')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Submission failed.')
    }
  }

  async function requestEdit() {
    if (!job || !editReason.trim()) {
      setError('Explain why the submitted shipment needs to be edited.')
      return
    }
    setError('')
    try {
      const request = await api.requestJobEdit(token!, job.id, editReason.trim())
      setEditReason('')
      setMessage(`Edit request submitted. Current status: ${request.status}.`)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Edit request failed.')
    }
  }

  if (loading) return <InlineLoader label="Loading authorized shipment" />
  if (!job) return <div><PageHeader eyebrow="Operations" title="Shipment unavailable" description="The shipment may no longer be visible or assigned to you." />{error && <ErrorMessage message={error} />}</div>

  return (
    <div>
      <PageHeader
        eyebrow="Operations"
        title={job.reference}
        description="Shipment access and every action are revalidated by the server."
        action={<Link className="button-secondary" to="/work">Back to My Work</Link>}
      />
      {error && <ErrorMessage message={error} />}
      {message && <p className="mb-4 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800" role="status">{message}</p>}
      <section className="grid gap-4 md:grid-cols-3">
        <div className="summary-card"><p className="summary-label">Workflow</p><div className="mt-2"><StatusBadge status={job.stage} /></div><p className="mt-3 text-xs">Revision {job.checklist_revision} / Record version {job.version}</p></div>
        <div className="summary-card"><p className="summary-label">Shipment</p><p className="mt-2 text-sm font-semibold uppercase">{job.direction} / {job.mode}</p><p className="mt-2 text-xs">{job.client_name}<br />{job.branch_name}</p></div>
        <div className="summary-card"><p className="summary-label">Responsibility</p>{responsibilities.map((item) => <p className="mt-2 text-xs" key={item.responsibility}><strong>{responsibilityLabelSafe(item.responsibility)}:</strong> {item.display_name ?? 'Unassigned'}{item.current_actor_responsible ? item.via_delegation ? ' (delegated to you)' : ' (you)' : ''}</p>)}</div>
      </section>
      {job.last_return_reason && <section className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-5"><p className="font-semibold text-amber-950">Correction feedback</p><p className="mt-2 text-sm text-amber-900">{job.last_return_reason}</p>{job.last_return_category && <p className="mt-2 text-xs uppercase text-amber-800">Return category: {job.last_return_category}</p>}</section>}
      {isChecker && job.last_maker_justification && <section className="mt-5 rounded-2xl border border-sky-200 bg-sky-50 p-5"><p className="font-semibold text-sky-950">Maker resubmission explanation</p><p className="mt-2 text-sm text-sky-900">{job.last_maker_justification}</p></section>}
      {isFilingOfficer && job.last_checker_justification && <section className="mt-5 rounded-2xl border border-sky-200 bg-sky-50 p-5"><p className="font-semibold text-sky-950">Checker verification explanation</p><p className="mt-2 text-sm text-sky-900">{job.last_checker_justification}</p></section>}
      <section className="summary-card mt-5">
        <h2 className="text-lg font-semibold">Shipment details</h2>
        <div className="mt-4 space-y-4">
          <label className="form-label">Goods description<textarea className="field mt-1 min-h-32" disabled={!canEdit} value={goodsDescription} onChange={(event) => setGoodsDescription(event.target.value)} /></label>
          <label className="form-label">Container or reference number<input className="field mt-1" disabled={!canEdit} value={containerReference} onChange={(event) => setContainerReference(event.target.value)} /></label>
          <div className="grid gap-3 sm:grid-cols-2"><label className="form-label">Direction<input className="field mt-1 uppercase" disabled value={job.direction} /></label><label className="form-label">Mode<input className="field mt-1 uppercase" disabled value={job.mode} /></label></div>
        </div>
        {canEdit && (
          <div className="mt-5 border-t border-slate-200 pt-5">
            {isCorrection && <label className="form-label">Correction and resubmission justification<textarea className="field mt-1 min-h-24" value={justification} onChange={(event) => setJustification(event.target.value)} placeholder="Explain what changed or why unchanged information remains correct." /></label>}
            <button className="button-secondary mt-3" type="button" onClick={() => void save()}>Save shipment details</button>
            <button className="button-primary ml-3 mt-3" type="button" onClick={() => setConfirmSubmit(true)}>{isCorrection ? 'Resubmit corrections' : 'Submit for verification'}</button>
          </div>
        )}
        {isMaker && job.maker_edit_locked && <p className="mt-5 rounded-lg bg-slate-100 p-3 text-sm text-slate-700">This submitted revision is locked. Editing remains unavailable unless it is returned or an Admin independently approves an edit request.</p>}
      </section>
      {canRequestEdit && <section className="summary-card mt-5"><h2 className="font-semibold">Request a post-submission edit</h2><p className="mt-1 text-sm text-slate-600">An independent Admin must approve this job-specific request.</p><label className="form-label mt-4">Reason<textarea className="field mt-1 min-h-24" value={editReason} onChange={(event) => setEditReason(event.target.value)} /></label><button className="button-secondary mt-3" type="button" onClick={() => void requestEdit()}>Send edit request</button></section>}
      {isChecker && job.stage === 'prepared' && (
        <CheckerPanel
          job={job}
          key={job.version}
          token={token!}
          onUpdated={setJob}
          onMessage={(value, isError) => {
            setError(isError ? value : '')
            setMessage(isError ? '' : value)
          }}
        />
      )}
      {isFilingOfficer && job.stage === 'checked' && (
        <FilingPanel
          job={job}
          key={job.version}
          token={token!}
          onUpdated={setJob}
          onMessage={(value, isError) => {
            setError(isError ? value : '')
            setMessage(isError ? '' : value)
          }}
        />
      )}
      <ConfirmationDialog
        open={confirmSubmit}
        title={isCorrection ? 'Resubmit these corrections?' : 'Submit this shipment?'}
        message="Submission locks Maker editing and sends the revision for independent Checker verification."
        confirmLabel={isCorrection ? 'Resubmit corrections' : 'Submit shipment'}
        onConfirm={() => void submit()}
        onCancel={() => setConfirmSubmit(false)}
      />
    </div>
  )
}

export function NotificationsPage() {
  const { token, user } = useAuth()
  const navigate = useNavigate()
  const [items, setItems] = useState<Notification[]>([])
  const [unread, setUnread] = useState(0)
  const [before, setBefore] = useState<string>()
  const [beforeStack, setBeforeStack] = useState<Array<string | undefined>>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function load() {
    setLoading(true)
    setError('')
    try {
      const [notifications, count] = await Promise.all([
        api.notifications(token!, before),
        api.unreadNotificationCount(token!),
      ])
      setItems(notifications)
      setUnread(count.count)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Notifications are unavailable.')
    } finally {
      setLoading(false)
    }
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
  useEffect(() => { void load() }, [token, before])

  async function read(item: Notification, open: boolean) {
    try {
      if (!item.read_at) await api.markNotificationRead(token!, item.id)
      await load()
      if (open && item.job_id) {
        const path = user?.kind === 'client'
          ? `/client/shipments/${item.job_id}`
          : user?.roles.some((role) => role.role_slug === 'admin')
            ? `/admin/jobs/${item.job_id}`
            : `/work/jobs/${item.job_id}`
        navigate(path)
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Notification update failed.')
    }
  }

  function nextPage() {
    const last = items.at(-1)
    if (!last) return
    setBeforeStack((values) => [...values, before])
    setBefore(last.created_at)
  }

  function previousPage() {
    const previous = beforeStack.at(-1)
    setBeforeStack((values) => values.slice(0, -1))
    setBefore(previous)
  }

  return (
    <div>
      <PageHeader eyebrow="Your workspace" title="Notifications" description={`${unread} unread actionable ${unread === 1 ? 'notification' : 'notifications'}.`} />
      {error && <ErrorMessage message={error} />}
      {loading ? <InlineLoader label="Loading notifications" /> : items.length === 0 ? (
        <EmptyState title="No notifications" message="There are no authorized notifications on this page." />
      ) : (
        <div className="space-y-3">
          {items.map((item) => <article className={`summary-card ${item.read_at ? '' : 'border-teal-300'}`} key={item.id}><div className="flex flex-col justify-between gap-3 sm:flex-row"><div><p className="font-semibold">{item.message}</p><p className="mt-1 text-xs text-slate-500">{item.job_reference ? `${item.job_reference} - ` : ''}{displayDate(item.created_at)}</p></div><div className="flex gap-2">{!item.read_at && <button className="button-secondary" onClick={() => void read(item, false)}>Mark read</button>}{item.job_id && <button className="button-primary" onClick={() => void read(item, true)}>Open shipment</button>}</div></div></article>)}
        </div>
      )}
      <nav className="mt-5 flex justify-between" aria-label="Notification pagination">
        <button className="button-secondary" disabled={beforeStack.length === 0} onClick={previousPage}>Previous</button>
        <button className="button-secondary" disabled={items.length < 25} onClick={nextPage}>Next</button>
      </nav>
    </div>
  )
}
