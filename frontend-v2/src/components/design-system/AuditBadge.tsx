import {
  AlertTriangleIcon,
  CheckCircleIcon,
  FileCheckIcon,
  FileTextIcon,
  LockIcon,
  ShieldCheckIcon,
  UsersIcon,
} from '../icons'
import { classifyAuditAction } from './auditUtils'
import type { AuditCategory } from './auditUtils'

interface AuditBadgeProps {
  action: string
  category?: AuditCategory
  denied?: boolean
}

export function AuditBadge({ action, category, denied }: AuditBadgeProps) {
  const cat = category || classifyAuditAction(action)

  let badgeStyle = 'bg-slate-100 text-slate-700 border-slate-200'
  let label = 'Security & System'
  let Icon = LockIcon

  if (cat === 'workflow') {
    badgeStyle = 'bg-sky-50 text-sky-800 border-sky-200'
    label = 'Workflow Transition'
    Icon = FileCheckIcon
  } else if (cat === 'access') {
    badgeStyle = 'bg-violet-50 text-violet-800 border-violet-200'
    label = 'Role & Policy'
    Icon = ShieldCheckIcon
  } else if (cat === 'responsibility') {
    badgeStyle = 'bg-teal-50 text-teal-800 border-teal-200'
    label = 'Responsibility & Cover'
    Icon = UsersIcon
  } else if (cat === 'exception') {
    badgeStyle = 'bg-amber-50 text-amber-800 border-amber-200'
    label = 'Exception & Override'
    Icon = FileTextIcon
  } else if (cat === 'security') {
    badgeStyle = 'bg-rose-50 text-rose-800 border-rose-200'
    label = 'Account & Auth'
    Icon = LockIcon
  }

  return (
    <div className="inline-flex items-center gap-1.5 flex-wrap">
      <span className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold border ${badgeStyle}`}>
        <Icon className="h-3.5 w-3.5 shrink-0" />
        {label}
      </span>
      {denied && (
        <span className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-bold uppercase tracking-wider bg-red-100 text-red-800 border border-red-200">
          <AlertTriangleIcon className="h-3 w-3" />
          Denied
        </span>
      )}
      {!denied && (
        <span className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
          <CheckCircleIcon className="h-3 w-3" />
          Allowed
        </span>
      )}
    </div>
  )
}
