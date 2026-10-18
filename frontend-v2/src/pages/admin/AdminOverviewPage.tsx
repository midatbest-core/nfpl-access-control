import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import type { DashboardOverview } from '../../api/contracts'
import { useAuth } from '../../auth/AuthContext'
import { SkeletonMetricsGrid } from '../../components/design-system/LoadingSkeleton'
import { StatusBadge } from '../../components/design-system/StatusBadge'
import { PageHeader } from '../../components/shell/AppShell'
import {
  AlertTriangleIcon,
  ArrowRightIcon,
  BoxIcon,
  ClockIcon,
  HistoryIcon,
  PlusIcon,
  UsersIcon,
} from '../../components/icons'

export function AdminOverviewPage() {
  const { token, user } = useAuth()
  const [data, setData] = useState<DashboardOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) return
    let active = true

    api.adminOverview(token)
      .then((res) => {
        if (active) {
          setData(res)
          setLoading(false)
        }
      })
      .catch((err: Error) => {
        if (active) {
          setError(err.message)
          setLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [token])

  const firstName = user?.display_name?.split(' ')[0] ?? 'Admin'

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Operations Command Center"
        title={`Welcome back, ${firstName}`}
        description="Unified customs brokerage operations, workforce availability, and authorization compliance monitoring."
        action={
          <div className="flex items-center gap-3">
            <Link
              to="/admin/jobs"
              className="inline-flex items-center gap-1.5 rounded-xl bg-maritime-800 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-maritime-900 transition"
            >
              <PlusIcon className="h-4 w-4 text-cyan-400" />
              Manage Shipments
            </Link>
          </div>
        }
      />

      {/* Metrics Section: Live Backend Data or Loading Skeletons */}
      {loading ? (
        <SkeletonMetricsGrid />
      ) : error ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
          <p className="text-sm font-semibold text-slate-700">Overview Status</p>
          <p className="mt-1 text-xs text-slate-500">Live backend response: {error}</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Link
            to="/admin/jobs"
            className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs hover:border-cyan-300 hover:shadow-md transition group block"
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 group-hover:text-cyan-700">Total Shipments</span>
              <BoxIcon className="h-4 w-4 text-slate-400 group-hover:text-cyan-600" />
            </div>
            <p className="mt-2 text-2xl font-black text-slate-900">{data?.total_jobs ?? 0}</p>
            <p className="mt-1 text-xs text-slate-500">Across all branches & modes &rarr;</p>
          </Link>

          <Link
            to="/admin/employees"
            className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs hover:border-cyan-300 hover:shadow-md transition group block"
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 group-hover:text-cyan-700">Workforce Size</span>
              <UsersIcon className="h-4 w-4 text-slate-400 group-hover:text-cyan-600" />
            </div>
            <p className="mt-2 text-2xl font-black text-slate-900">{data?.total_employees ?? 0}</p>
            <p className="mt-1 text-xs text-slate-500">Authorized personnel &rarr;</p>
          </Link>

          <Link
            to="/admin/requests"
            className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs hover:border-amber-300 hover:shadow-md transition group block"
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 group-hover:text-amber-700">Urgent Requests</span>
              <AlertTriangleIcon className="h-4 w-4 text-amber-500" />
            </div>
            <p className="mt-2 text-2xl font-black text-amber-600">{data?.pending_requests ?? 0}</p>
            <p className="mt-1 text-xs text-slate-500">Awaiting admin decision &rarr;</p>
          </Link>

          <Link
            to="/admin/attention"
            className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs hover:border-cyan-300 hover:shadow-md transition group block"
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 group-hover:text-cyan-700">Needs Attention</span>
              <ClockIcon className="h-4 w-4 text-cyan-600" />
            </div>
            <p className="mt-2 text-2xl font-black text-cyan-700">{data?.reassignment_required_jobs ?? 0}</p>
            <p className="mt-1 text-xs text-slate-500">Reassignment or absence flags &rarr;</p>
          </Link>
        </div>
      )}

      {/* Stage Breakdown & Quick Command Cards */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Stage Distribution */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h2 className="text-base font-bold text-slate-900">Shipment Stages Pipeline</h2>
              <p className="text-xs text-slate-500">Operational workflow progression</p>
            </div>
            <Link
              to="/admin/jobs"
              className="inline-flex items-center gap-1 text-xs font-semibold text-cyan-700 hover:text-cyan-800"
            >
              View directory &rarr;
            </Link>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            {['confirmed', 'prepared', 'checked', 'filed', 'cancelled', 'reopened'].map((stage) => {
              const count = data?.jobs_by_stage?.[stage] ?? 0
              return (
                <div key={stage} className="rounded-xl border border-slate-100 bg-slate-50/70 p-3.5 space-y-1">
                  <StatusBadge status={stage} size="sm" />
                  <p className="text-lg font-bold text-slate-900 pt-1">{count}</p>
                </div>
              )
            })}
          </div>
        </div>

        {/* Command Navigation Shortcuts */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-3">
          <h2 className="text-base font-bold text-slate-900">Operations Control</h2>
          <p className="text-xs text-slate-500">Quick access to governed administrative tools</p>

          <div className="space-y-2 pt-2">
            <Link
              to="/admin/requests"
              className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-3 text-xs font-semibold text-slate-800 hover:border-cyan-300 hover:bg-cyan-50/30 transition group"
            >
              <span className="flex items-center gap-2">
                <AlertTriangleIcon className="h-4 w-4 text-amber-500" />
                Urgent & Exception Requests
              </span>
              <ArrowRightIcon className="h-3.5 w-3.5 text-slate-400 group-hover:text-cyan-600 transition" />
            </Link>

            <Link
              to="/admin/employees"
              className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-3 text-xs font-semibold text-slate-800 hover:border-cyan-300 hover:bg-cyan-50/30 transition group"
            >
              <span className="flex items-center gap-2">
                <UsersIcon className="h-4 w-4 text-blue-500" />
                Workforce & Scoped Grants
              </span>
              <ArrowRightIcon className="h-3.5 w-3.5 text-slate-400 group-hover:text-cyan-600 transition" />
            </Link>

            <Link
              to="/admin/attention"
              className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-3 text-xs font-semibold text-slate-800 hover:border-cyan-300 hover:bg-cyan-50/30 transition group"
            >
              <span className="flex items-center gap-2">
                <ClockIcon className="h-4 w-4 text-cyan-500" />
                Jobs Requiring Attention
              </span>
              <ArrowRightIcon className="h-3.5 w-3.5 text-slate-400 group-hover:text-cyan-600 transition" />
            </Link>

            <Link
              to="/admin/audit"
              className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-3 text-xs font-semibold text-slate-800 hover:border-cyan-300 hover:bg-cyan-50/30 transition group"
            >
              <span className="flex items-center gap-2">
                <HistoryIcon className="h-4 w-4 text-purple-500" />
                Audit Log & Compliance
              </span>
              <ArrowRightIcon className="h-3.5 w-3.5 text-slate-400 group-hover:text-cyan-600 transition" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
