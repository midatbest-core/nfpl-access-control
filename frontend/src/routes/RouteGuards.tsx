import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { effectiveRoles, landingPath } from '../auth/roles'
import { FullPageLoader } from '../components/Feedback'

export function ProtectedRoute({
  children,
  allowedRoles,
}: {
  children: ReactNode
  allowedRoles?: string[]
}) {
  const auth = useAuth()
  const location = useLocation()
  if (auth.isLoading) return <FullPageLoader label="Checking your secure session" />
  if (!auth.isAuthenticated || !auth.user) {
    return <Navigate to="/login" replace state={{ from: location.pathname, expired: true }} />
  }
  if (auth.user.account_status !== 'active') return <Navigate to="/account-status" replace />
  if (allowedRoles?.length) {
    const roles = effectiveRoles(auth.user)
    if (!allowedRoles.some((role) => roles.has(role))) return <Navigate to="/unauthorized" replace />
  }
  return children
}

export function PublicOnlyRoute({ children }: { children: ReactNode }) {
  const auth = useAuth()
  if (auth.isLoading) return <FullPageLoader label="Checking your secure session" />
  if (auth.user && auth.isAuthenticated) return <Navigate to={landingPath(auth.user)} replace />
  return children
}

export function RoleLanding() {
  const auth = useAuth()
  if (auth.isLoading) return <FullPageLoader label="Preparing your workspace" />
  if (!auth.user || !auth.isAuthenticated) return <Navigate to="/login" replace />
  return <Navigate to={landingPath(auth.user)} replace />
}
