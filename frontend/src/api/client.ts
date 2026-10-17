import type {
  EmployeeProfile,
  ErrorEnvelope,
  LoginRequest,
  LoginResponse,
  RegistrationRequest,
  RegistrationResponse,
} from './contracts'

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim()
export const API_BASE_URL = (configuredBaseUrl || 'http://localhost:8000').replace(/\/$/, '')

let unauthorizedHandler: (() => void) | undefined

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly reasonCode?: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export function setUnauthorizedHandler(handler: (() => void) | undefined): void {
  unauthorizedHandler = handler
}

function errorMessage(body: ErrorEnvelope | null, fallback: string): {
  message: string
  reasonCode?: string
} {
  if (typeof body?.detail === 'string') return { message: body.detail }
  if (body?.detail && !Array.isArray(body.detail) && typeof body.detail === 'object') {
    const detail = body.detail as { explanation?: string; reason_code?: string }
    if (detail.explanation) {
      return { message: detail.explanation, reasonCode: detail.reason_code }
    }
  }
  if (Array.isArray(body?.detail) && body.detail.length > 0) {
    const first = body.detail[0] as { msg?: string }
    if (first.msg) return { message: first.msg }
  }
  return { message: fallback }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })
  } catch {
    throw new ApiError('The NFPL service could not be reached. Check your connection and try again.', 0)
  }

  if (!response.ok) {
    let body: ErrorEnvelope | null = null
    try {
      body = (await response.json()) as ErrorEnvelope
    } catch {
      // A non-JSON proxy or platform error uses the safe fallback below.
    }
    const fallback = response.status === 401
      ? 'Your session is invalid or has expired.'
      : 'The request could not be completed.'
    const parsed = errorMessage(body, fallback)
    if (response.status === 401 && token) unauthorizedHandler?.()
    throw new ApiError(parsed.message, response.status, parsed.reasonCode)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  login(payload: LoginRequest): Promise<LoginResponse> {
    return request('/v1/auth/login', { method: 'POST', body: JSON.stringify(payload) })
  },
  register(payload: RegistrationRequest): Promise<RegistrationResponse> {
    return request('/v1/auth/register', { method: 'POST', body: JSON.stringify(payload) })
  },
  profile(token: string): Promise<EmployeeProfile> {
    return request('/v1/identity/me', {}, token)
  },
  logout(token: string): Promise<void> {
    return request('/v1/auth/logout', { method: 'POST' }, token)
  },
}
