import type { ReactNode } from 'react'

export function FullPageLoader({ label }: { label: string }) {
  return (
    <main className="grid min-h-screen place-items-center bg-canvas px-6" aria-busy="true">
      <div className="text-center">
        <span className="mx-auto block h-10 w-10 animate-spin rounded-full border-4 border-teal-100 border-t-teal-700" />
        <p className="mt-4 text-sm font-medium text-slate-600">{label}</p>
      </div>
    </main>
  )
}

export function InlineLoader({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 py-6 text-sm text-slate-600" aria-live="polite">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-teal-100 border-t-teal-700" />
      {label}
    </div>
  )
}

export function ErrorMessage({ message, title = 'We could not complete that request' }: {
  message: string
  title?: string
}) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm" role="alert">
      <p className="font-semibold text-red-900">{title}</p>
      <p className="mt-1 text-red-700">{message}</p>
    </div>
  )
}

export function EmptyState({ icon, title, message, action }: {
  icon?: ReactNode
  title: string
  message: string
  action?: ReactNode
}) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
      {icon && <div className="mx-auto mb-4 text-teal-700">{icon}</div>}
      <h2 className="text-lg font-semibold text-ink">{title}</h2>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-600">{message}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}
