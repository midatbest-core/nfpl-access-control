export type AccountStatus = 'pending' | 'active' | 'disabled'
export type EmployeeAvailability = 'available' | 'busy' | 'absent'
export type UserKind = 'staff' | 'client' | 'service'
export type JobDirection = 'import' | 'export'
export type JobMode = 'air' | 'fcl' | 'lcl'
export type JobStage = 'confirmed' | 'prepared' | 'checked' | 'filed' | 'cancelled' | 'reopened' | 'archived'
export type ChecklistStatus = 'complete' | 'incomplete' | 'not_applicable'
export type FilingReturnCategory = 'maker_fault' | 'checker_fault' | 'both'

export type AuditActionCategory =
  | 'workflow'
  | 'access'
  | 'responsibility'
  | 'exception'
  | 'security'

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
  detail?: string | { explanation?: string; reason_code?: string } | Array<{ msg?: string; loc?: string[] }>
}

export interface DashboardOverview {
  total_jobs: number
  jobs_by_stage: Record<string, number>
  total_employees: number
  employees_by_availability: Record<string, number>
  pending_requests: number
  reassignment_required_jobs: number
}

export interface UrgentRequest {
  request_type: string
  request_id: string
  requested_at: string
  requester_user_id: string
  reason: string
  job_id: string | null
  version: number
}

export interface ReferenceRecord {
  id: string
  code: string
  name: string
}

export interface ReferenceData {
  clients: ReferenceRecord[]
  branches: ReferenceRecord[]
}

export interface AdminJob {
  id: string
  reference: string
  client_id: string
  client_name: string
  branch_id: string
  branch_name: string
  stage: string
  maker_user_id: string | null
  checker_user_id: string | null
  filing_officer_user_id: string | null
  created_at: string
  updated_at: string
  archived_at: string | null
  version: number
}

export interface Job {
  id: string
  reference: string
  client_id: string
  client_name: string
  branch_id: string
  branch_name: string
  direction: JobDirection
  mode: JobMode
  stage: string
  goods_description: string
  container_reference: string | null
  checklist_data: Record<string, unknown>
  checklist_revision: number
  maker_edit_locked: boolean
  maker_correction_required: boolean
  checker_correction_required: boolean
  last_return_category: string | null
  last_return_reason: string | null
  last_maker_justification: string | null
  last_checker_justification: string | null
  prepared_by_user_id: string | null
  checked_by_user_id: string | null
  filed_by_user_id: string | null
  version: number
}

export interface ChecklistItem {
  key: string
  label: string
  required: boolean
  status: ChecklistStatus | null
  justification: string | null
}

export interface JobCreate {
  reference: string
  client_id: string
  branch_id: string
  direction: JobDirection
  mode: JobMode
  goods_description: string
  container_reference: string | null
}

export interface EmployeePage {
  items: EmployeeProfile[]
  total: number
  page: number
  limit: number
}

export interface Suggestion {
  responsibility: string
  user_id: string
  display_name: string
  pending_workload: number
}

export interface AuditEvent {
  id: string
  job_id: string | null
  actor_user_id: string
  actor_display_name: string
  action: string
  occurred_at: string
  reason: string
  before_state: Record<string, unknown> | null
  after_state: Record<string, unknown> | null
  authorization_context: Record<string, unknown>
  affected_job_version: number | null
  denied: boolean
}

export interface AbsenceCandidate {
  user_id: string
  display_name: string
  eligible_assignment_count: number
  total_assignment_count: number
}

export interface AbsenceNomination {
  id: string
  requester_user_id: string
  nominee_user_id: string
  valid_from: string
  valid_until: string
  reason: string
  status: string
  requested_at: string
  decided_by_user_id: string | null
  decided_at: string | null
  decision_reason: string | null
  version: number
}

export interface AbsenceOutcome {
  id: string
  nomination_id: string
  job_id: string
  responsibility: string
  nominee_user_id: string
  outcome: string
  reason: string
  delegation_id: string | null
}

export interface DelegationRequest {
  responsibility: 'maker' | 'checker' | 'filing_officer'
  delegate_user_id: string
  valid_from: string
  valid_until: string
  reason: string
}

export interface DelegationResponse {
  id: string
  job_id: string
  responsibility: 'maker' | 'checker' | 'filing_officer'
  delegator_user_id: string
  delegate_user_id: string
  valid_from: string
  valid_until: string
  revoked_at: string | null
}

export interface AttentionJob {
  job_id: string
  reference: string
  client_name: string
  branch_name: string
  stage: string
  version: number
  reasons: string[]
}

export interface AttentionJobPage {
  items: AttentionJob[]
  next_cursor: string | null
}

export interface AttentionReceipt {
  audit_event_id: string
  delivered: number
}

export interface WorkQueueItem {
  job_id: string
  reference: string
  client_id: string
  client_name: string
  branch_id: string
  branch_name: string
  direction: JobDirection
  mode: JobMode
  stage: string
  responsibility: 'maker' | 'checker' | 'filing_officer'
  next_action: string
  feedback: string | null
  assigned_at: string
  priority: number
  version: number
  is_delegated: boolean
}

export interface WorkQueuePage {
  items: WorkQueueItem[]
  count: number
  limit: number
  next_cursor: string | null
}

export interface JobResponsibilityDetail {
  responsibility: 'maker' | 'checker' | 'filing_officer'
  user_id: string | null
  display_name: string | null
  current_actor_responsible: boolean
  via_delegation: boolean
}

export interface Notification {
  id: string
  job_id: string | null
  job_reference: string | null
  event_type: string
  message: string
  target_path: string
  created_at: string
  read_at: string | null
}

export interface EditRequest {
  id: string
  job_id: string
  status: string
  requested_by_user_id: string
  requested_at: string
  reason: string
  decided_by_user_id: string | null
  decided_at: string | null
  decision_reason: string | null
}

export interface OperationalHistoryItem {
  version_number: number
  occurred_at: string
  actor_user_id: string
  action: string
  reason: string
  stage: string
  changed_fields: string[]
}

export interface ClientJobDetail {
  id: string
  reference: string
  client_id: string
  direction: JobDirection
  mode: JobMode
  stage: string
  version: number
}

export interface ClientShipmentSummary {
  job_id: string
  reference: string
  direction: JobDirection
  mode: JobMode
  stage: string
  progress_percent: number
  updated_at: string
  version: number
}

export interface ClientShipmentPage {
  items: ClientShipmentSummary[]
  next_cursor: string | null
}

export interface ClientShipmentStatus {
  job_id: string
  reference: string
  stage: string
  progress_percent: number
  updated_at: string
  version: number
}

export interface ClientUpdate {
  cursor: string
  job_id: string
  reference: string
  stage: string
  progress_percent: number
  message: string
  occurred_at: string
  version: number
}

export interface ClientUpdatePage {
  items: ClientUpdate[]
  next_cursor: string | null
}
