const toneByStatus: Record<string, string> = {
  active: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  available: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  pending: 'bg-amber-50 text-amber-800 ring-amber-600/20',
  busy: 'bg-sky-50 text-sky-700 ring-sky-600/20',
  absent: 'bg-slate-100 text-slate-700 ring-slate-500/20',
  disabled: 'bg-red-50 text-red-700 ring-red-600/20',
  confirmed: 'bg-slate-100 text-slate-700 ring-slate-500/20',
  prepared: 'bg-blue-50 text-blue-700 ring-blue-600/20',
  checked: 'bg-violet-50 text-violet-700 ring-violet-600/20',
  filed: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  cancelled: 'bg-red-50 text-red-700 ring-red-600/20',
}

export function StatusBadge({ status }: { status: string }) {
  const label = status.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${toneByStatus[status] ?? 'bg-slate-100 text-slate-700 ring-slate-500/20'}`}>
      {label}
    </span>
  )
}
