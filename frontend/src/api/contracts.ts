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
