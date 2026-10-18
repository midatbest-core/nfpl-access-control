import { useState } from 'react'
import type { ReactNode } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { NotificationProvider } from '../../context/NotificationContext'
import { ConfirmationDialog } from '../design-system/ConfirmationDialog'
import { Sidebar } from './Sidebar'
import { TopNav } from './TopNav'

export function AppShell() {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [confirmSignOut, setConfirmSignOut] = useState(false)

  async function handleConfirmedSignOut() {
    setConfirmSignOut(false)
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <NotificationProvider>
      <div className="min-h-screen bg-slate-50 text-slate-900">
        {/* Sidebar Navigation */}
        <Sidebar
          mobileOpen={mobileOpen}
          onCloseMobile={() => setMobileOpen(false)}
          onSignOut={() => setConfirmSignOut(true)}
        />

        {/* Main Content Area */}
        <div className="lg:pl-64 flex flex-col min-h-screen">
          <TopNav
            onOpenMobile={() => setMobileOpen(true)}
            onSignOut={() => setConfirmSignOut(true)}
          />

          <main className="flex-1 mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
            <Outlet />
          </main>
        </div>

        {/* Sign Out Confirmation Modal */}
        <ConfirmationDialog
          open={confirmSignOut}
          title="Sign out of NFPL workspace?"
          message="Your active session will be closed on the server. You will need to re-authenticate with your email and password to return."
          confirmLabel="Sign out"
          dangerous
          onConfirm={() => void handleConfirmedSignOut()}
          onCancel={() => setConfirmSignOut(false)}
        />
      </div>
    </NotificationProvider>
  )
}

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between pb-2 border-b border-slate-200/60">
      <div>
        {eyebrow && (
          <p className="text-xs font-bold uppercase tracking-wider text-maritime-700">
            {eyebrow}
          </p>
        )}
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">
          {title}
        </h1>
        {description && (
          <p className="mt-1 text-sm text-slate-600 max-w-3xl leading-relaxed">
            {description}
          </p>
        )}
      </div>
      {action && <div className="shrink-0 flex items-center gap-3">{action}</div>}
    </div>
  )
}
