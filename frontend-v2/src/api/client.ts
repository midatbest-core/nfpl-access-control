import type {
  AbsenceCandidate,
  AbsenceNomination,
  AbsenceOutcome,
  AdminJob,
  AttentionJobPage,
  AttentionReceipt,
  AuditEvent,
  ChecklistItem,
  ClientJobDetail,
  ClientShipmentPage,
  ClientShipmentStatus,
  ClientUpdate,
  ClientUpdatePage,
  DashboardOverview,
  DelegationRequest,
  DelegationResponse,
  EditRequest,
  EmployeePage,
  EmployeeProfile,
  ErrorEnvelope,
  FilingReturnCategory,
  Job,
  JobCreate,
  JobResponsibilityDetail,
  LoginRequest,
  LoginResponse,
  Notification,
  OperationalHistoryItem,
  ReferenceData,
  RegistrationRequest,
  RegistrationResponse,
  Suggestion,
  UrgentRequest,
  WorkQueuePage,
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

function parseErrorMessage(body: ErrorEnvelope | null, fallback: string): {
  message: string
  reasonCode?: string
} {
  if (!body) return { message: fallback }

  if (typeof body.detail === 'string') {
    return { message: body.detail }
  }

  if (body.detail && !Array.isArray(body.detail) && typeof body.detail === 'object') {
    const detail = body.detail as { explanation?: string; reason_code?: string }
    if (detail.explanation) {
      return { message: detail.explanation, reasonCode: detail.reason_code }
    }
  }

  if (Array.isArray(body.detail) && body.detail.length > 0) {
    const first = body.detail[0] as { msg?: string; loc?: string[] }
    if (first?.msg) {
      const field = first.loc && first.loc.length > 1 ? `${first.loc[first.loc.length - 1]}: ` : ''
      return { message: `${field}${first.msg}` }
    }
  }

  return { message: fallback }
}

const MAX_CONCURRENT_REQUESTS = 4
let activeRequests = 0
const pendingQueue: Array<() => void> = []

function acquireRequestSlot(): Promise<void> {
  if (activeRequests < MAX_CONCURRENT_REQUESTS) {
    activeRequests++
    return Promise.resolve()
  }
  return new Promise<void>((resolve) => {
    let resolved = false
    const proceed = () => {
      if (resolved) return
      resolved = true
      activeRequests++
      resolve()
    }
    pendingQueue.push(proceed)
    setTimeout(proceed, 4000)
  })
}

function releaseRequestSlot(): void {
  activeRequests = Math.max(0, activeRequests - 1)
  const next = pendingQueue.shift()
  if (next) {
    next()
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<T> {
  await acquireRequestSlot()
  try {
    const headers = new Headers(options.headers)
    if (options.body && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }
    if (token) {
      headers.set('Authorization', `Bearer ${token}`)
    }

    const signal = options.signal || (typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function' ? AbortSignal.timeout(15000) : undefined)

    let response: Response
    try {
      response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers, signal })
    } catch {
      throw new ApiError('The NFPL service could not be reached. Check your connection and try again.', 0)
    }

  if (!response.ok) {
    let body: ErrorEnvelope | null = null
    try {
      body = (await response.json()) as ErrorEnvelope
    } catch {
      // Body is not JSON
    }

    const fallback =
      response.status === 401
        ? 'Your session is invalid or has expired.'
        : response.status === 403
          ? 'You do not have permission to perform this action.'
          : response.status === 404
            ? 'The requested resource was not found.'
            : 'The request could not be completed.'

    const parsed = parseErrorMessage(body, fallback)

    if (response.status === 401 && token) {
      unauthorizedHandler?.()
    }

    throw new ApiError(parsed.message, response.status, parsed.reasonCode)
  }

  if (
    typeof window !== 'undefined' &&
    options.method &&
    options.method !== 'GET' &&
    !path.includes('/notifications') &&
    !path.includes('/auth')
  ) {
    window.setTimeout(() => {
      window.dispatchEvent(new CustomEvent('nfpl:refresh-notifications'))
    }, 1000)
  }

    if (response.status === 204) {
      return undefined as T
    }

    return (await response.json()) as T
  } finally {
    releaseRequestSlot()
  }
}

export const api = {
  // Authentication & Identity
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

  // Self Availability
  updateAvailability(token: string, availability: 'available' | 'busy' | 'absent'): Promise<EmployeeProfile> {
    return request('/v1/employees/me/availability', { method: 'PATCH', body: JSON.stringify({ availability }) }, token)
  },

  // Admin Dashboard & Reference Data
  adminOverview(token: string): Promise<DashboardOverview> {
    return request('/v1/admin/dashboard/overview', {}, token)
  },
  urgentRequests(token: string): Promise<UrgentRequest[]> {
    return request('/v1/admin/dashboard/urgent-requests', {}, token)
  },
  attentionJobs(token: string, cursor?: string): Promise<AttentionJobPage> {
    const query = new URLSearchParams({ limit: '25' })
    if (cursor) query.set('cursor', cursor)
    return request(`/v1/admin/jobs-requiring-attention?${query}`, {}, token)
  },
  referenceData(token: string): Promise<ReferenceData> {
    return request('/v1/admin/reference-data', {}, token)
  },

  // Admin Jobs Management
  adminJobs(token: string, search = '', offset = 0): Promise<AdminJob[]> {
    const query = new URLSearchParams({ offset: String(offset), limit: '25' })
    if (search.trim()) query.set('search', search.trim())
    return request(`/v1/admin/jobs?${query}`, {}, token)
  },
  job(token: string, id: string): Promise<Job> {
    return request(`/v1/jobs/${id}`, {}, token)
  },
  createJob(token: string, payload: JobCreate): Promise<Job> {
    return request('/v1/jobs', { method: 'POST', body: JSON.stringify(payload) }, token)
  },
  archiveJob(token: string, id: string, expected_version: number, reason: string): Promise<AdminJob> {
    return request(`/v1/admin/jobs/${id}/archive`, { method: 'POST', body: JSON.stringify({ expected_version, reason }) }, token)
  },
  cancelJob(token: string, id: string, expected_version: number, reason: string): Promise<Job> {
    return request(`/v1/jobs/${id}/cancel`, { method: 'POST', body: JSON.stringify({ expected_version, reason }) }, token)
  },
  suggestions(token: string, id: string): Promise<Record<string, Suggestion[]>> {
    return request(`/v1/admin/jobs/${id}/assignment-suggestions`, {}, token)
  },
  assign(token: string, id: string, responsibility: string, target_user_id: string | null, reason: string): Promise<unknown> {
    return request(`/v1/admin/jobs/${id}/assignment`, { method: 'PUT', body: JSON.stringify({ responsibility, target_user_id, reason }) }, token)
  },
  delegateJob(token: string, jobId: string, payload: DelegationRequest): Promise<DelegationResponse> {
    return request(`/v1/admin/jobs/${jobId}/delegations`, { method: 'POST', body: JSON.stringify(payload) }, token)
  },
  revokeDelegation(token: string, delegationId: string, reason: string): Promise<DelegationResponse> {
    return request(`/v1/admin/delegations/${delegationId}/revoke`, { method: 'POST', body: JSON.stringify({ reason }) }, token)
  },

  // Admin Employee & Role Management
  employees(token: string, page = 1, search = ''): Promise<EmployeePage> {
    const query = new URLSearchParams({ page: String(page), limit: '25' })
    if (search.trim()) query.set('search', search.trim())
    return request(`/v1/admin/employees?${query}`, {}, token)
  },
  employeeAction(token: string, id: string, action: 'approve' | 'reject' | 'activate' | 'deactivate', reason: string): Promise<EmployeeProfile> {
    return request(`/v1/admin/employees/${id}/${action}`, { method: 'POST', body: JSON.stringify({ reason }) }, token)
  },
  grantRole(token: string, payload: unknown): Promise<unknown> {
    return request('/v1/admin/role-assignments', { method: 'POST', body: JSON.stringify(payload) }, token)
  },
  revokeRole(token: string, id: string, reason: string): Promise<unknown> {
    return request(`/v1/admin/role-assignments/${id}/revoke`, { method: 'POST', body: JSON.stringify({ reason }) }, token)
  },

  // Admin Audit
  audit(token: string, jobId: string): Promise<AuditEvent[]> {
    return request(`/v1/admin/jobs/${jobId}/audit`, {}, token)
  },

  // Admin Decisions & Exceptions
  absenceDecision(token: string, id: string, expected_version: number, approved: boolean, reason: string): Promise<unknown> {
    return request(`/v1/admin/absence-nominations/${id}/decision`, { method: 'POST', body: JSON.stringify({ expected_version, approved, reason }) }, token)
  },
  absenceCandidates(token: string): Promise<AbsenceCandidate[]> {
    return request('/v1/absence-nominations/candidates', {}, token)
  },
  absenceNominations(token: string): Promise<AbsenceNomination[]> {
    return request('/v1/absence-nominations', {}, token)
  },
  createAbsenceNomination(token: string, payload: { nominee_user_id: string; valid_from: string; valid_until: string; reason: string }): Promise<AbsenceNomination> {
    return request('/v1/absence-nominations', { method: 'POST', body: JSON.stringify(payload) }, token)
  },
  absenceOutcomes(token: string, id: string): Promise<AbsenceOutcome[]> {
    return request(`/v1/admin/absence-nominations/${id}/outcomes`, {}, token)
  },
  overrideAbsenceOutcome(token: string, id: string, replacement_user_id: string, reason: string): Promise<AbsenceOutcome> {
    return request(`/v1/admin/absence-outcomes/${id}/override`, { method: 'POST', body: JSON.stringify({ replacement_user_id, reason }) }, token)
  },
  editDecision(token: string, id: string, expected_version: number, approved: boolean, reason: string): Promise<unknown> {
    return request(`/v1/admin/edit-requests/${id}/decision`, { method: 'POST', body: JSON.stringify({ expected_version, approved, reason }) }, token)
  },
  exceptionApproval(token: string, id: string, expected_version: number): Promise<unknown> {
    return request(`/v1/admin/exception-requests/${id}/approve`, { method: 'POST', body: JSON.stringify({ expected_version }) }, token)
  },
  exceptionRequest(token: string, id: string, action: 'cancel' | 'reopen', reason: string): Promise<unknown> {
    return request(`/v1/admin/jobs/${id}/exception-requests`, { method: 'POST', body: JSON.stringify({ action, reason }) }, token)
  },

  // Operational Work Queue & Actions
  myWork(token: string, cursor?: string, limit = 20, search = ''): Promise<WorkQueuePage> {
    const query = new URLSearchParams({ limit: String(limit) })
    if (cursor) query.set('cursor', cursor)
    if (search.trim()) query.set('search', search.trim())
    return request(`/v1/my-work?${query}`, {}, token)
  },
  jobResponsibilities(token: string, id: string): Promise<JobResponsibilityDetail[]> {
    return request(`/v1/jobs/${id}/responsibilities`, {}, token)
  },
  updateJob(token: string, id: string, payload: { expected_version: number; goods_description: string; container_reference: string | null }): Promise<Job> {
    return request(`/v1/jobs/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }, token)
  },
  prepareJob(token: string, id: string, expected_version: number, justification: string): Promise<Job> {
    return request(`/v1/jobs/${id}/prepare`, { method: 'POST', body: JSON.stringify({ expected_version, checklist_data: null, justification }) }, token)
  },
  checkJob(token: string, id: string, payload: {
    expected_version: number
    approved: boolean
    reason: string
    checklist_items: Array<{
      key: string
      status: NonNullable<ChecklistItem['status']>
      justification: string | null
    }>
    justification: string
  }): Promise<Job> {
    return request(`/v1/jobs/${id}/check`, { method: 'POST', body: JSON.stringify(payload) }, token)
  },
  fileJob(token: string, id: string, expected_version: number): Promise<Job> {
    return request(`/v1/jobs/${id}/file`, { method: 'POST', body: JSON.stringify({ expected_version }) }, token)
  },
  returnForCorrection(token: string, id: string, expected_version: number, category: FilingReturnCategory, reason: string): Promise<Job> {
    return request(`/v1/jobs/${id}/return-for-correction`, { method: 'POST', body: JSON.stringify({ expected_version, category, reason }) }, token)
  },
  requestJobEdit(token: string, id: string, reason: string): Promise<EditRequest> {
    return request(`/v1/jobs/${id}/edit-requests`, { method: 'POST', body: JSON.stringify({ reason }) }, token)
  },
  operationalHistory(token: string, id: string): Promise<OperationalHistoryItem[]> {
    return request(`/v1/jobs/${id}/operational-history?limit=25`, {}, token)
  },

  // Notifications
  notifications(token: string, before?: string, unreadOnly = false): Promise<Notification[]> {
    const query = new URLSearchParams({ limit: '25' })
    if (before) query.set('before', before)
    if (unreadOnly) query.set('unread_only', 'true')
    return request(`/v1/notifications?${query}`, {}, token)
  },
  unreadNotificationCount(token: string): Promise<{ count: number }> {
    return request('/v1/notifications/unread-count', {}, token)
  },
  markNotificationRead(token: string, id: string): Promise<Notification> {
    return request(`/v1/notifications/${id}/read`, { method: 'POST' }, token)
  },
  markAllNotificationsRead(token: string): Promise<{ updated: number }> {
    return request('/v1/notifications/read-all', { method: 'POST' }, token)
  },

  // Client Viewer Portal
  clientJobs(token: string, cursor?: string, limit = 25, search = ''): Promise<ClientShipmentPage> {
    const query = new URLSearchParams({ limit: String(limit) })
    if (cursor) query.set('cursor', cursor)
    if (search.trim()) query.set('search', search.trim())
    return request(`/v1/client/jobs?${query}`, {}, token)
  },
  clientJob(token: string, id: string): Promise<ClientJobDetail> {
    return request(`/v1/jobs/${id}`, {}, token)
  },
  clientStatus(token: string, id: string): Promise<ClientShipmentStatus> {
    return request(`/v1/client/jobs/${id}/status`, {}, token)
  },
  clientHistory(token: string, id: string, beforeVersion?: number): Promise<ClientUpdate[]> {
    const query = new URLSearchParams({ limit: '25' })
    if (beforeVersion) query.set('before_version', String(beforeVersion))
    return request(`/v1/client/jobs/${id}/history?${query}`, {}, token)
  },
  clientUpdates(token: string, cursor?: string, limit = 25): Promise<ClientUpdatePage> {
    const query = new URLSearchParams({ limit: String(limit) })
    if (cursor) query.set('cursor', cursor)
    return request(`/v1/client/updates?${query}`, {}, token)
  },
  clientQuery(token: string, id: string, category: string, explanation: string): Promise<AttentionReceipt> {
    return request(`/v1/client/jobs/${id}/queries`, { method: 'POST', body: JSON.stringify({ category, explanation }) }, token)
  },
  adminAttention(token: string, id: string, explanation: string): Promise<AttentionReceipt> {
    return request(`/v1/admin/jobs/${id}/attention`, { method: 'POST', body: JSON.stringify({ explanation }) }, token)
  },
}
