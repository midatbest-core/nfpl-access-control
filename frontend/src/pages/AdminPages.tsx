import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { api, ApiError } from '../api/client'
import type { AdminJob, DashboardOverview, EmployeePage, ReferenceData, UrgentRequest } from '../api/contracts'
import { useAuth } from '../auth/AuthContext'
import { PageHeader } from '../components/AppShell'
import { SearchField } from '../components/Controls'
import { EmptyState, ErrorMessage, InlineLoader } from '../components/Feedback'
import { RoleManager } from '../components/RoleManager'
import { requestWorkspaceRefresh } from '../events/workspace'

const displayDate = (value: string) => new Date(value).toLocaleString()
function useData<T>(loader: () => Promise<T>, dependencies: unknown[]) {
  const [data, setData] = useState<T>()
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const reload = async () => {
    setLoading(true)
    setError('')
    try {
      setData(await loader())
    } catch (error) {
      setError(error instanceof Error ? error.message : 'The request could not be completed.')
    } finally {
      setLoading(false)
    }
  }
  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
  useEffect(() => { void reload() }, dependencies)
  return { data, error, loading, reload }
}
function Problem({ error }: { error: string }) { return error ? <ErrorMessage title="Request unavailable" message={error} /> : null }
function Counts({ title, values }: { title: string; values: Record<string, number> }) { return <section className="summary-card"><p className="summary-label">{title}</p>{Object.entries(values).map(([key,value]) => <p className="flex justify-between py-1 text-sm capitalize" key={key}><span>{key}</span><strong>{value}</strong></p>)}</section> }

export function AdminOverviewPage() {
  const { token, user } = useAuth()
  const overview = useData<DashboardOverview>(() => api.adminOverview(token!), [token])
  const urgent = useData<UrgentRequest[]>(() => api.urgentRequests(token!), [token])
  if (overview.loading || urgent.loading) return <InlineLoader label="Loading Admin overview" />
  const cards = overview.data ? [
    { label: 'Shipment jobs', value: overview.data.total_jobs, to: '/admin/jobs', hint: 'Open job directory' },
    { label: 'Employees', value: overview.data.total_employees, to: '/admin/employees', hint: 'Manage people & roles' },
    { label: 'Pending requests', value: overview.data.pending_requests, to: '/admin/requests', hint: 'Review decisions' },
    { label: 'Needs attention', value: overview.data.reassignment_required_jobs, to: '/admin/attention', hint: 'Resolve assignments' },
  ] : []
  return <div>
    <PageHeader eyebrow="Admin workspace" title={`Good day, ${user?.display_name.split(' ')[0] ?? 'Admin'}`} description="Start with the item that needs action. Every number below opens its working view." action={<Link className="button-primary" to="/admin/jobs/new">Create shipment</Link>} />
    <Problem error={overview.error || urgent.error} />
    {overview.data && <><section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{cards.map((card) => <Link className="summary-card group transition hover:-translate-y-0.5 hover:border-teal-300 hover:shadow-md" key={card.label} to={card.to}><p className="summary-label">{card.label}</p><p className="text-3xl font-bold">{card.value}</p><p className="mt-3 text-xs font-semibold text-teal-700">{card.hint} →</p></Link>)}</section><section className="mt-6 grid gap-4 sm:grid-cols-2"><Link to="/admin/jobs"><Counts title="Workflow stages" values={overview.data.jobs_by_stage} /></Link><Link to="/admin/employees"><Counts title="Employee availability" values={overview.data.employees_by_availability} /></Link></section></>}
    <section className="mt-8"><PageHeader title="Urgent requests" description="The newest pending decisions, with the full queue one click away." action={<Link className="button-secondary" to="/admin/requests">Open all requests</Link>} />{urgent.data?.length ? urgent.data.slice(0, 3).map((item) => <Link className="summary-card mb-3 block transition hover:border-teal-300" to="/admin/requests" key={item.request_id}><p className="font-semibold capitalize">{item.request_type.replaceAll('_', ' ')}</p><p className="mt-1 text-sm text-slate-600">{item.reason}</p><p className="mt-2 text-xs text-slate-500">{displayDate(item.requested_at)} {item.job_id ? `· Job ${item.job_id}` : ''}</p></Link>) : <EmptyState title="No urgent requests" message="There are no pending Admin requests." />}</section>
  </div>
}

export function AdminJobsPage() {
  const { token } = useAuth(); const [search,setSearch] = useState(''); const [offset,setOffset] = useState(0)
  const jobs = useData<AdminJob[]>(() => api.adminJobs(token!, search, offset), [token,search,offset])
  const [target,setTarget] = useState<AdminJob>(); const [reason,setReason] = useState('')
  async function archive() { if (!target || !reason.trim()) return; try { await api.archiveJob(token!,target.id,target.version,reason); setTarget(undefined); setReason(''); jobs.reload() } catch (e) { window.alert(e instanceof Error ? e.message : 'Archive failed') } }
  return <div><PageHeader eyebrow="Admin workspace" title="All jobs" description="Search by shipment reference, client name, or goods description." action={<Link className="button-primary" to="/admin/jobs/new">Create shipment</Link>}/><div className="mb-5 max-w-xl"><SearchField label="Search jobs" value={search} onChange={(value) => { setSearch(value); setOffset(0) }} placeholder="Reference, client, or description" /></div><Problem error={jobs.error}/>{jobs.loading ? <InlineLoader label="Loading jobs"/> : jobs.data?.length ? <><div className="overflow-x-auto rounded-2xl border bg-white"><table className="w-full text-left text-sm"><thead><tr><th className="p-3">Reference</th><th>Client / branch</th><th>Stage</th><th>Assigned IDs</th><th>Updated</th><th /></tr></thead><tbody>{jobs.data.map(job => <tr className="border-t" key={job.id}><td className="p-3"><Link className="font-semibold text-teal-700" to={`/admin/jobs/${job.id}`}>{job.reference}</Link></td><td>{job.client_name}<br/><span className="text-xs text-slate-500">{job.branch_name}</span></td><td className="capitalize">{job.stage}</td><td className="text-xs">Maker: {job.maker_user_id ?? 'Unassigned'}<br/>Checker: {job.checker_user_id ?? 'Unassigned'}<br/>Filer: {job.filing_officer_user_id ?? 'Unassigned'}</td><td>{displayDate(job.updated_at)}</td><td>{!job.archived_at && <button className="font-semibold text-red-700" onClick={() => setTarget(job)}>Archive</button>}</td></tr>)}</tbody></table></div><div className="mt-4 flex justify-between"><button className="button-secondary" disabled={!offset} onClick={() => setOffset(Math.max(0,offset-25))}>Previous</button><button className="button-secondary" disabled={jobs.data.length < 25} onClick={() => setOffset(offset+25)}>Next</button></div></> : <EmptyState title="No jobs found" message="Try another reference, client, or description."/>}{target && <div className="summary-card mt-5"><p className="font-semibold">Archive {target.reference}</p><input className="field mt-3" value={reason} onChange={e => setReason(e.target.value)} placeholder="Required archive reason"/><button className="button-danger mt-3" onClick={() => void archive()}>Confirm archive</button><button className="button-secondary ml-3 mt-3" onClick={() => setTarget(undefined)}>Cancel</button></div>}</div>
}

export function CreateJobPage() {
 const {token}=useAuth(); const [values,setValues]=useState<{reference:string;client_id:string;branch_id:string;direction:'import'|'export';mode:'air'|'fcl'|'lcl';goods_description:string;container_reference:string}>({reference:'',client_id:'',branch_id:'',direction:'import',mode:'air',goods_description:'',container_reference:''}); const [job,setJob]=useState<{id:string;reference:string}>(); const [error,setError]=useState('')
 async function submit(event: React.FormEvent) { event.preventDefault(); try { const result=await api.createJob(token!,values); setJob(result); setError('') } catch(e) { setError(e instanceof Error?e.message:'Creation failed') } }
 return <div><PageHeader eyebrow="Admin workspace" title="Create shipment" description="Use the existing NFPL client and branch identifiers. The backend does not yet expose a secure reference-data directory."/><Problem error={error}/>{job?<AssignmentSuggestions job={job}/>:<form className="max-w-xl space-y-4" onSubmit={e=>void submit(e)}>{(['reference','client_id','branch_id','goods_description','container_reference'] as const).map(key=><label className="form-label capitalize" key={key}>{key.replaceAll('_',' ')}<input className="field mt-1" required={key !== 'goods_description' && key !== 'container_reference'} value={values[key]} onChange={e=>setValues({...values,[key]:e.target.value})}/></label>)}<label className="form-label">Direction<select className="field mt-1" value={values.direction} onChange={e=>setValues({...values,direction:e.target.value as 'import'|'export'})}><option>import</option><option>export</option></select></label><label className="form-label">Mode<select className="field mt-1" value={values.mode} onChange={e=>setValues({...values,mode:e.target.value as 'air'|'fcl'|'lcl'})}><option>air</option><option>fcl</option><option>lcl</option></select></label><button className="button-primary">Create and show assignments</button></form>}</div>
}
export function AssignmentSuggestions({ job }: { job: { id: string; reference: string } }) {
  const { token } = useAuth()
  const data = useData(() => api.suggestions(token!, job.id), [token, job.id])
  const [message, setMessage] = useState('')
  const [savingRole, setSavingRole] = useState<string | null>(null)
  const [assignmentReason, setAssignmentReason] = useState('Admin assignment based on current eligibility and workload.')

  async function assign(role: string, id: string | null) {
    if (savingRole) return
    if (!assignmentReason.trim()) {
      setMessage('Enter an assignment or reallocation reason.')
      return
    }
    setSavingRole(role)
    setMessage('')
    try {
      await api.assign(token!, job.id, role, id, assignmentReason.trim())
      setMessage(`${role.replaceAll('_', ' ')} assignment saved.`)
      await data.reload()
      requestWorkspaceRefresh()
    } catch (error) {
      if (error instanceof ApiError && error.reasonCode === 'assignment_ineligible') {
        setMessage(`${error.message} Choose a different employee from the refreshed suggestions.`)
      } else if (error instanceof ApiError && error.status === 409) {
        setMessage(`${error.message} Reloaded suggestions are shown; choose a currently eligible employee.`)
      } else {
        setMessage(error instanceof Error ? error.message : 'Assignment failed.')
      }
      await data.reload()
    } finally {
      setSavingRole(null)
    }
  }

  return (
    <section className="summary-card">
      <p className="font-semibold">Assignment & reallocation</p>
      <p className="mt-1 text-sm text-slate-600">Choose from employees the backend currently considers eligible for {job.reference}.</p>
      <label className="form-label mt-4">Assignment reason<input className="field mt-1" value={assignmentReason} onChange={(event) => setAssignmentReason(event.target.value)} /></label>
      <Problem error={data.error} />
      {data.loading
        ? <InlineLoader label="Finding eligible employees" />
        : Object.entries(data.data ?? {}).map(([role, items]) => (
          <div className="mt-4" key={role}>
            <p className="font-semibold capitalize">{role.replaceAll('_', ' ')}</p>
            {items.length
              ? items.map((item) => (
                <button className="button-secondary mr-2 mt-2" disabled={savingRole !== null} key={item.user_id} onClick={() => void assign(role, item.user_id)}>
                  {item.display_name} ({item.pending_workload})
                </button>
              ))
              : <p className="text-sm text-amber-700">No currently eligible employee. Leave this responsibility unassigned for later reassignment.</p>}
            <button className="ml-2 text-sm" disabled={savingRole !== null} onClick={() => void assign(role, null)}>
              {savingRole === role ? 'Saving...' : 'Leave unassigned'}
            </button>
          </div>
        ))}
      {message && <p className="mt-4 text-sm" role="status">{message}</p>}
    </section>
  )
}

export function EmployeesPage(){const {token}=useAuth();const [search,setSearch]=useState('');const [page,setPage]=useState(1);const employees=useData<EmployeePage>(()=>api.employees(token!,page,search),[token,page,search]);const references=useData<ReferenceData>(()=>api.referenceData(token!),[token]);async function change(id:string,action:'approve'|'reject'|'activate'|'deactivate'){const reason=window.prompt(`Reason for ${action}`);if(!reason)return;try{await api.employeeAction(token!,id,action,reason);employees.reload()}catch(e){window.alert(e instanceof Error?e.message:'Update failed')}}return <div><PageHeader eyebrow="Admin workspace" title="Employees" description="Review employee availability, workload, roles, and account state."/><input className="field mb-5 max-w-md" aria-label="Search employees" value={search} onChange={e=>{setSearch(e.target.value);setPage(1)}} placeholder="Search employees"/><Problem error={employees.error || references.error}/>{employees.loading?<InlineLoader label="Loading employees"/>:employees.data?.items.map(employee=><div className="summary-card mb-3" key={employee.id}><p className="font-semibold">{employee.display_name}</p><p className="text-sm">{employee.email} - {employee.branch_name ?? 'No branch'}</p><p className="text-sm capitalize">{employee.account_status} / {employee.availability} / {employee.pending_workload} pending</p>{employee.account_status==='pending'&&<><button onClick={()=>void change(employee.id,'approve')}>Approve</button><button className="ml-3" onClick={()=>void change(employee.id,'reject')}>Reject</button></>}{employee.account_status==='active'&&<button className="text-red-700" onClick={()=>void change(employee.id,'deactivate')}>Deactivate</button>}{employee.account_status==='disabled'&&<button onClick={()=>void change(employee.id,'activate')}>Activate</button>}{references.loading?<InlineLoader label="Loading role scopes"/>:references.data&&<RoleManager employee={employee} references={references.data} token={token!} onChanged={employees.reload}/>}</div>)}{employees.data&&<div className="flex justify-between"><button className="button-secondary" disabled={page===1} onClick={()=>setPage(page-1)}>Previous</button><button className="button-secondary" disabled={page*employees.data.limit>=employees.data.total} onClick={()=>setPage(page+1)}>Next</button></div>}</div>}
export function AdminAuditPage() {
  const { token } = useAuth()
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const jobs = useData<AdminJob[]>(
    () => api.adminJobs(token!, search, offset),
    [token, search, offset],
  )

  return (
    <div>
      <PageHeader eyebrow="Admin workspace" title="Audit history" description="Search Admin-visible shipments by reference, then open their authorized immutable history." />
      <label className="form-label max-w-md">Search shipment reference
        <input
          className="field mt-1"
          aria-label="Search audit jobs"
          value={search}
          onChange={(event) => { setSearch(event.target.value); setOffset(0) }}
          placeholder="Reference, client, or description"
        />
      </label>
      <Problem error={jobs.error} />
      {jobs.loading
        ? <InlineLoader label="Loading shipments" />
        : jobs.data?.length
          ? (
            <>
              <div className="mt-5 overflow-x-auto rounded-2xl border bg-white">
                <table className="w-full text-left text-sm">
                  <thead><tr><th className="p-3">Shipment reference</th><th>Client / branch</th><th>Stage</th><th>Updated</th><th /></tr></thead>
                  <tbody>{jobs.data.map((job) => (
                    <tr className="border-t" key={job.id}>
                      <td className="p-3 font-semibold">{job.reference}</td>
                      <td>{job.client_name}<br /><span className="text-xs text-slate-500">{job.branch_name}</span></td>
                      <td className="capitalize">{job.stage}</td>
                      <td>{displayDate(job.updated_at)}</td>
                      <td><Link className="font-semibold text-teal-700" to={`/admin/audit/${job.id}`}>View timeline</Link></td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
              <div className="mt-4 flex justify-between">
                <button className="button-secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 25))}>Previous</button>
                <button className="button-secondary" disabled={jobs.data.length < 25} onClick={() => setOffset(offset + 25)}>Next</button>
              </div>
            </>
          )
          : <EmptyState title="No jobs found" message="Try another shipment reference." />}
    </div>
  )
}
