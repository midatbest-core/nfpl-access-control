import type { ReactNode } from 'react'
import { ChevronLeftIcon, ChevronRightIcon, SearchIcon } from '../icons'
import { EmptyState } from './EmptyState'
import { SkeletonTable } from './LoadingSkeleton'

export interface Column<T> {
  key: string
  header: string
  render: (item: T, index: number) => ReactNode
  className?: string
}

interface SearchTableProps<T> {
  data: T[]
  columns: Column<T>[]
  keyExtractor: (item: T, index: number) => string
  searchQuery?: string
  onSearchChange?: (query: string) => void
  searchPlaceholder?: string
  filterBar?: ReactNode
  totalCount?: number
  page?: number
  pageSize?: number
  hasNextPage?: boolean
  hasPrevPage?: boolean
  onNextPage?: () => void
  onPrevPage?: () => void
  isLoading?: boolean
  emptyTitle?: string
  emptyDescription?: string
  emptyAction?: ReactNode
  className?: string
}

export function SearchTable<T>({
  data,
  columns,
  keyExtractor,
  searchQuery,
  onSearchChange,
  searchPlaceholder = 'Search records...',
  filterBar,
  totalCount,
  page,
  hasNextPage = false,
  hasPrevPage = false,
  onNextPage,
  onPrevPage,
  isLoading = false,
  emptyTitle = 'No records found',
  emptyDescription = 'There are no items matching your criteria or currently available in this view.',
  emptyAction,
  className = '',
}: SearchTableProps<T>) {
  return (
    <div className={`space-y-4 ${className}`}>
      {/* Control Bar: Search Input & Custom Filter Controls */}
      {(onSearchChange || filterBar) && (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          {onSearchChange && (
            <div className="relative w-full sm:max-w-xs">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                {isLoading ? (
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-cyan-600 border-t-transparent" />
                ) : (
                  <SearchIcon className="h-4 w-4" />
                )}
              </div>
              <input
                type="search"
                value={searchQuery ?? ''}
                onChange={(e) => onSearchChange(e.target.value)}
                placeholder={searchPlaceholder}
                className={`block w-full rounded-xl border border-slate-300 bg-white py-2 pl-9 ${
                  isLoading ? 'pr-24' : 'pr-3'
                } text-sm text-slate-900 placeholder:text-slate-400 focus:border-cyan-600 focus:outline-hidden focus:ring-3 focus:ring-cyan-100 transition`}
                aria-label={searchPlaceholder}
              />
              {isLoading && (
                <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2.5">
                  <span className="inline-flex items-center gap-1.5 rounded-md bg-cyan-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-cyan-700 animate-pulse border border-cyan-200 shadow-2xs">
                    <span className="h-1.5 w-1.5 rounded-full bg-cyan-500 animate-ping" />
                    Searching
                  </span>
                </div>
              )}
            </div>
          )}
          {filterBar && <div className="flex flex-wrap items-center gap-2">{filterBar}</div>}
        </div>
      )}

      {/* Table Surface */}
      {isLoading && data.length === 0 ? (
        <SkeletonTable rows={5} cols={columns.length} />
      ) : data.length === 0 ? (
        <EmptyState
          title={emptyTitle}
          description={emptyDescription}
          action={emptyAction}
        />
      ) : (
        <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xs">
          {/* Animated Searching Progress Bar */}
          {isLoading && (
            <div className="absolute top-0 inset-x-0 h-1 z-20 bg-slate-100 overflow-hidden">
              <div className="h-full w-2/5 bg-linear-to-r from-cyan-500 via-sky-400 to-cyan-500 rounded-full animate-search-glide" />
            </div>
          )}

          {/* Searching Overlay with Floating Badge */}
          {isLoading && (
            <div className="absolute inset-0 bg-white/40 backdrop-blur-[0.5px] z-10 flex items-center justify-center transition-opacity duration-200 pointer-events-none">
              <div className="inline-flex items-center gap-2.5 rounded-full bg-slate-900/90 backdrop-blur-md px-4 py-2 text-xs font-semibold text-white shadow-xl animate-pulse">
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />
                <span>Searching records...</span>
              </div>
            </div>
          )}

          <div className={`overflow-x-auto ${isLoading ? 'opacity-60 transition-opacity duration-200' : ''}`}>
            <table className="w-full text-left border-collapse text-sm">
              <thead className="border-b border-slate-200 bg-slate-50/80 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                <tr>
                  {columns.map((col) => (
                    <th key={col.key} scope="col" className={`px-5 py-3.5 ${col.className ?? ''}`}>
                      {col.header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {data.map((item, index) => (
                  <tr
                    key={keyExtractor(item, index)}
                    className="transition-colors hover:bg-slate-50/70"
                  >
                    {columns.map((col) => (
                      <td key={col.key} className={`px-5 py-3.5 ${col.className ?? ''}`}>
                        {col.render(item, index)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination Footer */}
          {(onNextPage || onPrevPage || totalCount !== undefined) && (
            <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50/50 px-5 py-3 text-xs text-slate-500">
              <div>
                {totalCount !== undefined ? (
                  <span>Showing {data.length} of {totalCount} items</span>
                ) : page !== undefined ? (
                  <span>Page {page}</span>
                ) : (
                  <span>Showing {data.length} items</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={onPrevPage}
                  disabled={!hasPrevPage}
                  className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 shadow-2xs transition hover:bg-slate-50 disabled:opacity-40"
                  aria-label="Previous page"
                >
                  <ChevronLeftIcon className="h-3.5 w-3.5" />
                  Previous
                </button>
                <button
                  type="button"
                  onClick={onNextPage}
                  disabled={!hasNextPage}
                  className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 shadow-2xs transition hover:bg-slate-50 disabled:opacity-40"
                  aria-label="Next page"
                >
                  Next
                  <ChevronRightIcon className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
