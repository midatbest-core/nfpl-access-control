import { useEffect } from 'react'
import { AlertTriangleIcon, CloseIcon } from '../icons'

interface ConfirmationDialogProps {
  open: boolean
  title: string
  message: React.ReactNode
  confirmLabel?: string
  cancelLabel?: string
  dangerous?: boolean
  danger?: boolean
  isLoading?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmationDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  dangerous = false,
  danger = false,
  isLoading = false,
  onConfirm,
  onCancel,
}: ConfirmationDialogProps) {
  const isDangerous = danger || dangerous
  useEffect(() => {
    if (!open) return

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        onCancel()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, onCancel])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-sm transition-opacity"
      role="presentation"
      onMouseDown={onCancel}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        onMouseDown={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl border border-slate-100 transition-all transform animate-in fade-in zoom-in-95 duration-150"
      >
        <div className="flex items-start gap-4">
          <div
            className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${
              isDangerous ? 'bg-rose-50 text-rose-600' : 'bg-sky-50 text-sky-600'
            }`}
          >
            <AlertTriangleIcon className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 id="dialog-title" className="text-base font-bold text-slate-900">
              {title}
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">
              {message}
            </p>
          </div>
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            aria-label="Close dialog"
          >
            <CloseIcon className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={isLoading}
            className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 focus-visible:outline-slate-600"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isLoading}
            className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-white shadow-sm transition focus-visible:outline-2 ${
              isDangerous
                ? 'bg-rose-600 hover:bg-rose-700 focus-visible:outline-rose-600'
                : 'bg-maritime-800 hover:bg-maritime-900 focus-visible:outline-maritime-800'
            }`}
          >
            {isLoading && (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white" />
            )}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
