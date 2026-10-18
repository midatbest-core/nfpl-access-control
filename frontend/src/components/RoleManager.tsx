import { useState } from 'react'

import { api } from '../api/client'
import type { EmployeeProfile, ReferenceData, RoleAssignment } from '../api/contracts'
import { ConfirmationDialog } from './Controls'
import { ErrorMessage } from './Feedback'

const roles = ['maker', 'checker', 'filing-officer', 'client-viewer', 'parser-service']

function scopeSummary(assignment: RoleAssignment, references: ReferenceData): string {
  const client = assignment.all_clients
    ? 'all clients'
    : references.clients.find((item) => item.id === assignment.client_id)?.name ?? 'selected client'
  const branch = assignment.all_branches
    ? 'all branches'
    : references.branches.find((item) => item.id === assignment.branch_id)?.name ?? 'selected branch'
  const direction = assignment.all_directions ? 'all directions' : assignment.direction
  const mode = assignment.all_modes ? 'all modes' : assignment.mode?.toUpperCase()
  return [client, branch, direction, mode].join(' / ')
}

export function RoleManager({
  employee,
  references,
  token,
  onChanged,
}: {
  employee: EmployeeProfile
  references: ReferenceData
  token: string
  onChanged: () => void
}) {
  const [role, setRole] = useState('maker')
  const [clientId, setClientId] = useState('')
  const [branchId, setBranchId] = useState('')
  const [direction, setDirection] = useState<'import' | 'export' | ''>('')
  const [mode, setMode] = useState<'air' | 'fcl' | 'lcl' | ''>('')
  const [reason, setReason] = useState('')
  const [revokeReason, setRevokeReason] = useState('')
  const [revokeTarget, setRevokeTarget] = useState<RoleAssignment>()
  const [confirmRevoke, setConfirmRevoke] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  async function grant() {
    if (!reason.trim()) {
      setError('A reason is required.')
      return
    }
    const now = Date.now()
    const duplicate = employee.roles.some((assignment) => (
      assignment.role_slug === role
      && assignment.client_id === (clientId || null)
      && assignment.all_clients === !clientId
      && assignment.branch_id === (branchId || null)
      && assignment.all_branches === !branchId
      && assignment.direction === (direction || null)
      && assignment.all_directions === !direction
      && assignment.mode === (mode || null)
      && assignment.all_modes === !mode
      && !assignment.revoked_at
      && (!assignment.valid_until || Date.parse(assignment.valid_until) > now)
    ))
    if (duplicate) {
      setError(
        'This employee already has the same active role and scope. Choose a different scope, or revoke the existing assignment first.',
      )
      return
    }
    setSubmitting(true)
    try {
      await api.grantRole(token, {
        target_user_id: employee.id,
        role_slug: role,
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
      setReason('')
      setError('')
      setMessage('Scoped role granted.')
      onChanged()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Role grant failed.')
    } finally {
      setSubmitting(false)
    }
  }

  async function revoke() {
    if (!revokeTarget || !revokeReason.trim()) {
      setError('A revocation reason is required.')
      return
    }
    try {
      await api.revokeRole(token, revokeTarget.id, revokeReason.trim())
      setError('')
      setMessage('Role assignment revoked.')
      setRevokeTarget(undefined)
      setRevokeReason('')
      setConfirmRevoke(false)
      onChanged()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Role revocation failed.')
    }
  }

  return (
    <section className="mt-4 border-t border-slate-200 pt-4">
      {error && <ErrorMessage message={error} />}
      {message && <p className="mb-2 text-sm text-teal-700" role="status">{message}</p>}
      <p className="mb-2 text-sm font-semibold">Scoped role assignments</p>
      <div className="grid gap-2 sm:grid-cols-2">
        <select className="field" aria-label="Role" value={role} onChange={(event) => setRole(event.target.value)}>
          {roles.map((item) => <option key={item}>{item}</option>)}
        </select>
        <input className="field" aria-label="Role grant reason" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Required grant reason" />
        <select className="field" aria-label="Client scope" value={clientId} onChange={(event) => setClientId(event.target.value)}>
          <option value="">All clients</option>
          {references.clients.map((item) => <option value={item.id} key={item.id}>{item.name} ({item.code})</option>)}
        </select>
        <select className="field" aria-label="Branch scope" value={branchId} onChange={(event) => setBranchId(event.target.value)}>
          <option value="">All branches</option>
          {references.branches.map((item) => <option value={item.id} key={item.id}>{item.name} ({item.code})</option>)}
        </select>
        <select className="field" aria-label="Direction scope" value={direction} onChange={(event) => setDirection(event.target.value as 'import' | 'export' | '')}>
          <option value="">All directions</option><option value="import">Import</option><option value="export">Export</option>
        </select>
        <select className="field" aria-label="Mode scope" value={mode} onChange={(event) => setMode(event.target.value as 'air' | 'fcl' | 'lcl' | '')}>
          <option value="">All modes</option><option value="air">Air</option><option value="fcl">FCL</option><option value="lcl">LCL</option>
        </select>
      </div>
      <button className="button-primary mt-3" type="button" disabled={submitting} onClick={() => void grant()}>{submitting ? 'Granting role...' : 'Grant scoped role'}</button>
      <div className="mt-3 space-y-2">
        {employee.roles.length === 0 && <p className="text-xs text-slate-500">No role assignments.</p>}
        {employee.roles.map((item) => (
          <div className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 p-2 text-xs" key={item.id}>
            <span><strong>{item.role_slug}</strong> - {scopeSummary(item, references)}{item.revoked_at ? ' (revoked)' : ''}</span>
            {!item.revoked_at && <button className="text-red-700" type="button" onClick={() => { setRevokeTarget(item); setRevokeReason('') }}>Revoke</button>}
          </div>
        ))}
      </div>
      {revokeTarget && (
        <div className="mt-3 rounded-lg border border-red-200 p-3">
          <label className="form-label">Revocation reason
            <input className="field mt-1" value={revokeReason} onChange={(event) => setRevokeReason(event.target.value)} />
          </label>
          <button className="button-danger mt-2" type="button" disabled={!revokeReason.trim()} onClick={() => setConfirmRevoke(true)}>Review revocation</button>
          <button className="button-secondary ml-2 mt-2" type="button" onClick={() => { setRevokeTarget(undefined); setConfirmRevoke(false) }}>Cancel</button>
        </div>
      )}
      <ConfirmationDialog
        open={confirmRevoke}
        title="Revoke this scoped role?"
        message="The employee will immediately lose permissions derived from this assignment. Historical activity remains intact."
        confirmLabel="Revoke role"
        dangerous
        onConfirm={() => void revoke()}
        onCancel={() => setConfirmRevoke(false)}
      />
    </section>
  )
}
