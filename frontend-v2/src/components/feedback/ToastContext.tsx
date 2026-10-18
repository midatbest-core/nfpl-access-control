import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import {
  AlertCircleIcon,
  AlertTriangleIcon,
  ArrowRightIcon,
  CheckCircleIcon,
  CloseIcon,
  InfoIcon,
} from '../icons'

export type ToastType = 'success' | 'error' | 'warning' | 'info'

export interface ToastAction {
  label: string
  onClick: () => void
}

export interface ToastItem {
  id: string
  type: ToastType
  title: string
  message: string
  action?: ToastAction
}

interface ToastContextValue {
  toasts: ToastItem[]
  showToast: (type: ToastType, message: string, title?: string, action?: ToastAction) => void
  success: (message: string, title?: string, action?: ToastAction) => void
  error: (message: string, title?: string, action?: ToastAction) => void
  warning: (message: string, title?: string, action?: ToastAction) => void
  info: (message: string, title?: string, action?: ToastAction) => void
  dismissToast: (id: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const dismissToast = useCallback((id: string) => {
    setToasts((current) => current.filter((item) => item.id !== id))
  }, [])

  const showToast = useCallback(
    (type: ToastType, message: string, title?: string, action?: ToastAction) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
      const defaultTitle =
        type === 'success'
          ? 'Success'
          : type === 'error'
            ? 'Error'
            : type === 'warning'
              ? 'Warning'
              : 'Notice'

      const item: ToastItem = {
        id,
        type,
        title: title || defaultTitle,
        message,
        action,
      }

      setToasts((current) => [...current, item].slice(-5))

      window.setTimeout(() => {
        dismissToast(id)
      }, action ? 8000 : 5000)
    },
    [dismissToast],
  )

  const success = useCallback(
    (message: string, title?: string, action?: ToastAction) => showToast('success', message, title, action),
    [showToast],
  )
  const error = useCallback(
    (message: string, title?: string, action?: ToastAction) => showToast('error', message, title, action),
    [showToast],
  )
  const warning = useCallback(
    (message: string, title?: string, action?: ToastAction) => showToast('warning', message, title, action),
    [showToast],
  )
  const info = useCallback(
    (message: string, title?: string, action?: ToastAction) => showToast('info', message, title, action),
    [showToast],
  )

  const value = useMemo(
    () => ({
      toasts,
      showToast,
      success,
      error,
      warning,
      info,
      dismissToast,
    }),
    [toasts, showToast, success, error, warning, info, dismissToast],
  )

  return (
    <ToastContext.Provider value={value}>
      {children}
      {/* Top-Right Toast Container */}
      <aside
        aria-live="polite"
        aria-label="System notifications"
        className="fixed top-5 right-5 z-50 flex w-full max-w-sm flex-col gap-2.5 pointer-events-none"
      >
        {toasts.map((toast) => {
          const isSuccess = toast.type === 'success'
          const isError = toast.type === 'error'
          const isWarning = toast.type === 'warning'

          const borderBgClass = isSuccess
            ? 'border-emerald-200 bg-white shadow-emerald-950/5'
            : isError
              ? 'border-rose-200 bg-white shadow-rose-950/5'
              : isWarning
                ? 'border-amber-200 bg-white shadow-amber-950/5'
                : 'border-sky-200 bg-white shadow-sky-950/5'

          const iconClass = isSuccess
            ? 'text-emerald-600 bg-emerald-50'
            : isError
              ? 'text-rose-600 bg-rose-50'
              : isWarning
                ? 'text-amber-600 bg-amber-50'
                : 'text-sky-600 bg-sky-50'

          return (
            <div
              key={toast.id}
              role={isError ? 'alert' : 'status'}
              className={`pointer-events-auto flex items-start gap-3 rounded-xl border p-4 shadow-xl transition-all duration-200 animate-in fade-in slide-in-from-top-2 ${borderBgClass}`}
            >
              <div className={`mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg ${iconClass}`}>
                {isSuccess && <CheckCircleIcon className="h-4 w-4" />}
                {isError && <AlertCircleIcon className="h-4 w-4" />}
                {isWarning && <AlertTriangleIcon className="h-4 w-4" />}
                {!isSuccess && !isError && !isWarning && <InfoIcon className="h-4 w-4" />}
              </div>

              <div className="min-w-0 flex-1">
                <p className="text-xs font-bold uppercase tracking-wider text-slate-800">
                  {toast.title}
                </p>
                <p className="mt-0.5 text-sm text-slate-600 leading-snug break-words">
                  {toast.message}
                </p>
                {toast.action && (
                  <div className="mt-2.5">
                    <button
                      type="button"
                      onClick={() => {
                        toast.action?.onClick()
                        dismissToast(toast.id)
                      }}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-maritime-800 hover:bg-maritime-900 text-white px-2.5 py-1 text-xs font-semibold shadow-xs transition cursor-pointer"
                    >
                      <span>{toast.action.label}</span>
                      <ArrowRightIcon className="h-3 w-3" />
                    </button>
                  </div>
                )}
              </div>

              <button
                type="button"
                onClick={() => dismissToast(toast.id)}
                className="shrink-0 rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                aria-label="Dismiss notification"
              >
                <CloseIcon className="h-4 w-4" />
              </button>
            </div>
          )
        })}
      </aside>
    </ToastContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useToast(): ToastContextValue {
  const value = useContext(ToastContext)
  if (!value) {
    throw new Error('useToast must be used inside ToastProvider')
  }
  return value
}
