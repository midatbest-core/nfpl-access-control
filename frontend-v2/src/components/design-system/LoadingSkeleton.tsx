export function SkeletonLine({
  className = 'h-4 w-full',
}: {
  className?: string
}) {
  return (
    <div
      className={`rounded-md bg-slate-200/80 animate-shimmer ${className}`}
      aria-hidden="true"
    />
  )
}

export function SkeletonCard({
  lines = 3,
  className = '',
}: {
  lines?: number
  className?: string
}) {
  return (
    <div
      className={`rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm space-y-4 ${className}`}
      aria-hidden="true"
    >
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-xl bg-slate-200 animate-shimmer shrink-0" />
        <div className="space-y-1.5 flex-1">
          <SkeletonLine className="h-4 w-1/3" />
          <SkeletonLine className="h-3 w-1/2" />
        </div>
      </div>
      <div className="space-y-2 pt-2 border-t border-slate-100">
        {Array.from({ length: lines }).map((_, i) => (
          <SkeletonLine
            key={i}
            className={`h-3.5 ${i === lines - 1 ? 'w-2/3' : 'w-full'}`}
          />
        ))}
      </div>
    </div>
  )
}

export function SkeletonTable({
  rows = 5,
  cols = 4,
}: {
  rows?: number
  cols?: number
}) {
  return (
    <div className="w-full overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm" aria-hidden="true">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50/75 px-6 py-4">
        {Array.from({ length: cols }).map((_, c) => (
          <SkeletonLine key={c} className="h-4 w-20" />
        ))}
      </div>
      {/* Rows */}
      <div className="divide-y divide-slate-100">
        {Array.from({ length: rows }).map((_, r) => (
          <div key={r} className="flex items-center justify-between px-6 py-4">
            {Array.from({ length: cols }).map((_, c) => (
              <SkeletonLine
                key={c}
                className={`h-4 ${c === 0 ? 'w-28' : c === 1 ? 'w-36' : 'w-20'}`}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

export function SkeletonMetricsGrid() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-hidden="true">
      {Array.from({ length: 4 }).map((_, i) => (
        <SkeletonMetricCard key={i} />
      ))}
    </div>
  )
}

export function SkeletonMetricCard() {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm space-y-3" aria-hidden="true">
      <SkeletonLine className="h-3 w-20" />
      <SkeletonLine className="h-8 w-24" />
      <SkeletonLine className="h-3 w-32" />
    </div>
  )
}

