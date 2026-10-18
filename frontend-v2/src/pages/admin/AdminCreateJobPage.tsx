import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import type { Job, ReferenceData } from '../../api/contracts'
import { useAuth } from '../../auth/AuthContext'
import { AssignmentSuggestions } from '../../components/admin/AssignmentSuggestions'
import { EmptyState } from '../../components/design-system/EmptyState'
import { FormField, SelectInput, TextInput } from '../../components/design-system/FormElements'
import { SkeletonMetricsGrid } from '../../components/design-system/LoadingSkeleton'
import { useToast } from '../../components/feedback/ToastContext'
import { ArrowLeftIcon, PlusIcon } from '../../components/icons'
import { PageHeader } from '../../components/shell/AppShell'

export function AdminCreateJobPage() {
  const { token } = useAuth()
  const toast = useToast()
  const [references, setReferences] = useState<ReferenceData | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [createdJob, setCreatedJob] = useState<Job | null>(null)

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
    if (!token) return
    let active = true

    api.referenceData(token)
      .then((data) => {
        if (active) {
          setReferences(data)
          setForm((prev) => ({
            ...prev,
            client_id: prev.client_id || (data.clients.length > 0 ? data.clients[0].id : ''),
            branch_id: prev.branch_id || (data.branches.length > 0 ? data.branches[0].id : ''),
          }))
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
  }, [token])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!token) return
    if (!form.reference.trim()) {
      setError('Shipment reference identifier is required.')
      return
    }
    if (!form.client_id || !form.branch_id) {
      setError('Client and branch selection is required.')
      return
    }

    setSubmitting(true)
    setError(null)

    try {
      const result = await api.createJob(token, {
        reference: form.reference.trim(),
        client_id: form.client_id,
        branch_id: form.branch_id,
        direction: form.direction,
        mode: form.mode,
        goods_description: form.goods_description.trim(),
        container_reference: form.container_reference.trim() || null,
      })
      toast.success(`Shipment ${result.reference} created successfully.`)
      setCreatedJob(result)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to create shipment.')
      toast.error(caught instanceof Error ? caught.message : 'Failed to create shipment.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Link
          to="/admin/jobs"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 transition"
        >
          <ArrowLeftIcon className="h-4 w-4" />
          Back to Shipments Directory
        </Link>
      </div>

      <PageHeader
        eyebrow="Customs Brokerage Logistics"
        title="Create New Shipment"
        description="Initialize an authorized operational job record with verified client and branch scopes."
      />

      {error && (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-xs font-semibold text-rose-800">
          {error}
        </div>
      )}

      {createdJob ? (
        <div className="space-y-6">
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50/80 p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-emerald-800">Shipment Created</p>
                <h3 className="text-lg font-black text-emerald-950 mt-1 font-mono">{createdJob.reference}</h3>
                <p className="text-xs text-emerald-700 mt-1">
                  Scope: {createdJob.client_name} · {createdJob.branch_name} ({createdJob.direction.toUpperCase()} / {createdJob.mode.toUpperCase()})
                </p>
              </div>
              <Link
                to={`/admin/jobs/${createdJob.id}`}
                className="rounded-xl bg-maritime-800 px-4 py-2 text-xs font-semibold text-white hover:bg-maritime-900 transition"
              >
                Open Shipment Record &rarr;
              </Link>
            </div>
          </div>

          {/* Prompt to immediately assign roles */}
          <AssignmentSuggestions job={createdJob} token={token!} />
        </div>
      ) : loading ? (
        <SkeletonMetricsGrid />
      ) : !references || references.clients.length === 0 || references.branches.length === 0 ? (
        <EmptyState
          title="Reference Data Unavailable"
          description="At least one authorized client organization and operations branch must be configured in reference data."
          action={
            <Link
              to="/admin/jobs"
              className="inline-flex items-center gap-2 rounded-xl bg-cyan-800 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-900 transition"
            >
              Return to Jobs Directory
            </Link>
          }
        />
      ) : (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs max-w-2xl">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="grid gap-5 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <FormField
                  label="Shipment Reference Number"
                  required
                  helperText="Primary customs identifier (e.g. MAWB, HAWB, Bill of Lading, or internal file #)."
                >
                  <TextInput
                    value={form.reference}
                    onChange={(e) => setForm({ ...form, reference: e.target.value })}
                    placeholder="e.g. NFPL-2026-AIR-0091"
                    className="font-mono"
                  />
                </FormField>
              </div>

              <FormField label="Client Organization" required>
                <SelectInput
                  value={form.client_id}
                  onChange={(e) => setForm({ ...form, client_id: e.target.value })}
                >
                  {references.clients.map((c) => (
                    <option key={c.id} value={c.id}>{c.name} ({c.code})</option>
                  ))}
                </SelectInput>
              </FormField>

              <FormField label="Operations Branch" required>
                <SelectInput
                  value={form.branch_id}
                  onChange={(e) => setForm({ ...form, branch_id: e.target.value })}
                >
                  {references.branches.map((b) => (
                    <option key={b.id} value={b.id}>{b.name} ({b.code})</option>
                  ))}
                </SelectInput>
              </FormField>

              <FormField label="Trade Direction" required>
                <SelectInput
                  value={form.direction}
                  onChange={(e) => setForm({ ...form, direction: e.target.value as 'import' | 'export' })}
                >
                  <option value="import">Import Clearance</option>
                  <option value="export">Export Filing</option>
                </SelectInput>
              </FormField>

              <FormField label="Transportation Mode" required>
                <SelectInput
                  value={form.mode}
                  onChange={(e) => setForm({ ...form, mode: e.target.value as 'air' | 'fcl' | 'lcl' })}
                >
                  <option value="air">Air Cargo</option>
                  <option value="fcl">Ocean Full Container (FCL)</option>
                  <option value="lcl">Ocean Less-than-Container (LCL)</option>
                </SelectInput>
              </FormField>

              <div className="sm:col-span-2">
                <FormField label="Goods Description">
                  <TextInput
                    value={form.goods_description}
                    onChange={(e) => setForm({ ...form, goods_description: e.target.value })}
                    placeholder="e.g. High-precision optical sensors and laboratory equipment"
                  />
                </FormField>
              </div>

              <div className="sm:col-span-2">
                <FormField label="Container / Equipment Reference" helperText="Container identifier, trailer, or flight number if available.">
                  <TextInput
                    value={form.container_reference}
                    onChange={(e) => setForm({ ...form, container_reference: e.target.value })}
                    placeholder="e.g. MSKU-9182374 / Flight QA-208"
                    className="font-mono"
                  />
                </FormField>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
              <Link
                to="/admin/jobs"
                className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition"
              >
                Cancel
              </Link>
              <button
                type="submit"
                disabled={submitting}
                className="inline-flex items-center gap-1.5 rounded-xl bg-maritime-800 px-5 py-2.5 text-xs font-semibold text-white shadow-xs hover:bg-maritime-900 disabled:opacity-50 transition"
              >
                <PlusIcon className="h-4 w-4 text-cyan-400" />
                {submitting ? 'Creating Shipment...' : 'Create Shipment Record'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
