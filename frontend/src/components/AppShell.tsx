import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { effectiveRoles, ROLE } from '../auth/roles'
import { ConfirmationDialog, NotificationBell } from './Controls'
import { StatusBadge } from './StatusBadge'

interface NavigationItem {
  label: string
  to: string
  section: 'Admin' | 'Operations' | 'Client'
}

const adminItems: NavigationItem[] = [
  { label: 'Overview', to: '/admin', section: 'Admin' },
  { label: 'Jobs', to: '/admin/jobs', section: 'Admin' },
  { label: 'Employees', to: '/admin/employees', section: 'Admin' },
  { label: 'Urgent requests', to: '/admin/requests', section: 'Admin' },
  { label: 'Notifications', to: '/notifications', section: 'Admin' },
  { label: 'Audit history', to: '/admin/audit', section: 'Admin' },
]

const operationsItems: NavigationItem[] = [
  { label: 'My work', to: '/work', section: 'Operations' },
  { label: 'Notifications', to: '/notifications', section: 'Operations' },
]

const clientItems: NavigationItem[] = [
  { label: 'My shipments', to: '/client/shipments', section: 'Client' },
  { label: 'Recent updates', to: '/client/updates', section: 'Client' },
]

function Logo() {
  return (
    <div className="flex items-center gap-3">
      <div className="grid h-10 w-10 place-items-center rounded-xl bg-teal-700 text-sm font-black tracking-tight text-white shadow-sm">NF</div>
      <div><p className="text-sm font-bold tracking-wide text-white">NFPL</p><p className="text-xs text-teal-100">Shipment operations</p></div>
    </div>
  )
}

function Navigation({ items, onNavigate }: { items: NavigationItem[]; onNavigate: () => void }) {
  const sections = [...new Set(items.map((item) => item.section))]
  return (
    <nav className="mt-8 space-y-6" aria-label="Primary navigation">
      {sections.map((section) => (
        <div key={section}>
          <p className="mb-2 px-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-teal-200/70">{section}</p>
          <div className="space-y-1">
            {items.filter((item) => item.section === section).map((item) => (
              <NavLink key={`${section}-${item.to}`} to={item.to} end={item.to === '/admin' || item.to === '/work'} onClick={onNavigate} className={({ isActive }) => `flex items-center rounded-xl px-3 py-2.5 text-sm font-medium transition ${isActive ? 'bg-white text-teal-900 shadow-sm' : 'text-teal-50 hover:bg-white/10 hover:text-white'}`}>
                <span className="mr-3 h-1.5 w-1.5 rounded-full bg-current opacity-70" />{item.label}
              </NavLink>
            ))}
          </div>
        </div>
      ))}
    </nav>
  )
}

export function AppShell() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [confirmLogout, setConfirmLogout] = useState(false)
  const roles = useMemo(() => effectiveRoles(user), [user])
  const navigation = useMemo(() => {
    const items: NavigationItem[] = []
    if (roles.has(ROLE.admin)) items.push(...adminItems)
    if ([ROLE.maker, ROLE.checker, ROLE.filingOfficer].some((role) => roles.has(role))) items.push(...operationsItems)
    if (roles.has(ROLE.clientViewer)) items.push(...clientItems)
    return items.filter((item, index) => items.findIndex((candidate) => candidate.to === item.to) === index)
  }, [roles])
  const activeLabel = navigation.find((item) => item.to === location.pathname)?.label ?? 'NFPL Operations'

  async function handleLogout() {
    setConfirmLogout(false)
    await logout()
    navigate('/login', { replace: true })
  }

  const sidebar = (
    <div className="flex h-full flex-col bg-deep-teal px-4 py-5">
      <Logo />
      <Navigation items={navigation} onNavigate={() => setMobileOpen(false)} />
      <div className="mt-auto border-t border-white/10 pt-4">
        <button type="button" onClick={() => setConfirmLogout(true)} className="w-full rounded-xl px-3 py-2.5 text-left text-sm font-medium text-teal-50 transition hover:bg-white/10">Sign out</button>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-canvas">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 lg:block">{sidebar}</aside>
      {mobileOpen && <div className="fixed inset-0 z-40 lg:hidden"><button aria-label="Close navigation" className="absolute inset-0 bg-slate-950/50" onClick={() => setMobileOpen(false)} /><aside className="relative h-full w-72 shadow-2xl">{sidebar}</aside></div>}
      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-18 items-center gap-4 border-b border-slate-200/80 bg-white/95 px-4 backdrop-blur sm:px-6 lg:px-8">
          <button type="button" className="grid h-10 w-10 place-items-center rounded-xl text-slate-600 hover:bg-slate-100 lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Open navigation">
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 7h16M4 12h16M4 17h16" /></svg>
          </button>
          <div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-ink">{activeLabel}</p><p className="hidden truncate text-xs text-slate-500 sm:block">Secure shipment access workspace</p></div>
          <NotificationBell onClick={() => navigate('/notifications')} />
          <div className="hidden h-8 w-px bg-slate-200 sm:block" />
          <div className="hidden min-w-0 items-center gap-3 sm:flex">
            <div className="grid h-9 w-9 place-items-center rounded-full bg-teal-50 text-sm font-bold text-teal-800">{user?.display_name.slice(0, 1).toUpperCase()}</div>
            <div className="max-w-44"><p className="truncate text-sm font-semibold text-ink">{user?.display_name}</p><div className="mt-0.5"><StatusBadge status={user?.availability ?? 'available'} /></div></div>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-7 sm:px-6 lg:px-8 lg:py-9"><Outlet /></main>
      </div>
      <ConfirmationDialog open={confirmLogout} title="Sign out of NFPL?" message="You will need to enter your credentials again to return to your workspace." confirmLabel="Sign out" dangerous onConfirm={() => void handleLogout()} onCancel={() => setConfirmLogout(false)} />
    </div>
  )
}

export function PageHeader({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description: string; action?: ReactNode }) {
  return (
    <header className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div>{eyebrow && <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-teal-700">{eyebrow}</p>}<h1 className="text-2xl font-bold tracking-tight text-ink sm:text-3xl">{title}</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">{description}</p></div>
      {action}
    </header>
  )
}
