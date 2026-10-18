import type { ComponentType, SVGProps } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { effectiveRoles, ROLE } from '../../auth/roles'
import {
  AirIcon,
  AlertTriangleIcon,
  AnchorIcon,
  BellIcon,
  BoxIcon,
  ClockIcon,
  FileCheckIcon,
  FileTextIcon,
  HistoryIcon,
  LayersIcon,
  LogOutIcon,
  UsersIcon,
} from '../icons'

interface NavItem {
  label: string
  to: string
  icon: ComponentType<SVGProps<SVGSVGElement>>
  section: string
  exact?: boolean
}

export function Sidebar({
  mobileOpen,
  onCloseMobile,
  onSignOut,
}: {
  mobileOpen: boolean
  onCloseMobile: () => void
  onSignOut: () => void
}) {
  const { user } = useAuth()
  const roles = effectiveRoles(user)

  const items: NavItem[] = []

  // Admin section
  if (roles.has(ROLE.admin)) {
    items.push(
      { label: 'Operations Command', to: '/admin', icon: LayersIcon, section: 'Admin Command', exact: true },
      { label: 'Shipments', to: '/admin/jobs', icon: BoxIcon, section: 'Admin Command' },
      { label: 'Workforce & Roles', to: '/admin/employees', icon: UsersIcon, section: 'Admin Command' },
      { label: 'Urgent Requests', to: '/admin/requests', icon: AlertTriangleIcon, section: 'Admin Command' },
      { label: 'Attention Queue', to: '/admin/attention', icon: ClockIcon, section: 'Admin Command' },
      { label: 'Audit Explorer', to: '/admin/audit', icon: HistoryIcon, section: 'Admin Command' },
    )
  }

  // Operations section
  if ([ROLE.maker, ROLE.checker, ROLE.filingOfficer].some((r) => roles.has(r))) {
    items.push(
      { label: 'My Work Queue', to: '/work', icon: FileCheckIcon, section: 'Operations Workspace', exact: true },
      { label: 'Absence & Delegation', to: '/absence', icon: UsersIcon, section: 'Operations Workspace' },
      { label: 'Notifications', to: '/notifications', icon: BellIcon, section: 'Operations Workspace' },
    )
  }

  // Client section
  if (roles.has(ROLE.clientViewer)) {
    items.push(
      { label: 'My Shipments', to: '/client/shipments', icon: AirIcon, section: 'Client Portal', exact: true },
      { label: 'Activity Updates', to: '/client/updates', icon: FileTextIcon, section: 'Client Portal' },
      { label: 'Notifications', to: '/notifications', icon: BellIcon, section: 'Client Portal' },
    )
  }

  // Deduplicate items with identical 'to'
  const uniqueItems = items.filter(
    (item, index, self) => index === self.findIndex((other) => other.to === item.to),
  )

  const sections = Array.from(new Set(uniqueItems.map((item) => item.section)))

  const content = (
    <div className="flex h-full flex-col bg-maritime-900 text-slate-200">
      {/* Brand Header */}
      <div className="flex items-center gap-3 border-b border-maritime-800/80 px-6 py-5">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-cyan-500 to-sky-700 text-white shadow-md shadow-cyan-900/40">
          <AnchorIcon className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-extrabold tracking-wide text-white">NFPL</span>
            <span className="rounded-sm bg-cyan-500/20 px-1 py-0.2 text-[9px] font-bold text-cyan-300 uppercase tracking-widest">
              Logistics
            </span>
          </div>
          <p className="text-[11px] text-slate-400 truncate">Nagarkot Forwarders</p>
        </div>
      </div>

      {/* Navigation Groups */}
      <nav aria-label="Main sidebar navigation" className="flex-1 overflow-y-auto px-4 py-5 space-y-6">
        {sections.map((section) => (
          <div key={section} className="space-y-1">
            <p className="px-3 text-[10px] font-bold uppercase tracking-widest text-slate-400">
              {section}
            </p>
            <div className="space-y-0.5 pt-1">
              {uniqueItems
                .filter((item) => item.section === section)
                .map((item) => {
                  const Icon = item.icon
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      end={item.exact}
                      onClick={onCloseMobile}
                      className={({ isActive }) =>
                        `group flex items-center gap-3 rounded-xl px-3 py-2 text-xs font-semibold transition ${
                          isActive
                            ? 'bg-maritime-800 text-white shadow-xs'
                            : 'text-slate-300 hover:bg-maritime-800/60 hover:text-white'
                        }`
                      }
                    >
                      {({ isActive }) => (
                        <>
                          <Icon
                            className={`h-4 w-4 shrink-0 transition ${
                              isActive ? 'text-cyan-400' : 'text-slate-400 group-hover:text-slate-200'
                            }`}
                          />
                          <span className="truncate">{item.label}</span>
                          {isActive && (
                            <span className="ml-auto h-1.5 w-1.5 rounded-full bg-cyan-400" aria-hidden="true" />
                          )}
                        </>
                      )}
                    </NavLink>
                  )
                })}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer User Profile & Sign Out */}
      <div className="border-t border-maritime-800/80 p-4">
        <div className="flex items-center justify-between rounded-xl bg-maritime-950/60 p-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-cyan-600/30 text-xs font-bold text-cyan-300 border border-cyan-500/30">
              {user?.display_name?.charAt(0).toUpperCase() ?? 'U'}
            </div>
            <div className="min-w-0">
              <p className="truncate text-xs font-bold text-white">{user?.display_name}</p>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    user?.availability === 'available'
                      ? 'bg-emerald-400'
                      : user?.availability === 'busy'
                        ? 'bg-sky-400'
                        : 'bg-slate-400'
                  }`}
                  aria-hidden="true"
                />
                <span className="text-[10px] text-slate-300 capitalize truncate">
                  {user?.availability ?? 'Offline'}
                </span>
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={onSignOut}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-maritime-800 hover:text-rose-400 transition"
            title="Sign out of workspace"
            aria-label="Sign out"
          >
            <LogOutIcon className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )

  return (
    <>
      {/* Desktop Fixed Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 lg:block">
        {content}
      </aside>

      {/* Mobile Drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            className="fixed inset-0 bg-slate-950/60 backdrop-blur-xs transition-opacity"
            onClick={onCloseMobile}
            aria-label="Close mobile sidebar"
          />
          <aside className="relative h-full w-72 max-w-[85vw] shadow-2xl">
            {content}
          </aside>
        </div>
      )}
    </>
  )
}
