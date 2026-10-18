import { AirIcon, BoxIcon, ContainerIcon, ExportIcon, ImportIcon } from '../icons'

interface StatusBadgeProps {
  status: string
  size?: 'sm' | 'md'
  showIcon?: boolean
}

export function StatusBadge({ status, size = 'md', showIcon = true }: StatusBadgeProps) {
  const normalized = status.toLowerCase().replace(/[\s-]/g, '_')
  const label = status.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

  const sizeClasses =
    size === 'sm'
      ? 'px-2 py-0.5 text-[11px]'
      : 'px-2.5 py-1 text-xs'

  // Stage styles
  if (['confirmed', 'prepared', 'checked', 'filed', 'cancelled', 'reopened', 'archived'].includes(normalized)) {
    let toneClasses = 'bg-slate-100 text-slate-700 border-slate-200'
    let dotColor = 'bg-slate-400'

    if (normalized === 'confirmed') {
      toneClasses = 'bg-slate-100 text-slate-700 border-slate-200'
      dotColor = 'bg-slate-500'
    } else if (normalized === 'prepared') {
      toneClasses = 'bg-sky-50 text-sky-700 border-sky-200'
      dotColor = 'bg-sky-500'
    } else if (normalized === 'checked') {
      toneClasses = 'bg-indigo-50 text-indigo-700 border-indigo-200'
      dotColor = 'bg-indigo-500'
    } else if (normalized === 'filed') {
      toneClasses = 'bg-emerald-50 text-emerald-700 border-emerald-200'
      dotColor = 'bg-emerald-500'
    } else if (normalized === 'cancelled') {
      toneClasses = 'bg-rose-50 text-rose-700 border-rose-200'
      dotColor = 'bg-rose-500'
    } else if (normalized === 'reopened') {
      toneClasses = 'bg-amber-50 text-amber-800 border-amber-200'
      dotColor = 'bg-amber-500'
    } else if (normalized === 'archived') {
      toneClasses = 'bg-purple-50 text-purple-700 border-purple-200'
      dotColor = 'bg-purple-500'
    }

    return (
      <span className={`inline-flex items-center gap-1.5 rounded-full font-semibold border ${toneClasses} ${sizeClasses}`}>
        {showIcon && <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} aria-hidden="true" />}
        {label}
      </span>
    )
  }

  // Availability / Account status styles
  if (['available', 'busy', 'absent', 'active', 'pending', 'disabled'].includes(normalized)) {
    let toneClasses = 'bg-slate-100 text-slate-700 border-slate-200'
    let dotColor = 'bg-slate-400'

    if (normalized === 'available' || normalized === 'active') {
      toneClasses = 'bg-emerald-50 text-emerald-700 border-emerald-200'
      dotColor = 'bg-emerald-500'
    } else if (normalized === 'busy') {
      toneClasses = 'bg-blue-50 text-blue-700 border-blue-200'
      dotColor = 'bg-blue-500'
    } else if (normalized === 'absent') {
      toneClasses = 'bg-slate-100 text-slate-600 border-slate-200'
      dotColor = 'bg-slate-400'
    } else if (normalized === 'pending') {
      toneClasses = 'bg-amber-50 text-amber-800 border-amber-200'
      dotColor = 'bg-amber-500'
    } else if (normalized === 'disabled') {
      toneClasses = 'bg-rose-50 text-rose-700 border-rose-200'
      dotColor = 'bg-rose-500'
    }

    return (
      <span className={`inline-flex items-center gap-1.5 rounded-full font-semibold border ${toneClasses} ${sizeClasses}`}>
        {showIcon && <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} aria-hidden="true" />}
        {label}
      </span>
    )
  }

  // Generic fallback
  return (
    <span className={`inline-flex items-center gap-1 rounded-full font-medium bg-slate-100 text-slate-700 border border-slate-200 ${sizeClasses}`}>
      {label}
    </span>
  )
}

export function ModeBadge({ mode }: { mode: 'air' | 'fcl' | 'lcl' | string }) {
  const norm = mode.toLowerCase()
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-xs font-semibold uppercase tracking-wider text-slate-700 border border-slate-200">
      {norm === 'air' && <AirIcon className="h-3 w-3 text-sky-600" />}
      {norm === 'fcl' && <ContainerIcon className="h-3 w-3 text-blue-600" />}
      {norm === 'lcl' && <BoxIcon className="h-3 w-3 text-amber-600" />}
      {mode.toUpperCase()}
    </span>
  )
}

export function DirectionBadge({ direction }: { direction: 'import' | 'export' | string }) {
  const isImport = direction.toLowerCase() === 'import'
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-semibold uppercase tracking-wider border ${
        isImport
          ? 'bg-cyan-50 text-cyan-800 border-cyan-200'
          : 'bg-indigo-50 text-indigo-800 border-indigo-200'
      }`}
    >
      {isImport ? (
        <ImportIcon className="h-3 w-3 text-cyan-700" />
      ) : (
        <ExportIcon className="h-3 w-3 text-indigo-700" />
      )}
      {direction.toUpperCase()}
    </span>
  )
}

export function ResponsibilityBadge({ responsibility }: { responsibility: string }) {
  const norm = responsibility.toLowerCase().replace(/[\s-]/g, '_')
  const label = responsibility.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

  let colorClasses = 'bg-slate-100 text-slate-800 border-slate-200'
  if (norm === 'maker') {
    colorClasses = 'bg-sky-50 text-sky-800 border-sky-200'
  } else if (norm === 'checker') {
    colorClasses = 'bg-violet-50 text-violet-800 border-violet-200'
  } else if (norm === 'filing_officer') {
    colorClasses = 'bg-emerald-50 text-emerald-800 border-emerald-200'
  }

  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold border ${colorClasses}`}>
      {label}
    </span>
  )
}
