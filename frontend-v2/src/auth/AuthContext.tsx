import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { api, setUnauthorizedHandler } from '../api/client'
import type { EmployeeProfile, LoginRequest } from '../api/contracts'
import { clearSession, readSession, saveSession } from './session'
import type { StoredSession } from './session'

interface AuthContextValue {
  user: EmployeeProfile | null
  token: string | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (credentials: LoginRequest) => Promise<EmployeeProfile>
  logout: () => Promise<void>
  refreshProfile: () => Promise<EmployeeProfile | null>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<StoredSession | null>(() => readSession())
  const [user, setUser] = useState<EmployeeProfile | null>(null)
  const [isLoading, setIsLoading] = useState(() => session !== null)

  const endSession = useCallback(() => {
    clearSession()
    setSession(null)
    setUser(null)
    setIsLoading(false)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(endSession)
    return () => setUnauthorizedHandler(undefined)
  }, [endSession])

  useEffect(() => {
    if (!session) return
    const delay = Date.parse(session.expiresAt) - Date.now()
    const timer = window.setTimeout(
      endSession,
      Math.max(0, Math.min(delay, 2_147_000_000)),
    )
    return () => window.clearTimeout(timer)
  }, [endSession, session])

  useEffect(() => {
    if (!session || user) return
    let active = true
    api.profile(session.token)
      .then((profile) => {
        if (active) {
          setUser(profile)
          setIsLoading(false)
        }
      })
      .catch(() => {
        if (active) endSession()
      })
    return () => {
      active = false
    }
  }, [endSession, session, user])

  const login = useCallback(async (credentials: LoginRequest) => {
    try {
      const result = await api.login(credentials)
      const nextSession = { token: result.access_token, expiresAt: result.expires_at }
      saveSession(nextSession)
      const profile = await api.profile(nextSession.token)
      setSession(nextSession)
      setUser(profile)
      return profile
    } catch (error) {
      clearSession()
      setSession(null)
      setUser(null)
      throw error
    }
  }, [])

  const logout = useCallback(async () => {
    const currentToken = session?.token
    try {
      if (currentToken) {
        await api.logout(currentToken)
      }
    } finally {
      endSession()
    }
  }, [endSession, session])

  const refreshProfile = useCallback(async () => {
    if (!session?.token) return null
    try {
      const profile = await api.profile(session.token)
      setUser(profile)
      return profile
    } catch {
      endSession()
      return null
    }
  }, [endSession, session])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token: session?.token ?? null,
      isLoading,
      isAuthenticated: Boolean(session && user),
      login,
      logout,
      refreshProfile,
    }),
    [isLoading, login, logout, refreshProfile, session, user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (!value) {
    throw new Error('useAuth must be used inside AuthProvider')
  }
  return value
}
