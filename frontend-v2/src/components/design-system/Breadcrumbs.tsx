import { Link, useLocation } from 'react-router-dom'
import { ChevronRightIcon } from '../icons'

export interface BreadcrumbItem {
  label: string
  to?: string
}

const routeLabels: Record<string, string> = {
  admin: 'Operations Command',
  jobs: 'Shipments',
  new: 'Create Shipment',
  employees: 'Workforce & Roles',
  requests: 'Urgent Requests',
  attention: 'Attention Queue',
  audit: 'Audit Explorer',
  work: 'Operational Workspace',
  absence: 'Absence & Delegation',
  notifications: 'Notifications',
  client: 'Client Portal',
  shipments: 'My Shipments',
  updates: 'Activity Feed',
}

export function Breadcrumbs({ items }: { items?: BreadcrumbItem[] }) {
  const location = useLocation()

  const crumbs: BreadcrumbItem[] = items || (() => {
    const parts = location.pathname.split('/').filter(Boolean)
    const result: BreadcrumbItem[] = [{ label: 'Home', to: '/' }]

    let accumulated = ''
    for (let i = 0; i < parts.length; i++) {
      accumulated += `/${parts[i]}`
      const isLast = i === parts.length - 1
      const part = parts[i]
      const label = routeLabels[part] || (part.length > 15 ? `${part.slice(0, 10)}...` : part)

      result.push({
        label,
        to: isLast ? undefined : accumulated,
      })
    }
    return result
  })()

  if (crumbs.length <= 1) return null

  return (
    <nav aria-label="Breadcrumb" className="flex items-center text-xs text-slate-500">
      <ol className="flex items-center flex-wrap gap-1.5">
        {crumbs.map((crumb, idx) => {
          const isLast = idx === crumbs.length - 1
          return (
            <li key={`${crumb.label}-${idx}`} className="flex items-center gap-1.5">
              {idx > 0 && <ChevronRightIcon className="h-3 w-3 text-slate-400 shrink-0" aria-hidden="true" />}
              {isLast || !crumb.to ? (
                <span className="font-semibold text-slate-800" aria-current="page">
                  {crumb.label}
                </span>
              ) : (
                <Link
                  to={crumb.to}
                  className="hover:text-slate-900 transition-colors underline-offset-2 hover:underline"
                >
                  {crumb.label}
                </Link>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
