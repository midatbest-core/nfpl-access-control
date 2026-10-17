import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import { api } from '../api/client'
import type { Job, UrgentRequest } from '../api/contracts'
import { useAuth } from '../auth/AuthContext'
import { PageHeader } from '../components/AppShell'
import { ErrorMessage, InlineLoader } from '../components/Feedback'

function useRequest<T>(request: () => Promise<T>, dependencies: unknown[]) {
  const [data, setData] = useState<T>(); const [error, setError] = useState(''); const [loading, setLoading] = useState(true)
  const load = () => { setLoading(true); request().then(setData).catch((e: Error) => setError(e.message)).finally(() => setLoading(false)) }
  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
  useEffect(() => { load() }, dependencies)
  return { data, error, loading, load }
}
function PageError({ text }: { text: string }) { return text ? <ErrorMessage message={text}/> : null }

export function RequestsPage() {
  const { token } = useAuth(); const requests = useRequest(() => api.urgentRequests(token!), [token]); const [message, setMessage] = useState('')
  async function decide(item: UrgentRequest, approved: boolean) {
    const reason = window.prompt(approved ? 'Approval reason' : 'Rejection reason'); if (!reason) return
    try {
      if (item.request_type === 'absence_nomination') await api.absenceDecision(token!, item.request_id, item.version, approved, reason)
      else if (item.request_type === 'edit_request') await api.editDecision(token!, item.request_id, item.version, approved, reason)
      else { if (!approved) { setMessage('Exceptional requests have no rejection endpoint in the approved backend contract.'); return } await api.exceptionApproval(token!, item.request_id, item.version) }
      setMessage('Request decision recorded.'); requests.load()
    } catch (e: unknown) { setMessage(e instanceof Error ? e.message : 'Decision failed') }
  }
  return <div><PageHeader eyebrow="Admin workspace" title="Urgent requests" description="Approve or reject only actions supported by the existing secured API."/><PageError text={requests.error || message}/>{requests.loading?<InlineLoader label="Loading requests"/>:requests.data?.map(item=><section className="summary-card mb-3" key={item.request_id}><p className="font-semibold capitalize">{item.request_type.replaceAll('_',' ')}</p><p className="text-sm text-slate-600">{item.reason}</p><p className="mt-1 text-xs">Request version {item.version}</p><button className="button-primary mt-3" onClick={()=>void decide(item,true)}>Approve</button>{item.request_type !== 'exceptional_transition'&&<button className="button-secondary ml-3 mt-3" onClick={()=>void decide(item,false)}>Reject</button>}</section>)}</div>
}

export function JobDetailsPage() {
  const { jobId = '' } = useParams(); const { token } = useAuth(); const job = useRequest<Job>(() => api.job(token!, jobId), [token,jobId]); const [message,setMessage] = useState('')
  async function cancel() { if (!job.data) return; const reason=window.prompt('Cancellation reason'); if(!reason) return; try { await api.cancelJob(token!,job.data.id,job.data.version,reason); setMessage('Cancellation submitted.'); job.load() } catch(e: unknown) { setMessage(e instanceof Error?e.message:'Cancellation failed') } }
  async function exception(action: 'cancel' | 'reopen') { if (!job.data) return; const reason=window.prompt(`Exceptional ${action} reason`); if(!reason)return; try { await api.exceptionRequest(token!,job.data.id,action,reason); setMessage('Exceptional request submitted for independent approval.'); } catch(e: unknown) { setMessage(e instanceof Error?e.message:'Request failed') } }
  if(job.loading)return <InlineLoader label="Loading shipment"/>
  return <div><PageHeader eyebrow="Admin workspace" title={job.data?.reference ?? 'Shipment'} description="Authorized shipment details and exceptional controls."/><PageError text={job.error || message}/>{job.data&&<section className="summary-card"><p>{job.data.direction} / {job.data.mode} / {job.data.stage}</p><p className="mt-2">{job.data.goods_description}</p><p className="mt-2 text-sm">Version {job.data.version}</p>{!['filed','cancelled'].includes(job.data.stage)&&<button className="button-danger mt-4" onClick={()=>void cancel()}>Cancel shipment</button>}{job.data.stage==='filed'&&<button className="button-danger mt-4" onClick={()=>void exception('cancel')}>Request filed cancellation</button>}{['filed','cancelled'].includes(job.data.stage)&&<button className="button-secondary ml-3 mt-4" onClick={()=>void exception('reopen')}>Request reopening</button>}</section>}</div>
}
