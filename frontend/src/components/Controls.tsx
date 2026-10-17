import type { ReactNode } from 'react'

export function SearchField({
  value,
  onChange,
  label = 'Search',
  placeholder = 'Search',
}: {
  value: string
  onChange: (value: string) => void
  label?: string
  placeholder?: string
}) {
  return (
    <label className="relative block">
      <span className="sr-only">{label}</span>
      <svg aria-hidden="true" viewBox="0 0 24 24" className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" />
      </svg>
      <input className="field pl-10" type="search" value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />
    </label>
  )
}

export function ConfirmationDialog({
  open,
  title,
  message,
  confirmLabel,
  onConfirm,
  onCancel,
  dangerous = false,
}: {
  open: boolean
  title: string
  message: string
  confirmLabel: string
  onConfirm: () => void
  onCancel: () => void
  dangerous?: boolean
}) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/45 p-4" role="presentation" onMouseDown={onCancel}>
      <section className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl" role="dialog" aria-modal="true" aria-labelledby="confirmation-title" onMouseDown={(event) => event.stopPropagation()}>
        <h2 id="confirmation-title" className="text-xl font-semibold text-ink">{title}</h2>
        <p className="mt-3 text-sm leading-6 text-slate-600">{message}</p>
        <div className="mt-6 flex justify-end gap-3">
          <button type="button" className="button-secondary" onClick={onCancel}>Keep working</button>
          <button type="button" className={dangerous ? 'button-danger' : 'button-primary'} onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </section>
    </div>
  )
}

export function PaginatedList<T>({
  items,
  renderItem,
  hasNext,
  hasPrevious,
  onNext,
  onPrevious,
  empty,
}: {
  items: T[]
  renderItem: (item: T) => ReactNode
  hasNext: boolean
  hasPrevious: boolean
  onNext: () => void
  onPrevious: () => void
  empty: ReactNode
}) {
  if (items.length === 0) return empty
  return (
    <div>
      <div className="space-y-3">{items.map(renderItem)}</div>
      <nav className="mt-6 flex items-center justify-between border-t border-slate-200 pt-4" aria-label="Pagination">
        <button type="button" className="button-secondary" disabled={!hasPrevious} onClick={onPrevious}>Previous</button>
        <button type="button" className="button-secondary" disabled={!hasNext} onClick={onNext}>Next</button>
      </nav>
    </div>
  )
}

export function NotificationBell() {
  return (
    <button type="button" className="relative grid h-10 w-10 place-items-center rounded-xl text-slate-500 transition hover:bg-slate-100 hover:text-ink" aria-label="Notifications - available in a later frontend phase" title="Notification center coming in a later phase">
      <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M10 21h4" />
      </svg>
    </button>
  )
}
