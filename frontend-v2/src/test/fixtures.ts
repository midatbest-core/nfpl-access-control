import type { EmployeeProfile, RoleAssignment } from '../api/contracts'

export function role(roleSlug: string, overrides: Partial<RoleAssignment> = {}): RoleAssignment {
  return {
    id: `role-${roleSlug}`,
    role_slug: roleSlug,
    all_clients: true,
    client_id: null,
    all_branches: true,
    branch_id: null,
    all_directions: true,
    direction: null,
    all_modes: true,
    mode: null,
    valid_from: '2025-01-01T00:00:00Z',
    valid_until: null,
    revoked_at: null,
    ...overrides,
  }
}

export function profile(
  roleSlugs: string[] = ['maker'],
  overrides: Partial<EmployeeProfile> = {},
): EmployeeProfile {
  return {
    id: 'user-1',
    email: 'morgan.lee@nfpl.test',
    display_name: 'Morgan Lee',
    kind: 'staff',
    branch_id: 'branch-1',
    branch_name: 'Main Branch',
    account_status: 'active',
    availability: 'available',
    pending_workload: 3,
    roles: roleSlugs.map((slug) => role(slug)),
    created_at: '2025-01-01T00:00:00Z',
    ...overrides,
  }
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export function mockJob(overrides: Partial<import('../api/contracts').Job> = {}): import('../api/contracts').Job {
  return {
    id: 'job-101',
    reference: 'NFPL-2026-AIR-001',
    client_id: 'client-1',
    client_name: 'Acme Logistics',
    branch_id: 'branch-1',
    branch_name: 'Primary Port',
    direction: 'import',
    mode: 'air',
    stage: 'draft',
    goods_description: 'Electronic components and sensors',
    container_reference: 'CONT-10029',
    checklist_data: {
      items: [
        { key: 'invoice_check', label: 'Commercial Invoice Verified', required: true, status: null, justification: null },
        { key: 'origin_cert', label: 'Certificate of Origin Attached', required: false, status: null, justification: null },
      ],
    },
    checklist_revision: 1,
    maker_edit_locked: false,
    maker_correction_required: false,
    checker_correction_required: false,
    last_return_category: null,
    last_return_reason: null,
    last_maker_justification: null,
    last_checker_justification: null,
    prepared_by_user_id: null,
    checked_by_user_id: null,
    filed_by_user_id: null,
    version: 1,
    ...overrides,
  }
}

export function mockReferenceData(): import('../api/contracts').ReferenceData {
  return {
    clients: [
      { id: 'client-1', name: 'Acme Logistics', code: 'ACME' },
      { id: 'client-2', name: 'Global Freight', code: 'GLBL' },
    ],
    branches: [
      { id: 'branch-1', name: 'Primary Port', code: 'PORT-01' },
      { id: 'branch-2', name: 'Airport Hub', code: 'AIR-02' },
    ],
  }
}

