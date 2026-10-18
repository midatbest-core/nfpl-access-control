import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { EmployeeProfile, ReferenceData } from '../../api/contracts'
import { useAuth } from '../../auth/AuthContext'
import { RoleManagerModal } from '../../components/admin/RoleManagerModal'
import { ConfirmationDialog } from '../../components/design-system/ConfirmationDialog'
import { FormField, TextInput } from '../../components/design-system/FormElements'
import type { Column } from '../../components/design-system/SearchTable'
import { SearchTable } from '../../components/design-system/SearchTable'
import { StatusBadge } from '../../components/design-system/StatusBadge'
import { useToast } from '../../components/feedback/ToastContext'
import { ShieldIcon } from '../../components/icons'
import { PageHeader } from '../../components/shell/AppShell'

export function AdminEmployeesPage() {
  const { token } = useAuth()
  const toast = useToast()
  const [employees, setEmployees] = useState<EmployeeProfile[]>([])
  const [references, setReferences] = useState<ReferenceData | null>(null)
  const [totalCount, setTotalCount] = useState<number | undefined>(undefined)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)

  // Account transition modal
  const [actionTarget, setActionTarget] = useState<{
    employee: EmployeeProfile
    action: 'approve' | 'reject' | 'activate' | 'deactivate'
  } | null>(null)
  const [actionReason, setActionReason] = useState('')
  const [processingAction, setProcessingAction] = useState(false)

  // Scoped Role modal
  const [roleModalEmployee, setRoleModalEmployee] = useState<EmployeeProfile | null>(null)

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(search)
      setPage(1)
      setLoading(true)
    }, 250)
    return () => clearTimeout(handler)
  }, [search])

  const isSearching = loading || search !== debouncedSearch

  useEffect(() => {
    if (!token) return
    let active = true

    Promise.all([
      api.employees(token, page, debouncedSearch),
      references ? Promise.resolve(references) : api.referenceData(token),
    ])
      .then(([empRes, refRes]) => {
        if (active) {
          setEmployees(empRes.items)
          setTotalCount(empRes.total)
          if (!references) setReferences(refRes)
          setLoading(false)
        }
      })
      .catch(() => {
        if (active) {
          setEmployees([])
          setLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [token, page, debouncedSearch, references])

  async function reloadEmployees() {
    if (!token) return
    setLoading(true)
    try {
      const empRes = await api.employees(token, page, search)
      setEmployees(empRes.items)
      setTotalCount(empRes.total)
    } catch {
      setEmployees([])
    } finally {
      setLoading(false)
    }
  }

  async function handleAccountTransition() {
    if (!token || !actionTarget || !actionReason.trim()) {
      toast.error('An audited reason is required for account transitions.')
      return
    }
    setProcessingAction(true)
    try {
      await api.employeeAction(token, actionTarget.employee.id, actionTarget.action, actionReason.trim())
      toast.success(
        `Account ${actionTarget.action}d for ${actionTarget.employee.display_name}.`
      )
      setActionTarget(null)
      setActionReason('')
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Account transition failed.')
      setActionTarget(null)
      setActionReason('')
      await reloadEmployees()
    } finally {
      setProcessingAction(false)
    }
  }

  const columns: Column<EmployeeProfile>[] = [
    {
      key: 'name',
      header: 'Employee',
      render: (emp) => (
        <div>
          <span className="text-xs font-bold text-slate-900">{emp.display_name}</span>
          <p className="font-mono text-[11px] text-slate-500">{emp.email}</p>
        </div>
      ),
    },
    {
      key: 'branch',
      header: 'Branch',
      render: (emp) => (
        <span className="text-xs text-slate-600">{emp.branch_name || emp.branch_id || 'All Branches'}</span>
      ),
    },
    {
      key: 'status',
      header: 'Account Status',
      render: (emp) => <StatusBadge status={emp.account_status} size="sm" />,
    },
    {
      key: 'availability',
      header: 'Availability',
      render: (emp) => <StatusBadge status={emp.availability} size="sm" />,
    },
    {
      key: 'workload',
      header: 'Active Jobs',
      render: (emp) => (
        <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700">
          {emp.pending_workload}
        </span>
      ),
    },
    {
      key: 'roles',
      header: 'Assigned Roles',
      render: (emp) => (
        <div className="flex flex-wrap gap-1 max-w-xs">
          {emp.roles.filter(r => !r.revoked_at).length === 0 ? (
            <span className="text-[11px] text-slate-400 italic">None</span>
          ) : (
            emp.roles.filter(r => !r.revoked_at).map((r) => (
              <span
                key={r.id}
                className="rounded-md bg-maritime-50 px-1.5 py-0.5 text-[10px] font-bold text-maritime-800 border border-maritime-200 uppercase"
              >
                {r.role_slug.replace('-', ' ')}
              </span>
            ))
          )}
        </div>
      ),
    },
    {
      key: 'actions',
      header: 'Governance Actions',
      render: (emp) => (
        <div className="flex flex-wrap items-center gap-1.5">
          {/* Account Status Transitions */}
          {emp.account_status === 'pending' && (
            <>
              <button
                type="button"
                onClick={() => {
                  setActionTarget({ employee: emp, action: 'approve' })
                  setActionReason('')
                }}
                className="rounded-lg bg-emerald-50 px-2 py-1 text-[11px] font-bold text-emerald-700 hover:bg-emerald-100 transition"
              >
                Approve
              </button>
              <button
                type="button"
                onClick={() => {
                  setActionTarget({ employee: emp, action: 'reject' })
                  setActionReason('')
                }}
                className="rounded-lg bg-rose-50 px-2 py-1 text-[11px] font-bold text-rose-700 hover:bg-rose-100 transition"
              >
                Reject
              </button>
            </>
          )}

          {emp.account_status === 'active' && (
            <button
              type="button"
              onClick={() => {
                setActionTarget({ employee: emp, action: 'deactivate' })
                setActionReason('')
              }}
              className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-600 hover:bg-rose-50 hover:text-rose-700 hover:border-rose-200 transition"
            >
              Deactivate
            </button>
          )}

          {emp.account_status === 'disabled' && (
            <button
              type="button"
              onClick={() => {
                setActionTarget({ employee: emp, action: 'activate' })
                setActionReason('')
              }}
              className="rounded-lg bg-emerald-50 px-2 py-1 text-[11px] font-bold text-emerald-700 hover:bg-emerald-100 transition"
            >
              Activate
            </button>
          )}

          {/* Manage Scoped Roles Button */}
          <button
            type="button"
            onClick={() => setRoleModalEmployee(emp)}
            className="inline-flex items-center gap-1 rounded-lg bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-700 hover:bg-slate-200 transition"
          >
            <ShieldIcon className="h-3 w-3 text-slate-500" />
            Roles
          </button>
        </div>
      ),
    },
  ]

  const pageSize = 25
  const hasNextPage = totalCount !== undefined ? page * pageSize < totalCount : false
  const hasPrevPage = page > 1

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Workforce & Governance"
        title="Employee Directory & Scoped Access"
        description="Inspect staff profiles, account status approvals, availability, and active role assignments."
      />

      <SearchTable
        data={employees}
        columns={columns}
        keyExtractor={(emp) => emp.id}
        searchQuery={search}
        onSearchChange={(q) => {
          setSearch(q)
          setPage(1)
        }}
        searchPlaceholder="Search employees by name or email..."
        totalCount={totalCount}
        page={page}
        isLoading={isSearching}
        hasNextPage={hasNextPage}
        hasPrevPage={hasPrevPage}
        onNextPage={() => {
          setPage((p) => p + 1)
          setLoading(true)
        }}
        onPrevPage={() => {
          setPage((p) => Math.max(1, p - 1))
          setLoading(true)
        }}
        emptyTitle="No employees found"
        emptyDescription={search ? `No staff matching "${search}".` : 'No employee records returned by directory service.'}
      />

      {/* Account Action Confirmation Dialog */}
      <ConfirmationDialog
        open={actionTarget !== null}
        title={`${actionTarget?.action.toUpperCase()} Account?`}
        message={
          <div className="space-y-3">
            <p>
              Are you sure you want to <strong>{actionTarget?.action}</strong> the account for{' '}
              <strong>{actionTarget?.employee.display_name}</strong>?
            </p>
            <FormField label="Audited Action Reason" required>
              <TextInput
                value={actionReason}
                onChange={(e) => setActionReason(e.target.value)}
                placeholder={`Reason for ${actionTarget?.action}...`}
              />
            </FormField>
          </div>
        }
        confirmLabel={processingAction ? 'Processing...' : `Confirm ${actionTarget?.action}`}
        danger={actionTarget?.action === 'deactivate' || actionTarget?.action === 'reject'}
        onConfirm={() => void handleAccountTransition()}
        onCancel={() => setActionTarget(null)}
      />

      {/* Scoped Role Manager Modal */}
      {roleModalEmployee && references && (
        <RoleManagerModal
          employee={roleModalEmployee}
          references={references}
          token={token!}
          onClose={() => setRoleModalEmployee(null)}
          onChanged={() => {
            setRoleModalEmployee(null)
            void reloadEmployees()
          }}
        />
      )}
    </div>
  )
}
