const SESSION_KEY = 'nfpl.auth.session'

export interface StoredSession {
  token: string
  expiresAt: string
}

export function readSession(): StoredSession | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY)
    if (!raw) return null

    const value = JSON.parse(raw) as Partial<StoredSession>
    if (!value.token || !value.expiresAt || Number.isNaN(Date.parse(value.expiresAt))) {
      clearSession()
      return null
    }

    if (Date.parse(value.expiresAt) <= Date.now()) {
      clearSession()
      return null
    }

    return { token: value.token, expiresAt: value.expiresAt }
  } catch {
    clearSession()
    return null
  }
}

export function saveSession(value: StoredSession): void {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(value))
}

export function clearSession(): void {
  sessionStorage.removeItem(SESSION_KEY)
}
