import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { Job, ReferenceData } from '../api/contracts'
import { useAuth } from '../auth/AuthContext'
import { PageHeader } from '../components/AppShell'
import { EmptyState, ErrorMessage, InlineLoader } from '../components/Feedback'
import { AssignmentSuggestions } from './AdminPages'

export function CreateJobWithSelectionsPage() {
  const { token } = useAuth()
  const [references, setReferences] = useState<ReferenceData>()
  const [job, setJob] = useState<Job>()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [form, setForm] = useState({
    reference: '',
    client_id: '',
    branch_id: '',
    direction: 'import' as 'import' | 'export',
    mode: 'air' as 'air' | 'fcl' | 'lcl',
    goods_description: '',
    container_reference: '',
  })

  useEffect(() => {
    let current = true
    api.referenceData(token!)
      .then((data) => { if (current) setReferences(data) })
      .catch((caught: Error) => { if (current) setError(caught.message) })
      .finally(() => { if (current) setLoading(false) })
    return () => { current = false }
  }, [token])

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setError('')
    try {
      setJob(await api.createJob(token!, form))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Shipment creation failed.')
    }
  }

  if (job) return <AssignmentSuggestions job={job} />
  const noReferences = references && (references.clients.length === 0 || references.branches.length === 0)
  return (
    <div>
      <PageHeader eyebrow="Admin workspace" title="Create shipment" description="Select client and branch from authorized NFPL reference data." />
      {error && <ErrorMessage message={error} />}
      {loading && <InlineLoader label="Loading clients and branches" />}
      {noReferences && <EmptyState title="Reference data unavailable" message="At least one client and branch must exist before a shipment can be created." />}
      {references && !noReferences && (
        <form className="max-w-xl space-y-4" onSubmit={(event) => void submit(event)}>
          <label className="form-label">Shipment reference<input className="field mt-1" required value={form.reference} onChange={(event) => setForm({ ...form, reference: event.target.value })} /></label>
          <label className="form-label">Client<select className="field mt-1" aria-label="Client" required value={form.client_id} onChange={(event) => setForm({ ...form, client_id: event.target.value })}><option value="">Select client</option>{references.clients.map((item) => <option value={item.id} key={item.id}>{item.name} ({item.code})</option>)}</select></label>
          <label className="form-label">Branch<select className="field mt-1" aria-label="Branch" required value={form.branch_id} onChange={(event) => setForm({ ...form, branch_id: event.target.value })}><option value="">Select branch</option>{references.branches.map((item) => <option value={item.id} key={item.id}>{item.name} ({item.code})</option>)}</select></label>
          <label className="form-label">Direction<select className="field mt-1" value={form.direction} onChange={(event) => setForm({ ...form, direction: event.target.value as 'import' | 'export' })}><option>import</option><option>export</option></select></label>
          <label className="form-label">Mode<select className="field mt-1" value={form.mode} onChange={(event) => setForm({ ...form, mode: event.target.value as 'air' | 'fcl' | 'lcl' })}><option>air</option><option>fcl</option><option>lcl</option></select></label>
          <label className="form-label">Goods description<input className="field mt-1" value={form.goods_description} onChange={(event) => setForm({ ...form, goods_description: event.target.value })} /></label>
          <label className="form-label">Container/reference number<input className="field mt-1" value={form.container_reference} onChange={(event) => setForm({ ...form, container_reference: event.target.value })} /></label>
          <button className="button-primary">Create and show assignments</button>
        </form>
      )}
    </div>
  )
}
