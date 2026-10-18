import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { Notification } from '../api/contracts'
import { useAuth } from '../auth/AuthContext'
import { effectiveRoles, ROLE } from '../auth/roles'
import { useToast } from '../components/feedback/ToastContext'

export interface NotificationContextValue {
  notifications: Notification[]
  unreadCount: number
  loading: boolean
  refresh: () => Promise<void>
  markAsRead: (id: string) => Promise<void>
  markAllRead: () => Promise<void>
  clearAll: () => Promise<void>
  openNotificationTarget: (notification: Notification) => Promise<void>
}

const NotificationContext = createContext<NotificationContextValue | null>(null)

export function NotificationProvider({ children }: { children: ReactNode }) {
  const { token, user } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()

  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(true)

  const seenIds = useRef(new Set<string>())
  const initialFetchDone = useRef(false)
  const isRefreshing = useRef(false)
  const lastRefreshTimestamp = useRef(0)
  const roles = useMemo(() => effectiveRoles(user), [user])

  const openNotificationTarget = useCallback(
    async (item: Notification) => {
      if (!token) return

      // Optimistically mark as read
      if (!item.read_at) {
        try {
          await api.markNotificationRead(token, item.id)
          setNotifications((current) =>
            current.map((n) => (n.id === item.id ? { ...n, read_at: new Date().toISOString() } : n)),
          )
          setUnreadCount((count) => Math.max(0, count - 1))
        } catch {
          // Continue navigation even if read ack fails
        }
      }

      if (item.job_id) {
        if (user?.kind === 'client') {
          navigate(`/client/shipments/${item.job_id}`)
        } else if (roles.has(ROLE.admin)) {
          navigate(`/admin/jobs/${item.job_id}`)
        } else {
          navigate(`/work/jobs/${item.job_id}`)
        }
        return
      }

      if (item.target_path.includes('absence')) {
        if (roles.has(ROLE.admin)) {
          navigate('/admin/workforce')
        } else {
          navigate('/absence')
        }
        return
      }

      if (item.target_path.includes('my-work')) {
        navigate('/work')
        return
      }

      navigate('/notifications')
    },
    [token, user, roles, navigate],
  )

  const refresh = useCallback(async () => {
    if (!token || isRefreshing.current) return
    isRefreshing.current = true
    lastRefreshTimestamp.current = Date.now()

    try {
      const items = await api.notifications(token)
      const clearedAt = user?.id ? localStorage.getItem(`nfpl.notifications_cleared_at.${user.id}`) : null
      const clearedTime = clearedAt ? new Date(clearedAt).getTime() : 0

      // Only show notifications newer than clearedTime if user clicked "Clear all"
      const activeItems = clearedTime > 0
        ? items.filter((n) => new Date(n.created_at).getTime() > clearedTime)
        : items

      setNotifications(activeItems)

      const unread = activeItems.filter((n) => !n.read_at)
      setUnreadCount(unread.length)

      const fresh = unread.filter((n) => !seenIds.current.has(n.id))

      // Track all retrieved IDs
      activeItems.forEach((n) => seenIds.current.add(n.id))

      // If this is a dynamic background update and there are fresh notifications, POP UP!
      if (initialFetchDone.current && fresh.length > 0) {
        fresh.forEach((item) => {
          toast.info(
            item.message,
            item.job_reference ? `Shipment ${item.job_reference}` : 'Shipment Alert',
            {
              label: 'Open Details',
              onClick: () => {
                void openNotificationTarget(item)
              },
            },
          )
        })
      }
      initialFetchDone.current = true
    } catch {
      // Catch errors silently for background poll
    } finally {
      isRefreshing.current = false
      setLoading(false)
    }
  }, [token, user, toast, openNotificationTarget])

  const markAsRead = useCallback(
    async (id: string) => {
      if (!token) return
      try {
        await api.markNotificationRead(token, id)
        setNotifications((current) =>
          current.map((n) => (n.id === id ? { ...n, read_at: new Date().toISOString() } : n)),
        )
        setUnreadCount((count) => Math.max(0, count - 1))
      } catch {
        toast.error('Could not update notification status', 'Error')
      }
    },
    [token, toast],
  )

  const markAllRead = useCallback(async () => {
    if (!token) return
    try {
      await api.markAllNotificationsRead(token)
      setNotifications((current) =>
        current.map((n) => ({ ...n, read_at: n.read_at || new Date().toISOString() })),
      )
      setUnreadCount(0)
      toast.success('All notifications marked as read', 'Notifications Updated')
    } catch {
      toast.error('Could not mark all notifications as read', 'Error')
    }
  }, [token, toast])

  const clearAll = useCallback(async () => {
    if (!token) return
    try {
      await api.markAllNotificationsRead(token)
    } catch {
      // Continue locally even if network fails
    }
    const nowIso = new Date().toISOString()
    if (user?.id) {
      localStorage.setItem(`nfpl.notifications_cleared_at.${user.id}`, nowIso)
    }
    setNotifications([])
    setUnreadCount(0)
    toast.success('All notifications cleared from your panel.', 'Notifications Cleared')
  }, [token, user, toast])

  // Efficient Polling & Real-Time Listeners (Respecting 5-Connection Database Pool)
  useEffect(() => {
    if (!token) return

    queueMicrotask(() => {
      void refresh()
    })

    // Poll every 20 seconds while page is active and visible
    const interval = window.setInterval(() => {
      if (document.visibilityState === 'visible' && !isRefreshing.current) {
        void refresh()
      }
    }, 20_000)

    const onFocus = () => {
      if (Date.now() - lastRefreshTimestamp.current > 4_000) {
        void refresh()
      }
    }

    const onVisibility = () => {
      if (document.visibilityState === 'visible' && Date.now() - lastRefreshTimestamp.current > 4_000) {
        void refresh()
      }
    }

    const onCustomRefresh = () => {
      if (Date.now() - lastRefreshTimestamp.current > 3_000) {
        void refresh()
      }
    }

    window.addEventListener('focus', onFocus)
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('nfpl:refresh-notifications', onCustomRefresh)

    return () => {
      window.clearInterval(interval)
      window.removeEventListener('focus', onFocus)
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('nfpl:refresh-notifications', onCustomRefresh)
    }
  }, [token, refresh])

  const value = useMemo<NotificationContextValue>(
    () => ({
      notifications,
      unreadCount,
      loading,
      refresh,
      markAsRead,
      markAllRead,
      clearAll,
      openNotificationTarget,
    }),
    [notifications, unreadCount, loading, refresh, markAsRead, markAllRead, clearAll, openNotificationTarget],
  )

  return <NotificationContext.Provider value={value}>{children}</NotificationContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useNotifications(): NotificationContextValue {
  const value = useContext(NotificationContext)
  if (!value) {
    return {
      notifications: [],
      unreadCount: 0,
      loading: false,
      refresh: async () => {},
      markAsRead: async () => {},
      markAllRead: async () => {},
      clearAll: async () => {},
      openNotificationTarget: async () => {},
    }
  }
  return value
}
