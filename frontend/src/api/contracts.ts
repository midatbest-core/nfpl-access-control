export type AccountStatus = 'pending' | 'active' | 'disabled'
export type EmployeeAvailability = 'available' | 'busy' | 'absent'
export type UserKind = 'staff' | 'client' | 'service'
export type JobDirection = 'import' | 'export'
export type JobMode = 'air' | 'fcl' | 'lcl'

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: 'bearer'
  expires_at: string
}

export interface RegistrationRequest {
  name: string
  email: string
  password: string
  branch_id: string
}

export interface RegistrationResponse {
  id: string
  email: string
  display_name: string
  branch_id: string
  account_status: AccountStatus
}

export interface RoleAssignment {
  id: string
  role_slug: string
  all_clients: boolean
  client_id: string | null
  all_branches: boolean
  branch_id: string | null
  all_directions: boolean
  direction: JobDirection | null
  all_modes: boolean
  mode: JobMode | null
  valid_from: string
  valid_until: string | null
  revoked_at: string | null
}

export interface EmployeeProfile {
  id: string
  email: string
  display_name: string
  kind: UserKind
  branch_id: string | null
  branch_name: string | null
  account_status: AccountStatus
  availability: EmployeeAvailability
  pending_workload: number
  roles: RoleAssignment[]
  created_at: string
}

export interface ErrorEnvelope {
  detail?: string | { explanation?: string; reason_code?: string } | unknown[]
}

export interface DashboardOverview { total_jobs: number; jobs_by_stage: Record<string, number>; total_employees: number; employees_by_availability: Record<string, number>; pending_requests: number; reassignment_required_jobs: number }
export interface UrgentRequest { request_type: string; request_id: string; requested_at: string; requester_user_id: string; reason: string; job_id: string | null; version: number }
export interface ReferenceRecord { id: string; code: string; name: string }
export interface ReferenceData { clients: ReferenceRecord[]; branches: ReferenceRecord[] }
export interface AdminJob { id: string; reference: string; client_id: string; branch_id: string; stage: string; maker_user_id: string | null; checker_user_id: string | null; filing_officer_user_id: string | null; created_at: string; updated_at: string; archived_at: string | null; version: number }
export interface Job { id: string; reference: string; client_id: string; branch_id: string; direction: JobDirection; mode: JobMode; stage: string; goods_description: string; container_reference: string | null; version: number }
export interface EmployeePage { items: EmployeeProfile[]; total: number; page: number; limit: number }
export interface Suggestion { responsibility: string; user_id: string; display_name: string; pending_workload: number }
export interface AuditEvent { id: string; job_id: string | null; actor_user_id: string; action: string; occurred_at: string; reason: string; denied: boolean }
