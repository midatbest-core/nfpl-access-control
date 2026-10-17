import type {
  EmployeeProfile,
  ErrorEnvelope,
  LoginRequest,
  LoginResponse,
  RegistrationRequest,
  RegistrationResponse,
  AdminJob, AuditEvent, DashboardOverview, EmployeePage, Job, Suggestion, UrgentRequest, ReferenceData,
  EditRequest, JobCreate, JobResponsibilityDetail, Notification, WorkQueuePage,
  ChecklistItem, ClientJobDetail, ClientShipmentPage, ClientShipmentStatus,
  ClientUpdate, ClientUpdatePage, FilingReturnCategory, OperationalHistoryItem,
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
  adminOverview: (token: string) => request<DashboardOverview>('/v1/admin/dashboard/overview', {}, token),
  urgentRequests: (token: string) => request<UrgentRequest[]>('/v1/admin/dashboard/urgent-requests', {}, token),
  referenceData: (token: string) => request<ReferenceData>('/v1/admin/reference-data', {}, token),
  adminJobs: (token: string, search = '', offset = 0) => request<AdminJob[]>(`/v1/admin/jobs?search=${encodeURIComponent(search)}&offset=${offset}&limit=25`, {}, token),
  job: (token: string, id: string) => request<Job>(`/v1/jobs/${id}`, {}, token),
  createJob: (token: string, payload: JobCreate) => request<Job>('/v1/jobs', { method: 'POST', body: JSON.stringify(payload) }, token),
  archiveJob: (token: string, id: string, expected_version: number, reason: string) => request<AdminJob>(`/v1/admin/jobs/${id}/archive`, { method: 'POST', body: JSON.stringify({ expected_version, reason }) }, token),
  cancelJob: (token: string, id: string, expected_version: number, reason: string) => request<Job>(`/v1/jobs/${id}/cancel`, { method: 'POST', body: JSON.stringify({ expected_version, reason }) }, token),
  suggestions: (token: string, id: string) => request<Record<string, Suggestion[]>>(`/v1/admin/jobs/${id}/assignment-suggestions`, {}, token),
  assign: (token: string, id: string, responsibility: string, target_user_id: string | null, reason: string) => request(`/v1/admin/jobs/${id}/assignment`, { method: 'PUT', body: JSON.stringify({ responsibility, target_user_id, reason }) }, token),
  employees: (token: string, page = 1, search = '') => request<EmployeePage>(`/v1/admin/employees?page=${page}&limit=25&search=${encodeURIComponent(search)}`, {}, token),
  employeeAction: (token: string, id: string, action: 'approve'|'reject'|'activate'|'deactivate', reason: string) => request<EmployeeProfile>(`/v1/admin/employees/${id}/${action}`, { method: 'POST', body: JSON.stringify({ reason }) }, token),
  audit: (token: string, jobId: string) => request<AuditEvent[]>(`/v1/admin/jobs/${jobId}/audit`, {}, token),
  absenceDecision: (token: string, id: string, expected_version: number, approved: boolean, reason: string) => request(`/v1/admin/absence-nominations/${id}/decision`, { method: 'POST', body: JSON.stringify({ expected_version, approved, reason }) }, token),
  editDecision: (token: string, id: string, expected_version: number, approved: boolean, reason: string) => request(`/v1/admin/edit-requests/${id}/decision`, { method: 'POST', body: JSON.stringify({ expected_version, approved, reason }) }, token),
  exceptionApproval: (token: string, id: string, expected_version: number) => request(`/v1/admin/exception-requests/${id}/approve`, { method: 'POST', body: JSON.stringify({ expected_version }) }, token),
  exceptionRequest: (token: string, id: string, action: 'cancel' | 'reopen', reason: string) => request(`/v1/admin/jobs/${id}/exception-requests`, { method: 'POST', body: JSON.stringify({ action, reason }) }, token),
  grantRole: (token: string, payload: unknown) => request('/v1/admin/role-assignments', { method: 'POST', body: JSON.stringify(payload) }, token),
  revokeRole: (token: string, id: string, reason: string) => request(`/v1/admin/role-assignments/${id}/revoke`, { method: 'POST', body: JSON.stringify({ reason }) }, token),
  myWork: (token: string, cursor?: string, limit = 20) => {
    const query = new URLSearchParams({ limit: String(limit) })
    if (cursor) query.set('cursor', cursor)
    return request<WorkQueuePage>(`/v1/my-work?${query}`, {}, token)
  },
  jobResponsibilities: (token: string, id: string) => request<JobResponsibilityDetail[]>(`/v1/jobs/${id}/responsibilities`, {}, token),
  updateJob: (token: string, id: string, payload: { expected_version: number; goods_description: string; container_reference: string | null }) => request<Job>(`/v1/jobs/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }, token),
  prepareJob: (token: string, id: string, expected_version: number, justification: string) => request<Job>(`/v1/jobs/${id}/prepare`, { method: 'POST', body: JSON.stringify({ expected_version, checklist_data: null, justification }) }, token),
  requestJobEdit: (token: string, id: string, reason: string) => request<EditRequest>(`/v1/jobs/${id}/edit-requests`, { method: 'POST', body: JSON.stringify({ reason }) }, token),
  notifications: (token: string, before?: string) => {
    const query = new URLSearchParams({ limit: '25' })
    if (before) query.set('before', before)
    return request<Notification[]>(`/v1/notifications?${query}`, {}, token)
  },
  unreadNotificationCount: (token: string) => request<{ count: number }>('/v1/notifications/unread-count', {}, token),
  markNotificationRead: (token: string, id: string) => request<Notification>(`/v1/notifications/${id}/read`, { method: 'POST' }, token),
  checkJob: (token: string, id: string, payload: {
    expected_version: number
    approved: boolean
    reason: string
    checklist_items: Array<{
      key: string
      status: NonNullable<ChecklistItem['status']>
      justification: string | null
    }>
    justification: string
  }) => request<Job>(`/v1/jobs/${id}/check`, { method: 'POST', body: JSON.stringify(payload) }, token),
  fileJob: (token: string, id: string, expected_version: number) => request<Job>(`/v1/jobs/${id}/file`, { method: 'POST', body: JSON.stringify({ expected_version }) }, token),
  returnForCorrection: (token: string, id: string, expected_version: number, category: FilingReturnCategory, reason: string) => request<Job>(`/v1/jobs/${id}/return-for-correction`, { method: 'POST', body: JSON.stringify({ expected_version, category, reason }) }, token),
  operationalHistory: (token: string, id: string) => request<OperationalHistoryItem[]>(`/v1/jobs/${id}/operational-history?limit=25`, {}, token),
  clientJobs: (token: string, cursor?: string, limit = 25) => {
    const query = new URLSearchParams({ limit: String(limit) })
    if (cursor) query.set('cursor', cursor)
    return request<ClientShipmentPage>(`/v1/client/jobs?${query}`, {}, token)
  },
  clientJob: (token: string, id: string) => request<ClientJobDetail>(`/v1/jobs/${id}`, {}, token),
  clientStatus: (token: string, id: string) => request<ClientShipmentStatus>(`/v1/client/jobs/${id}/status`, {}, token),
  clientHistory: (token: string, id: string, beforeVersion?: number) => {
    const query = new URLSearchParams({ limit: '25' })
    if (beforeVersion) query.set('before_version', String(beforeVersion))
    return request<ClientUpdate[]>(`/v1/client/jobs/${id}/history?${query}`, {}, token)
  },
  clientUpdates: (token: string, cursor?: string, limit = 25) => {
    const query = new URLSearchParams({ limit: String(limit) })
    if (cursor) query.set('cursor', cursor)
    return request<ClientUpdatePage>(`/v1/client/updates?${query}`, {}, token)
  },
}
