import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api/client'
import type { AbsenceOutcome, Job, Suggestion, UrgentRequest } from '../api/contracts'
import { useAuth } from '../auth/AuthContext'
import { PageHeader } from '../components/AppShell'
import { ErrorMessage, InlineLoader } from '../components/Feedback'
import { StatusBadge } from '../components/StatusBadge'
import { requestWorkspaceRefresh } from '../events/workspace'
import { AssignmentSuggestions } from './AdminPages'

function useRequest<T>(request: () => Promise<T>, dependencies: unknown[]) {
  const [data, setData] = useState<T>(); const [error, setError] = useState(''); const [loading, setLoading] = useState(true)
  const load = () => { setLoading(true); request().then(setData).catch((e: Error) => setError(e.message)).finally(() => setLoading(false)) }
  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
  useEffect(() => { load() }, dependencies)
  return { data, error, loading, load }
}
function PageError({ text }: { text: string }) { return text ? <ErrorMessage message={text}/> : null }

export function RequestsPage() {
  const { token } = useAuth()
  const requests = useRequest(() => api.urgentRequests(token!), [token])
  const [selected, setSelected] = useState<{ item: UrgentRequest; approved: boolean }>()
  const [reason, setReason] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [outcomes, setOutcomes] = useState<AbsenceOutcome[]>([])
  const [suggestions, setSuggestions] = useState<Record<string, Suggestion[]>>({})
  const [replacement, setReplacement] = useState<Record<string, string>>({})
  const [overrideReason, setOverrideReason] = useState<Record<string, string>>({})

  async function loadOutcomes(nominationId: string) {
    const items = await api.absenceOutcomes(token!, nominationId)
    setOutcomes(items)
    const flagged = items.filter((item) => !['delegated', 'overridden'].includes(item.outcome))
    const entries = await Promise.all(flagged.map(async (item) => {
      const options = await api.suggestions(token!, item.job_id)
      return [item.id, options[item.responsibility] ?? []] as const
    }))
    setSuggestions(Object.fromEntries(entries))
  }

  async function decide(item: UrgentRequest, approved: boolean) {
    if (!reason.trim()) return setError('An Admin decision reason is required.')
    setError('')
    try {
      if (item.request_type === 'absence_nomination') {
        await api.absenceDecision(token!, item.request_id, item.version, approved, reason.trim())
        if (approved) await loadOutcomes(item.request_id)
      } else if (item.request_type === 'edit_request') {
        await api.editDecision(token!, item.request_id, item.version, approved, reason.trim())
      } else {
        if (!approved) return setError('This exceptional API supports approval only.')
        await api.exceptionApproval(token!, item.request_id, item.version)
      }
      setSelected(undefined)
      setReason('')
      setMessage('Request decision recorded and affected work refreshed.')
      requests.load()
      requestWorkspaceRefresh()
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Decision failed.') }
  }

  async function override(item: AbsenceOutcome) {
    const employeeId = replacement[item.id]
    const explanation = overrideReason[item.id]?.trim()
    if (!employeeId || !explanation) return setError('Choose an eligible replacement and enter an override reason.')
    try {
      const updated = await api.overrideAbsenceOutcome(token!, item.id, employeeId, explanation)
      setOutcomes((current) => current.map((outcome) => outcome.id === updated.id ? updated : outcome))
      setMessage('Individual absence delegation overridden and audited.')
      requestWorkspaceRefresh()
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Override failed.') }
  }

  return <div>
    <PageHeader eyebrow="Admin workspace" title="Urgent requests" description="Review the reason and optimistic version, then approve or reject without leaving the queue." />
    {(requests.error || error) && <PageError text={requests.error || error} />}
    {message && <p className="mb-5 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800" role="status">{message}</p>}
    {requests.loading ? <InlineLoader label="Loading requests" /> : requests.data?.length ? requests.data.map((item) => <section className="summary-card mb-3" key={item.request_id}><div className="flex flex-col justify-between gap-4 sm:flex-row"><div><p className="font-semibold capitalize">{item.request_type.replaceAll('_', ' ')}</p><p className="mt-1 text-sm text-slate-600">{item.reason}</p><p className="mt-2 text-xs text-slate-500">Request version {item.version}</p>{item.job_id && <Link className="mt-2 inline-block text-sm font-semibold text-teal-700" to={`/admin/jobs/${item.job_id}`}>Open shipment</Link>}</div><div className="flex gap-2 self-start"><button className="button-primary" onClick={() => { setSelected({ item, approved: true }); setReason('') }}>Approve</button>{item.request_type !== 'exceptional_transition' && <button className="button-secondary" onClick={() => { setSelected({ item, approved: false }); setReason('') }}>Reject</button>}</div></div>{selected?.item.request_id === item.request_id && <div className="mt-4 border-t border-slate-200 pt-4"><label className="form-label">Decision reason<textarea className="field mt-1 min-h-20" value={reason} onChange={(event) => setReason(event.target.value)} /></label><button className={selected.approved ? 'button-primary mt-3' : 'button-danger mt-3'} onClick={() => void decide(item, selected.approved)}>Confirm {selected.approved ? 'approval' : 'rejection'}</button><button className="button-secondary ml-2 mt-3" onClick={() => setSelected(undefined)}>Cancel</button></div>}</section>) : <p className="summary-card text-sm text-slate-600">No urgent requests are waiting.</p>}
    {outcomes.length > 0 && <section className="mt-8"><PageHeader title="Absence transfer results" description="Eligible jobs were transferred automatically. Resolve only flagged jobs below." />{outcomes.map((item) => <article className="summary-card mb-3" key={item.id}><div className="flex flex-wrap items-center justify-between gap-2"><Link className="font-semibold text-teal-700" to={`/admin/jobs/${item.job_id}`}>Job {item.job_id}</Link><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold capitalize">{item.outcome}</span></div><p className="mt-2 text-sm capitalize">{item.responsibility.replaceAll('_', ' ')}</p><p className="mt-1 text-sm text-slate-600">{item.reason}</p>{!['delegated', 'overridden'].includes(item.outcome) && <div className="mt-4 grid gap-3 sm:grid-cols-2"><label className="form-label">Eligible replacement<select className="field mt-1" value={replacement[item.id] ?? ''} onChange={(event) => setReplacement((current) => ({ ...current, [item.id]: event.target.value }))}><option value="">Choose replacement</option>{suggestions[item.id]?.map((option) => <option key={option.user_id} value={option.user_id}>{option.display_name} · {option.pending_workload} open</option>)}</select></label><label className="form-label">Override reason<input className="field mt-1" value={overrideReason[item.id] ?? ''} onChange={(event) => setOverrideReason((current) => ({ ...current, [item.id]: event.target.value }))} /></label><button className="button-primary sm:col-span-2 sm:justify-self-start" onClick={() => void override(item)}>Override this job nomination</button></div>}</article>)}</section>}
  </div>
}

export function JobDetailsPage() {
  const { jobId = '' } = useParams()
  const { token } = useAuth()
  const job = useRequest<Job>(() => api.job(token!, jobId), [token, jobId])
  const [reason, setReason] = useState('')
  const [attention, setAttention] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function cancel() {
    if (!job.data || !reason.trim()) return setError('A cancellation reason is required.')
    try {
      await api.cancelJob(token!, job.data.id, job.data.version, reason.trim())
      setMessage('Shipment cancelled and audited.')
      setReason('')
      job.load()
      requestWorkspaceRefresh()
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Cancellation failed.') }
  }

  async function exception(action: 'cancel' | 'reopen') {
    if (!job.data || !reason.trim()) return setError(`A ${action} reason is required.`)
    try {
      await api.exceptionRequest(token!, job.data.id, action, reason.trim())
      setReason('')
      setMessage(`Exceptional ${action} request recorded for the configured approval flow.`)
      requestWorkspaceRefresh()
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Request failed.') }
  }

  async function sendAttention() {
    if (!job.data || !attention.trim()) return setError('Explain what responsible employees need to address.')
    try {
      const receipt = await api.adminAttention(token!, job.data.id, attention.trim())
      setAttention('')
      setMessage(`Attention sent to ${receipt.delivered} currently authorized employee${receipt.delivered === 1 ? '' : 's'}.`)
      requestWorkspaceRefresh()
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Attention message failed.') }
  }

  if (job.loading) return <InlineLoader label="Loading shipment" />
  return <div>
    <PageHeader eyebrow="Admin workspace" title={job.data?.reference ?? 'Shipment'} description="Resolve responsibility, exceptions, and staff attention from one authorized shipment view." action={<Link className="button-secondary" to="/admin/jobs">Back to jobs</Link>} />
    {(job.error || error) && <PageError text={job.error || error} />}
    {message && <p className="mb-5 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800" role="status">{message}</p>}
    {job.data && <>
      <section className="grid gap-4 md:grid-cols-3"><div className="summary-card"><p className="summary-label">Workflow</p><StatusBadge status={job.data.stage} /><p className="mt-3 text-xs">Record version {job.data.version}</p></div><div className="summary-card md:col-span-2"><p className="summary-label">Shipment</p><p className="font-semibold uppercase">{job.data.direction} / {job.data.mode}</p><p className="mt-2 text-sm text-slate-600">{job.data.client_name} · {job.data.branch_name}</p><p className="mt-3 text-sm">{job.data.goods_description}</p></div></section>
      <div className="mt-5"><AssignmentSuggestions job={job.data} /></div>
      <section className="summary-card mt-5"><h2 className="text-lg font-semibold">Administrative workflow control</h2><p className="mt-1 text-sm text-slate-600">Reasons and optimistic job versions are checked and recorded by the server.</p><label className="form-label mt-4">Required reason<textarea className="field mt-1 min-h-24" value={reason} onChange={(event) => setReason(event.target.value)} /></label><div className="mt-3 flex flex-wrap gap-3">{!['filed', 'cancelled'].includes(job.data.stage) && <button className="button-danger" onClick={() => void cancel()}>Cancel shipment</button>}{job.data.stage === 'filed' && <button className="button-danger" onClick={() => void exception('cancel')}>Request filed cancellation</button>}{['filed', 'cancelled'].includes(job.data.stage) && <button className="button-secondary" onClick={() => void exception('reopen')}>Request reopening</button>}<Link className="button-secondary" to={`/admin/audit/${job.data.id}`}>View audit timeline</Link></div></section>
      <section className="summary-card mt-5"><h2 className="text-lg font-semibold">Send attention to responsible staff</h2><p className="mt-1 text-sm text-slate-600">The server targets only current assignees and effective delegates and prevents identical duplicates.</p><label className="form-label mt-4">Explanation<textarea className="field mt-1 min-h-24" value={attention} onChange={(event) => setAttention(event.target.value)} /></label><button className="button-primary mt-3" onClick={() => void sendAttention()}>Send attention notification</button></section>
    </>}
  </div>
}
