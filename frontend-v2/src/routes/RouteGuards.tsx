import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { effectiveRoles, landingPath } from '../auth/roles'

export function FullPageSpinner({ label = 'Verifying workspace access...' }: { label?: string }) {
  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 px-6" aria-busy="true">
      <div className="flex flex-col items-center text-center">
        <div className="relative">
          <div className="h-12 w-12 rounded-full border-3 border-cyan-100 border-t-cyan-600 animate-spin" />
        </div>
        <p className="mt-4 text-xs font-bold uppercase tracking-wider text-slate-500">
          {label}
        </p>
      </div>
    </main>
  )
}

export function ProtectedRoute({
  children,
  allowedRoles,
}: {
  children: ReactNode
  allowedRoles?: string[]
}) {
  const auth = useAuth()
  const location = useLocation()

  if (auth.isLoading) {
    return <FullPageSpinner label="Checking secure session" />
  }

  if (!auth.isAuthenticated || !auth.user) {
    return <Navigate to="/login" replace state={{ from: location.pathname, expired: true }} />
  }

  if (auth.user.account_status !== 'active') {
    return <Navigate to="/account-status" replace />
  }

  if (allowedRoles && allowedRoles.length > 0) {
    const roles = effectiveRoles(auth.user)
    const hasRole = allowedRoles.some((role) => roles.has(role))
    if (!hasRole) {
      return <Navigate to="/unauthorized" replace />
    }
  }

  return children
}

export function PublicOnlyRoute({ children }: { children: ReactNode }) {
  const auth = useAuth()

  if (auth.isLoading) {
    return <FullPageSpinner label="Checking secure session" />
  }

  if (auth.isAuthenticated && auth.user) {
    return <Navigate to={landingPath(auth.user)} replace />
  }

  return children
}

export function RoleLanding() {
  const auth = useAuth()

  if (auth.isLoading) {
    return <FullPageSpinner label="Preparing your workspace" />
  }

  if (!auth.isAuthenticated || !auth.user) {
    return <Navigate to="/login" replace />
  }

  return <Navigate to={landingPath(auth.user)} replace />
}
