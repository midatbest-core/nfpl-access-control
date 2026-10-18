import { useState } from 'react'
import { api } from '../../api/client'
import type { EmployeeProfile, ReferenceData, RoleAssignment } from '../../api/contracts'
import { ConfirmationDialog } from '../design-system/ConfirmationDialog'
import { FormField, SelectInput, TextInput } from '../design-system/FormElements'
import { useToast } from '../feedback/ToastContext'
import { ShieldIcon, XIcon } from '../icons'

const ROLES = [
  { value: 'maker', label: 'Maker' },
  { value: 'checker', label: 'Checker' },
  { value: 'filing-officer', label: 'Filing Officer' },
  { value: 'client-viewer', label: 'Client Viewer' },
  { value: 'parser-service', label: 'Parser Service' },
]

export function RoleManagerModal({
  employee,
  references,
  token,
  onClose,
  onChanged,
}: {
  employee: EmployeeProfile
  references: ReferenceData
  token: string
  onClose: () => void
  onChanged: () => void
}) {
  const toast = useToast()
  const [roleSlug, setRoleSlug] = useState('maker')
  const [clientId, setClientId] = useState('')
  const [branchId, setBranchId] = useState('')
  const [direction, setDirection] = useState<'import' | 'export' | ''>('')
  const [mode, setMode] = useState<'air' | 'fcl' | 'lcl' | ''>('')
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Revocation state
  const [revokeTarget, setRevokeTarget] = useState<RoleAssignment | null>(null)
  const [revokeReason, setRevokeReason] = useState('')
  const [confirmRevoke, setConfirmRevoke] = useState(false)
  const [revoking, setRevoking] = useState(false)
  const [now] = useState(() => Date.now())

  const activeGrants = employee.roles.filter((r) => {
    if (r.revoked_at) return false
    if (r.valid_until && Date.parse(r.valid_until) <= now) return false
    return true
  })

  async function handleGrant(e: React.FormEvent) {
    e.preventDefault()
    if (!reason.trim()) {
      setError('A grant justification reason is required.')
      return
    }

    const duplicate = employee.roles.some((assignment) => (
      assignment.role_slug === roleSlug &&
      assignment.client_id === (clientId || null) &&
      assignment.all_clients === !clientId &&
      assignment.branch_id === (branchId || null) &&
      assignment.all_branches === !branchId &&
      assignment.direction === (direction || null) &&
      assignment.all_directions === !direction &&
      assignment.mode === (mode || null) &&
      assignment.all_modes === !mode &&
      !assignment.revoked_at &&
      (!assignment.valid_until || Date.parse(assignment.valid_until) > Date.now())
    ))

    if (duplicate) {
      setError('This employee already has an identical active role and scope.')
      return
    }

    setSubmitting(true)
    setError(null)

    try {
      await api.grantRole(token, {
        target_user_id: employee.id,
        role_slug: roleSlug,
        reason: reason.trim(),
        scope: {
          all_clients: !clientId,
          client_id: clientId || null,
          all_branches: !branchId,
          branch_id: branchId || null,
          all_directions: !direction,
          direction: direction || null,
          all_modes: !mode,
          mode: mode || null,
        },
      })
      toast.success('Scoped role grant added successfully.')
      setReason('')
      onChanged()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Role grant failed.')
      toast.error(caught instanceof Error ? caught.message : 'Role grant failed.')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleRevoke() {
    if (!revokeTarget || !revokeReason.trim()) {
      toast.error('A revocation reason is required.')
      return
    }
    setRevoking(true)
    try {
      await api.revokeRole(token, revokeTarget.id, revokeReason.trim())
      toast.success('Role assignment revoked.')
      setConfirmRevoke(false)
      setRevokeTarget(null)
      setRevokeReason('')
      onChanged()
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Revocation failed.')
    } finally {
      setRevoking(false)
    }
  }

  function formatScope(assignment: RoleAssignment): string {
    const clientName = assignment.all_clients
      ? 'All Clients'
      : references.clients.find((c) => c.id === assignment.client_id)?.name ?? assignment.client_id
    const branchName = assignment.all_branches
      ? 'All Branches'
      : references.branches.find((b) => b.id === assignment.branch_id)?.name ?? assignment.branch_id
    const dir = assignment.all_directions ? 'All Directions' : assignment.direction?.toUpperCase()
    const m = assignment.all_modes ? 'All Modes' : assignment.mode?.toUpperCase()
    return `${clientName} · ${branchName} · ${dir} · ${m}`
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs" onClick={onClose} />

      {/* Modal Dialog */}
      <div className="relative z-10 flex max-h-[90vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-2xl border border-slate-200">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-maritime-50 text-maritime-700">
              <ShieldIcon className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">Manage Scoped Roles</h2>
              <p className="text-xs text-slate-500">{employee.display_name} ({employee.email})</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition"
            aria-label="Close dialog"
          >
            <XIcon className="h-5 w-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {error && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs font-semibold text-rose-800">
              {error}
            </div>
          )}

          {/* Active Grants List */}
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
              Active Scoped Role Grants ({activeGrants.length})
            </h3>
            {activeGrants.length === 0 ? (
              <p className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-500 text-center">
                No active roles assigned. Employee cannot perform operational actions until granted.
              </p>
            ) : (
              <div className="space-y-2.5">
                {activeGrants.map((grant) => (
                  <div
                    key={grant.id}
                    className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-3.5 shadow-xs"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="rounded-md bg-maritime-100 px-2.5 py-0.5 text-xs font-bold text-maritime-800 uppercase">
                          {grant.role_slug.replace('-', ' ')}
                        </span>
                        <span className="text-[11px] text-slate-400 font-mono">
                          ID: {grant.id.slice(0, 8)}...
                        </span>
                      </div>
                      <p className="mt-1.5 text-xs font-medium text-slate-700">
                        {formatScope(grant)}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setRevokeTarget(grant)
                        setRevokeReason('')
                        setConfirmRevoke(true)
                      }}
                      className="self-start sm:self-center rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-100 transition"
                    >
                      Revoke Grant
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Grant New Role Form */}
          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-5 space-y-4">
            <h3 className="text-sm font-bold text-slate-900">Grant New Scoped Role</h3>
            <form onSubmit={handleGrant} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <FormField label="Role Type" required>
                  <SelectInput
                    value={roleSlug}
                    onChange={(e) => setRoleSlug(e.target.value)}
                  >
                    {ROLES.map((r) => (
                      <option key={r.value} value={r.value}>{r.label}</option>
                    ))}
                  </SelectInput>
                </FormField>

                <FormField label="Client Scope">
                  <SelectInput
                    value={clientId}
                    onChange={(e) => setClientId(e.target.value)}
                  >
                    <option value="">All Clients (Wildcard)</option>
                    {references.clients.map((c) => (
                      <option key={c.id} value={c.id}>{c.name} ({c.code})</option>
                    ))}
                  </SelectInput>
                </FormField>

                <FormField label="Branch Scope">
                  <SelectInput
                    value={branchId}
                    onChange={(e) => setBranchId(e.target.value)}
                  >
                    <option value="">All Branches (Wildcard)</option>
                    {references.branches.map((b) => (
                      <option key={b.id} value={b.id}>{b.name} ({b.code})</option>
                    ))}
                  </SelectInput>
                </FormField>

                <FormField label="Direction Scope">
                  <SelectInput
                    value={direction}
                    onChange={(e) => setDirection(e.target.value as 'import' | 'export' | '')}
                  >
                    <option value="">All Directions</option>
                    <option value="import">Import Only</option>
                    <option value="export">Export Only</option>
                  </SelectInput>
                </FormField>

                <FormField label="Mode Scope">
                  <SelectInput
                    value={mode}
                    onChange={(e) => setMode(e.target.value as 'air' | 'fcl' | 'lcl' | '')}
                  >
                    <option value="">All Modes</option>
                    <option value="air">Air Freight</option>
                    <option value="fcl">Ocean FCL</option>
                    <option value="lcl">Ocean LCL</option>
                  </SelectInput>
                </FormField>

                <div className="sm:col-span-2">
                  <FormField label="Grant Justification Reason" required helperText="Audited justification recorded in the immutable compliance log.">
                    <TextInput
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      placeholder="e.g. Operational requirement for North Region customs clearance"
                    />
                  </FormField>
                </div>
              </div>

              <div className="flex justify-end pt-2">
                <button
                  type="submit"
                  disabled={submitting}
                  className="rounded-xl bg-maritime-800 px-5 py-2.5 text-xs font-semibold text-white shadow-xs hover:bg-maritime-900 disabled:opacity-50 transition"
                >
                  {submitting ? 'Granting Role...' : 'Authorize Role Grant'}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>

      {/* Revocation Confirmation Dialog */}
      <ConfirmationDialog
        open={confirmRevoke}
        title="Revoke Role Assignment?"
        message={
          <div className="space-y-3">
            <p>
              Are you sure you want to revoke <strong>{revokeTarget?.role_slug}</strong> from{' '}
              <strong>{employee.display_name}</strong>?
            </p>
            <FormField label="Revocation Reason" required>
              <TextInput
                value={revokeReason}
                onChange={(e) => setRevokeReason(e.target.value)}
                placeholder="Reason for role revocation..."
              />
            </FormField>
          </div>
        }
        confirmLabel={revoking ? 'Revoking...' : 'Confirm Revocation'}
        danger
        onConfirm={() => void handleRevoke()}
        onCancel={() => setConfirmRevoke(false)}
      />
    </div>
  )
}
