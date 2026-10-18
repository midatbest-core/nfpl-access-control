import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import { effectiveRoles, ROLE } from '../../auth/roles'
import { useNotifications } from '../../context/NotificationContext'
import { formatRelativeTime } from '../../context/notificationUtils'
import { Breadcrumbs } from '../design-system/Breadcrumbs'
import { useToast } from '../feedback/ToastContext'
import {
  ArrowRightIcon,
  BellIcon,
  BuildingIcon,
  CheckCircleIcon,
  ChevronDownIcon,
  MenuIcon,
  RefreshIcon,
  ShieldCheckIcon,
  Trash2Icon,
} from '../icons'

interface TopNavProps {
  unreadCount?: number
  onOpenMobile: () => void
  onSignOut: () => void
}

export function TopNav({ unreadCount = 0, onOpenMobile }: TopNavProps) {
  const { user, token, refreshProfile } = useAuth()
  const toast = useToast()
  const notificationsCtx = useNotifications()

  const [updatingAvailability, setUpdatingAvailability] = useState(false)
  const [showStatusMenu, setShowStatusMenu] = useState(false)
  const [popoverOpen, setPopoverOpen] = useState(false)
  const [filterTab, setFilterTab] = useState<'all' | 'unread'>('all')

  const popoverRef = useRef<HTMLDivElement>(null)
  const bellBtnRef = useRef<HTMLButtonElement>(null)

  const effectiveUnreadCount =
    unreadCount > 0 ? unreadCount : notificationsCtx.unreadCount
  const {
    notifications,
    markAsRead,
    markAllRead,
    openNotificationTarget,
    refresh,
  } = notificationsCtx

  const displayedItems =
    filterTab === 'unread'
      ? notifications.filter((n) => !n.read_at)
      : notifications

  const roles = effectiveRoles(user)
  const roleLabel = roles.has(ROLE.admin)
    ? 'Admin'
    : roles.has(ROLE.clientViewer)
      ? 'Client'
      : [ROLE.maker, ROLE.checker, ROLE.filingOfficer].some((r) => roles.has(r))
        ? 'Operations'
        : 'Staff'

  // Close notifications popover on click outside or Escape
  useEffect(() => {
    if (!popoverOpen) return

    function handleClickOutside(e: MouseEvent) {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(e.target as Node) &&
        bellBtnRef.current &&
        !bellBtnRef.current.contains(e.target as Node)
      ) {
        setPopoverOpen(false)
      }
    }

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setPopoverOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [popoverOpen])

  async function handleAvailabilityChange(next: 'available' | 'busy' | 'absent') {
    if (!token || updatingAvailability) return
    setUpdatingAvailability(true)
    setShowStatusMenu(false)
    try {
      await api.updateAvailability(token, next)
      await refreshProfile()
      toast.success(`Availability status updated to ${next}`, 'Status Updated')
    } catch {
      toast.error('Could not update availability status. Please try again.', 'Update Failed')
    } finally {
      setUpdatingAvailability(false)
    }
  }

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-slate-200/80 bg-white/95 px-4 backdrop-blur-md sm:px-6 lg:px-8">
      {/* Left: Mobile Toggle + Breadcrumbs */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          type="button"
          onClick={onOpenMobile}
          className="grid h-9 w-9 place-items-center rounded-xl text-slate-600 hover:bg-slate-100 lg:hidden"
          aria-label="Open mobile navigation"
        >
          <MenuIcon className="h-5 w-5" />
        </button>
        <div className="hidden sm:block min-w-0">
          <Breadcrumbs />
        </div>
      </div>

      {/* Right Controls: Branch, Role Pill, Status Toggle, Notifications */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Branch / Scope Pill */}
        {user?.branch_id && (
          <div className="hidden sm:flex items-center gap-1.5 rounded-xl bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-700">
            <BuildingIcon className="h-3.5 w-3.5 text-slate-500" />
            <span className="truncate max-w-[140px]">{user.branch_id}</span>
          </div>
        )}

        {/* Role Pill */}
        <div className="inline-flex items-center gap-1.5 rounded-xl bg-maritime-50 px-3 py-1.5 text-xs font-bold text-maritime-900 border border-maritime-200/60 shadow-2xs">
          <ShieldCheckIcon className="h-3.5 w-3.5 text-maritime-700" />
          <span>{roleLabel}</span>
        </div>

        {/* Availability Toggle Menu (Staff only) */}
        {user?.kind === 'staff' && (
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowStatusMenu(!showStatusMenu)}
              disabled={updatingAvailability}
              className={`flex items-center gap-2 rounded-xl px-2.5 py-1.5 text-xs font-semibold border transition ${
                user.availability === 'available'
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-800 hover:bg-emerald-100'
                  : user.availability === 'busy'
                    ? 'border-sky-200 bg-sky-50 text-sky-800 hover:bg-sky-100'
                    : 'border-slate-200 bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
              aria-label="Toggle availability status"
              aria-expanded={showStatusMenu}
              aria-haspopup="true"
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  user.availability === 'available'
                    ? 'bg-emerald-500'
                    : user.availability === 'busy'
                      ? 'bg-sky-500'
                      : 'bg-slate-400'
                }`}
              />
              <span className="capitalize">{user.availability}</span>
              <ChevronDownIcon className="h-3.5 w-3.5 text-slate-400" />
            </button>

            {showStatusMenu && (
              <div
                className="absolute right-0 mt-2 w-40 rounded-xl border border-slate-200 bg-white p-1 shadow-lg ring-1 ring-black/5 z-30 animate-in fade-in zoom-in-95 duration-100"
                role="menu"
              >
                <button
                  type="button"
                  onClick={() => handleAvailabilityChange('available')}
                  className={`flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 ${
                    user.availability === 'available' ? 'bg-emerald-50 text-emerald-800 font-bold' : ''
                  }`}
                  role="menuitem"
                >
                  <span className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-emerald-500" />
                    Available
                  </span>
                  {user.availability === 'available' && <CheckCircleIcon className="h-3.5 w-3.5 text-emerald-600" />}
                </button>
                <button
                  type="button"
                  onClick={() => handleAvailabilityChange('busy')}
                  className={`flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 ${
                    user.availability === 'busy' ? 'bg-sky-50 text-sky-800 font-bold' : ''
                  }`}
                  role="menuitem"
                >
                  <span className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-sky-500" />
                    Busy
                  </span>
                  {user.availability === 'busy' && <CheckCircleIcon className="h-3.5 w-3.5 text-sky-600" />}
                </button>
                <button
                  type="button"
                  onClick={() => handleAvailabilityChange('absent')}
                  className={`flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 ${
                    user.availability === 'absent' ? 'bg-slate-100 text-slate-800 font-bold' : ''
                  }`}
                  role="menuitem"
                >
                  <span className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-slate-400" />
                    Absent
                  </span>
                  {user.availability === 'absent' && <CheckCircleIcon className="h-3.5 w-3.5 text-slate-600" />}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Notifications Pop-up Dropdown Trigger */}
        <div className="relative">
          <button
            ref={bellBtnRef}
            type="button"
            onClick={() => setPopoverOpen((prev) => !prev)}
            className={`relative grid h-9 w-9 place-items-center rounded-xl transition cursor-pointer ${
              popoverOpen
                ? 'bg-slate-200 text-slate-900 shadow-inner'
                : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'
            }`}
            aria-label="View notifications"
            aria-expanded={popoverOpen}
            aria-haspopup="true"
            title="Notifications"
          >
            <BellIcon className="h-4.5 w-4.5" />
            {effectiveUnreadCount > 0 && (
              <span className="absolute -top-1 -right-1 flex h-4.5 min-w-4.5 items-center justify-center">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75" />
                <span
                  className="relative inline-flex items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white shadow-xs"
                  aria-label={`${effectiveUnreadCount} unread notifications`}
                >
                  {effectiveUnreadCount > 99 ? '99+' : effectiveUnreadCount}
                </span>
              </span>
            )}
          </button>

          {/* Floating Pop-up Notifications Card */}
          {popoverOpen && (
            <div
              ref={popoverRef}
              className="absolute right-0 top-11 z-50 w-96 max-w-[calc(100vw-2rem)] rounded-2xl border border-slate-200 bg-white shadow-2xl ring-1 ring-black/5 animate-in fade-in slide-in-from-top-2 duration-150 overflow-hidden"
              role="dialog"
              aria-label="Notifications pop-up"
            >
              {/* Header */}
              <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50/80 px-4 py-3">
                <div className="flex items-center gap-2">
                  <span
                    className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse"
                    title="Live dynamic updates"
                  />
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                    Notifications
                  </h3>
                  {effectiveUnreadCount > 0 && (
                    <span className="rounded-full bg-rose-50 px-2 py-0.5 text-[10px] font-bold text-rose-700 border border-rose-200">
                      {effectiveUnreadCount} unread
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => void refresh()}
                    className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition cursor-pointer"
                    title="Refresh notifications"
                    aria-label="Refresh notifications"
                  >
                    <RefreshIcon className="h-3.5 w-3.5" />
                  </button>
                  {notifications.length > 0 && (
                    <button
                      type="button"
                      onClick={() => void notificationsCtx.clearAll()}
                      className="inline-flex items-center gap-1 text-[11px] font-semibold text-rose-600 hover:text-rose-800 px-2 py-1 rounded-lg hover:bg-rose-50 transition cursor-pointer"
                      title="Clear all notifications from this panel"
                    >
                      <Trash2Icon className="h-3 w-3" />
                      <span>Clear all</span>
                    </button>
                  )}
                  {effectiveUnreadCount > 0 && (
                    <button
                      type="button"
                      onClick={() => void markAllRead()}
                      className="text-[11px] font-semibold text-sky-700 hover:text-sky-900 px-2 py-1 rounded-lg hover:bg-sky-50 transition cursor-pointer"
                    >
                      Mark all read
                    </button>
                  )}
                </div>
              </div>

              {/* Filter Tabs */}
              <div className="flex border-b border-slate-100 bg-white px-3 pt-2">
                <button
                  type="button"
                  onClick={() => setFilterTab('all')}
                  className={`pb-2 px-2 text-xs font-semibold border-b-2 transition cursor-pointer ${
                    filterTab === 'all'
                      ? 'border-maritime-700 text-maritime-900'
                      : 'border-transparent text-slate-500 hover:text-slate-800'
                  }`}
                >
                  All ({notifications.length})
                </button>
                <button
                  type="button"
                  onClick={() => setFilterTab('unread')}
                  className={`pb-2 px-2 text-xs font-semibold border-b-2 transition cursor-pointer ${
                    filterTab === 'unread'
                      ? 'border-maritime-700 text-maritime-900'
                      : 'border-transparent text-slate-500 hover:text-slate-800'
                  }`}
                >
                  Unread ({effectiveUnreadCount})
                </button>
              </div>

              {/* Notification Items List */}
              <div className="max-h-80 overflow-y-auto divide-y divide-slate-100">
                {displayedItems.length === 0 ? (
                  <div className="py-8 px-4 text-center">
                    <div className="mx-auto mb-2 grid h-10 w-10 place-items-center rounded-full bg-slate-100 text-slate-400">
                      <BellIcon className="h-5 w-5" />
                    </div>
                    <p className="text-xs font-bold text-slate-700">
                      {filterTab === 'unread' ? 'No unread notifications' : 'No notifications'}
                    </p>
                    <p className="mt-0.5 text-[11px] text-slate-400">
                      {filterTab === 'unread'
                        ? "You're all caught up with active tasks."
                        : 'Activity and assignment alerts will appear here.'}
                    </p>
                  </div>
                ) : (
                  displayedItems.slice(0, 10).map((item) => {
                    const isUnread = !item.read_at
                    return (
                      <div
                        key={item.id}
                        className={`group relative flex items-start gap-3 p-3.5 transition cursor-pointer ${
                          isUnread
                            ? 'bg-sky-50/40 hover:bg-sky-50/70 border-l-3 border-l-sky-500'
                            : 'hover:bg-slate-50 border-l-3 border-l-transparent'
                        }`}
                        onClick={() => {
                          setPopoverOpen(false)
                          void openNotificationTarget(item)
                        }}
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center justify-between gap-1">
                            <div className="flex items-center gap-1.5 min-w-0">
                              {item.job_reference && (
                                <span className="font-mono text-[10px] font-bold text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">
                                  {item.job_reference}
                                </span>
                              )}
                              <span className="text-[10px] font-semibold text-slate-500 truncate">
                                {item.event_type.replace(/_/g, ' ')}
                              </span>
                            </div>
                            <span className="shrink-0 text-[10px] text-slate-400">
                              {formatRelativeTime(item.created_at)}
                            </span>
                          </div>

                          <p className="mt-1 text-xs text-slate-700 leading-snug break-words">
                            {item.message}
                          </p>
                        </div>

                        {isUnread && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              void markAsRead(item.id)
                            }}
                            className="shrink-0 p-1 rounded-md text-slate-400 hover:text-sky-600 hover:bg-sky-100 transition"
                            title="Mark as read"
                            aria-label="Mark as read"
                          >
                            <CheckCircleIcon className="h-4 w-4" />
                          </button>
                        )}
                      </div>
                    )
                  })
                )}
              </div>

              {/* Footer */}
              <div className="border-t border-slate-100 bg-slate-50/70 p-2 text-center">
                <Link
                  to="/notifications"
                  onClick={() => setPopoverOpen(false)}
                  className="inline-flex items-center gap-1.5 text-xs font-semibold text-maritime-800 hover:text-maritime-900 transition"
                >
                  <span>Open Full Notifications Center</span>
                  <ArrowRightIcon className="h-3.5 w-3.5" />
                </Link>
              </div>
            </div>
          )}
        </div>

        {/* User Avatar Circle */}
        <div
          className="grid h-8.5 w-8.5 place-items-center rounded-xl bg-gradient-to-tr from-maritime-800 to-cyan-700 text-xs font-bold text-white shadow-xs"
          title={user?.display_name}
        >
          {user?.display_name?.charAt(0).toUpperCase() ?? 'U'}
        </div>
      </div>
    </header>
  )
}
