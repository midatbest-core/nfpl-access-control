import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { ClientUpdate } from '../../api/contracts'
import { useAuth } from '../../auth/AuthContext'
import { EmptyState } from '../../components/design-system/EmptyState'
import { SkeletonCard } from '../../components/design-system/LoadingSkeleton'
import { PageHeader } from '../../components/shell/AppShell'
import { BoxIcon, ClockIcon } from '../../components/icons'

export function ClientUpdatesPage() {
  const { token } = useAuth()
  const [updates, setUpdates] = useState<ClientUpdate[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!token) return
    let active = true

    api.clientUpdates(token)
      .then((res) => {
        if (active) {
          setUpdates(res.items)
          setLoading(false)
        }
      })
      .catch(() => {
        if (active) {
          setUpdates([])
          setLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [token])

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Activity Feed"
        title="Recent Shipment Updates"
        description="Sanitized event timeline of milestone progress across your customs brokerage shipments."
      />

      {loading ? (
        <div className="space-y-3">
          <SkeletonCard lines={2} />
          <SkeletonCard lines={2} />
        </div>
      ) : updates.length === 0 ? (
        <EmptyState
          icon={<BoxIcon className="h-7 w-7 text-slate-400" />}
          title="No recent updates"
          description="There have been no recent milestone status changes recorded for your shipments."
        />
      ) : (
        <div className="relative border-l-2 border-slate-200 ml-4 space-y-6 py-2">
          {updates.map((update, idx) => (
            <div key={`${update.cursor}-${idx}`} className="relative pl-6">
              <span className="absolute -left-[9px] top-1 h-4 w-4 rounded-full border-2 border-white bg-cyan-600 shadow-2xs" />
              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold text-slate-900">
                    Shipment {update.reference}
                  </span>
                  <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
                    <ClockIcon className="h-3 w-3" />
                    <span>{new Date(update.occurred_at).toLocaleString()}</span>
                  </div>
                </div>

                <p className="text-sm text-slate-700 leading-relaxed">{update.message}</p>

                <div className="flex items-center gap-3 pt-2 text-xs">
                  <span className="rounded-md bg-slate-100 px-2 py-0.5 font-semibold text-slate-700 capitalize">
                    {update.stage}
                  </span>
                  <span className="text-slate-500 font-medium">
                    {update.progress_percent}% complete
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
