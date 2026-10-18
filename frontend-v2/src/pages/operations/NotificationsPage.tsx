import { useState } from 'react'
import { useNotifications } from '../../context/NotificationContext'
import { formatRelativeTime } from '../../context/notificationUtils'
import { EmptyState } from '../../components/design-system/EmptyState'
import { SkeletonCard } from '../../components/design-system/LoadingSkeleton'
import { PageHeader } from '../../components/shell/AppShell'
import {
  BellIcon,
  CheckCircleIcon,
  ClockIcon,
  RefreshIcon,
  Trash2Icon,
} from '../../components/icons'

export function NotificationsPage() {
  const {
    notifications,
    unreadCount,
    loading,
    refresh,
    markAllRead,
    clearAll,
    openNotificationTarget,
  } = useNotifications()

  const [unreadOnly, setUnreadOnly] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  const items = unreadOnly
    ? notifications.filter((n) => !n.read_at)
    : notifications

  async function handleManualRefresh() {
    setRefreshing(true)
    try {
      await refresh()
    } finally {
      setRefreshing(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Activity & Alerts"
        title="Notifications Center"
        description="Real-time alerts for shipment returns, assignments, delegation expiries, and administrative decisions."
        action={
          <div className="flex items-center gap-2">
            <span
              className="hidden sm:inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-1.5 rounded-xl"
              title="Notifications are automatically kept in sync"
            >
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              Live
            </span>

            <button
              type="button"
              onClick={() => void handleManualRefresh()}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 transition cursor-pointer"
              title="Refresh now"
            >
              <RefreshIcon className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">Sync</span>
            </button>

            <button
              type="button"
              onClick={() => setUnreadOnly(!unreadOnly)}
              className={`rounded-xl px-3 py-2 text-xs font-semibold transition border cursor-pointer ${
                unreadOnly
                  ? 'bg-sky-50 text-sky-800 border-sky-300 font-bold'
                  : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'
              }`}
            >
              {unreadOnly ? `Unread only (${unreadCount})` : 'Show unread only'}
            </button>

            {unreadCount > 0 && (
              <button
                type="button"
                onClick={() => void markAllRead()}
                className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 transition cursor-pointer"
              >
                Mark all as read
              </button>
            )}

            {notifications.length > 0 && (
              <button
                type="button"
                onClick={() => void clearAll()}
                className="inline-flex items-center gap-1.5 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-700 shadow-2xs hover:bg-rose-100 transition cursor-pointer"
                title="Clear all notifications"
              >
                <Trash2Icon className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Clear notifications</span>
                <span className="sm:hidden">Clear</span>
              </button>
            )}
          </div>
        }
      />

      {loading && notifications.length === 0 ? (
        <div className="space-y-3">
          <SkeletonCard lines={2} />
          <SkeletonCard lines={2} />
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={<BellIcon className="h-7 w-7 text-slate-400" />}
          title={unreadOnly ? 'No unread notifications' : 'No notifications'}
          description={
            unreadOnly
              ? 'You have caught up with all active alerts.'
              : 'You do not have any notifications in your inbox.'
          }
        />
      ) : (
        <div className="space-y-2.5">
          {items.map((item) => {
            const isRead = Boolean(item.read_at)
            return (
              <div
                key={item.id}
                role="button"
                tabIndex={0}
                onClick={() => void openNotificationTarget(item)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    void openNotificationTarget(item)
                  }
                }}
                className={`flex items-start gap-4 rounded-2xl border p-4 transition-all text-left cursor-pointer ${
                  isRead
                    ? 'border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50/50'
                    : 'border-sky-300 bg-sky-50/40 text-slate-900 shadow-xs hover:border-sky-400 hover:bg-sky-50/70 border-l-4 border-l-sky-600'
                }`}
              >
                <div
                  className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl ${
                    isRead ? 'bg-slate-100 text-slate-400' : 'bg-sky-100 text-sky-700'
                  }`}
                >
                  <BellIcon className="h-4.5 w-4.5" />
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-900">
                      {item.job_reference ? `Shipment ${item.job_reference}` : 'System Notice'}
                    </span>
                    <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider bg-slate-100 px-1.5 py-0.5 rounded">
                      {item.event_type.replace(/_/g, ' ')}
                    </span>
                    {!isRead && (
                      <span className="h-2 w-2 rounded-full bg-sky-500 animate-pulse" aria-label="Unread notification" />
                    )}
                  </div>
                  <p className="mt-1 text-sm text-slate-700 leading-snug">{item.message}</p>
                  <div className="mt-2 flex items-center gap-2 text-[11px] text-slate-400">
                    <ClockIcon className="h-3 w-3" />
                    <span>{formatRelativeTime(item.created_at)}</span>
                    <span>•</span>
                    <span>{new Date(item.created_at).toLocaleString()}</span>
                  </div>
                </div>

                {isRead && (
                  <CheckCircleIcon className="h-4 w-4 text-slate-300 shrink-0 mt-1" title="Read" />
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
